use crate::AppConfig;
use crate::Backend;
use arrayvec::ArrayVec;
use shenango::thread;
use shenango::udp::UdpSpawner;
use std::io::{ErrorKind, Read, Write};
use std::net::SocketAddrV4;
use std::os::raw::c_void;
use std::slice;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;

use crate::hintmap::HintMap;
use crate::payload::HINT_CLASS_IGNORED;
use crate::Connection;
use crate::FakeWorker;
use crate::Payload;
use crate::payload::Stamps;
use crate::KBUFSIZE;
use crate::PAYLOAD_SIZE;

/// How a server treats scheduling hints.
#[derive(Clone)]
pub enum ServerHints {
    /// Do not apply hints; replies report HINT_CLASS_IGNORED. Also used for
    /// the Linux backend, which has no Caladan runtime.
    Ignore,
    /// Apply hints from the map by request kind; replies report the class the
    /// runtime holds for the handler thread.
    Apply(Arc<HintMap>),
}

impl ServerHints {
    pub fn from_config(config: &AppConfig) -> Self {
        if config.ignore_hints || !matches!(config.backend, Backend::Runtime) {
            return ServerHints::Ignore;
        }
        let map = config.hintmap().unwrap_or_default();
        ServerHints::Apply(Arc::new(map))
    }

    fn describe(&self) -> String {
        match self {
            ServerHints::Ignore => "hints: ignored".to_string(),
            ServerHints::Apply(m) if m.is_empty() => "hints: none mapped".to_string(),
            ServerHints::Apply(m) => format!("hints: applying {:?}", m),
        }
    }
}

use std::io;

pub fn run_linux_udp_server(config: AppConfig) {
    let worker = config.fakeworker();
    let backend = config.backend;
    let addr = config.addrs[0];
    let join_handles: Vec<_> = (0..config.nthreads)
        .map(|_| {
            let worker = worker.clone();
            backend.spawn_thread(move || {
                let socket = backend.create_udp_connection(Some(addr), None).unwrap();
                println!("Bound to address {}", socket.local_addr());
                let mut buf = vec![0; KBUFSIZE];
                loop {
                    let (len, remote_addr) = socket.recv_from(&mut buf[..]).unwrap();
                    let payload = match Payload::deserialize(&mut &buf[..len]) {
                        Ok(p) => p,
                        Err(_) => continue, // short or malformed datagram
                    };
                    worker.work(payload.work_iterations, payload.randomness);
                    Payload::set_class_tagged_on_wire(&mut buf[..len], HINT_CLASS_IGNORED);
                    socket.send_to(&buf[..len], remote_addr).unwrap();
                }
            })
        })
        .collect();

    for j in join_handles {
        j.join().unwrap();
    }
}

/// Serves one TCP connection. With hints applied, each request's hints are
/// set on the connection's thread, so they take effect from the next time the
/// thread wakes up: on TCP the class is effectively per connection.
fn socket_worker(socket: &mut Connection, worker: Arc<FakeWorker>, hints: ServerHints) {
    let mut v = vec![0; PAYLOAD_SIZE];
    let mut r = || {
        socket.read_exact(&mut v[..PAYLOAD_SIZE])?;
        let mut payload = Payload::deserialize(&mut &v[..PAYLOAD_SIZE])?;
        v.clear();
        // The thread was woken for this request under the hints set while
        // handling the previous one, so report those, then tag the thread for
        // its next wakeup with this request's kind.
        let class = match &hints {
            ServerHints::Ignore => HINT_CLASS_IGNORED,
            ServerHints::Apply(map) => {
                let class = thread::self_class();
                let _ = thread::set_self_hints(&map.get(payload.kind()));
                class
            }
        };
        worker.work(payload.work_iterations, payload.randomness);
        payload.set_class_tagged(class);
        payload.randomness = shenango::rdtsc();
        payload.serialize_into(&mut v)?;
        Ok(socket.write_all(&v[..])?)
    };
    loop {
        if let Err(e) = r() as io::Result<()> {
            match e.raw_os_error() {
                Some(-104) | Some(104) => break,
                _ => {}
            }
            if e.kind() != ErrorKind::UnexpectedEof {
                println!("Receive thread: {}", e);
            }
            break;
        }
    }
}

