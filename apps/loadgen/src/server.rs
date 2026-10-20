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
use std::sync::{Arc, OnceLock};

use crate::hintmap::HintMap;
use crate::payload::HINT_CLASS_IGNORED;
use crate::Connection;
use crate::FakeWorker;
use crate::Payload;
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
                    let payload = Payload::deserialize(&mut &buf[..len]).unwrap();
                    worker.work(payload.work_iterations, payload.randomness);
                    Payload::set_class_applied_on_wire(&mut buf[..len], HINT_CLASS_IGNORED);
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
        let class = match &hints {
            ServerHints::Ignore => HINT_CLASS_IGNORED,
            ServerHints::Apply(map) => {
                let _ = thread::set_self_hints(&map.get(payload.kind()));
                thread::self_class()
            }
        };
        worker.work(payload.work_iterations, payload.randomness);
        payload.set_class_applied(class);
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

/// Hint map used by the UDP spawner's classifier, set once at startup.
static SPAWNER_HINTS: OnceLock<HintMap> = OnceLock::new();
/// Whether the UDP spawner ignores hints (replies report HINT_CLASS_IGNORED).
static SPAWNER_IGNORE_HINTS: AtomicBool = AtomicBool::new(false);

/// Runs in the runtime's packet-processing thread before the handler thread
/// is queued: reads the request kind from the datagram and fills in the hints
/// the server's map assigns to it. Must stay short and must not block.
extern "C" fn classify(buf: *const c_void, len: usize, out: *mut shenango::ffi::thread_hints) {
    let data = unsafe { slice::from_raw_parts(buf as *const u8, len) };
    if let (Some(kind), Some(map)) = (Payload::kind_from_wire(data), SPAWNER_HINTS.get()) {
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
        unsafe {
            let buf = slice::from_raw_parts((*d).buf as *mut u8, (*d).len as usize);
            let mut payload = Payload::deserialize(&mut &buf[..]).unwrap();
            #[allow(static_mut_refs)]
            let worker = SPAWNER_WORKER.as_ref().unwrap();
            let class = if SPAWNER_IGNORE_HINTS.load(Ordering::Relaxed) {
                HINT_CLASS_IGNORED
            } else {
                thread::self_class()
            };
            worker.work(payload.work_iterations, payload.randomness);
            payload.set_class_applied(class);
            payload.randomness = shenango::rdtsc();
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
                SPAWNER_HINTS.set((*map).clone()).unwrap();
                UdpSpawner::new_classified(addr, echo, classify).unwrap()
            }
        }
    };

    let wg = shenango::WaitGroup::new();
    wg.add(1);
    wg.wait();
}