pub fn run_tcp_server(config: AppConfig) {
    let backend = config.backend;
    let addr = config.addrs[0];
    let worker = config.fakeworker();
    let hints = ServerHints::from_config(&config);
    if let ServerHints::Apply(map) = &hints {
        // on TCP a hint set while handling one request applies to the next
        // wakeup, so a relative deadline would be measured from the wrong
        // request; only classes and service times are meaningful
        if map.has_deadlines() {
            eprintln!("--hintmap deadlines are not supported with the TCP server; use UDP");
            std::process::exit(1);
        }
    }
    let tcpq = backend.create_tcp_listener(addr).unwrap();
    println!("Bound to address {}", addr);
    println!("{}", hints.describe());
    loop {
        match tcpq.accept() {
            Ok(mut c) => {
                let worker = worker.clone();
                let hints = hints.clone();
                backend.spawn_thread(move || socket_worker(&mut c, worker, hints));
            }
            Err(e) => {
                println!("Listener: {}", e);
            }
        }
    }
}

/// Whether the UDP spawner ignores hints (replies report HINT_CLASS_IGNORED).
static SPAWNER_IGNORE_HINTS: AtomicBool = AtomicBool::new(false);

/// Runs in the runtime's packet-processing thread before the handler thread
/// is queued: reads the request kind from the datagram and fills in the hints
/// the server's map (`arg`) assigns to it. Must stay short and must not block.
extern "C" fn classify(
    arg: *mut c_void,
    d: *const shenango::ffi::udp_spawn_data,
    out: *mut shenango::ffi::thread_hints,
) {
    let (map, data) = unsafe {
        (
            &*(arg as *const HintMap),
            slice::from_raw_parts((*d).buf as *const u8, (*d).len as usize),
        )
    };
    if let Some(kind) = Payload::kind_from_wire(data) {
        let h = map.get(kind);
        if h != thread::Hints::default() {
            unsafe { h.write_to(out) };
        }
    }
}

pub fn run_spawner_server(addr: SocketAddrV4, workerspec: &str, hints: ServerHints) {
    static mut SPAWNER_WORKER: Option<FakeWorker> = None;
    unsafe {
        SPAWNER_WORKER = Some(FakeWorker::create(workerspec).unwrap());
    }
    extern "C" fn echo(d: *mut shenango::ffi::udp_spawn_data) {
        let start_tsc = shenango::rdtsc();
        let (enqueue_tsc, enqueue_k, run_k) = thread::self_sched_info();
        unsafe {
            let buf = slice::from_raw_parts((*d).buf as *mut u8, (*d).len as usize);
            // never panic on wire input (a panic here would abort the server)
            let mut payload = match Payload::deserialize(&mut &buf[..]) {
                Ok(p) => p,
                Err(_) => {
                    UdpSpawner::release_data(d);
                    return;
                }
            };
            #[allow(static_mut_refs)]
            let worker = SPAWNER_WORKER.as_ref().unwrap();
            let class = if SPAWNER_IGNORE_HINTS.load(Ordering::Relaxed) {
                HINT_CLASS_IGNORED
            } else {
                thread::self_class()
            };
            worker.work(payload.work_iterations, payload.randomness);
            payload.randomness = shenango::rdtsc();
            payload.set_stamps(Stamps {
                enqueue_tsc,
                start_tsc,
                enqueue_kthread: enqueue_k as u8,
                run_kthread: run_k as u8,
            });
            payload.set_class_tagged(class);
            let mut array = ArrayVec::<_, PAYLOAD_SIZE>::new();
            payload.serialize_into(&mut array).unwrap();
            let _ = UdpSpawner::reply(d, array.as_slice());
            UdpSpawner::release_data(d);
        }
    }

    println!("{}", hints.describe());
    let _s = unsafe {
        match hints {
            ServerHints::Ignore => {
                SPAWNER_IGNORE_HINTS.store(true, Ordering::Relaxed);
                UdpSpawner::new(addr, echo).unwrap()
            }
            ServerHints::Apply(map) if map.is_empty() => UdpSpawner::new(addr, echo).unwrap(),
            ServerHints::Apply(map) => {
                // the map lives as long as the server (it never exits)
                let arg = Box::into_raw(Box::new((*map).clone())) as *mut c_void;
                UdpSpawner::new_classified(addr, echo, classify, arg).unwrap()
            }
        }
    };

    let wg = shenango::WaitGroup::new();
    wg.add(1);
    wg.wait();
}
