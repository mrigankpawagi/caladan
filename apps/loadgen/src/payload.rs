use crate::Buffer;
use crate::Connection;
use crate::LoadgenProtocol;
use crate::Packet;
use crate::Transport;

use byteorder::{BigEndian, ReadBytesExt, WriteBytesExt};
use serde::{Deserialize, Serialize};
use std::io;
use std::io::Read;

/// Synthetic request/response payload.
///
/// `hint` is a packed word used to carry scheduling-hint information between
/// client and server:
///   bits 0..8   request kind, chosen by the client (index into the server's
///               hint map; 0 = default kind)
///   bits 8..16  priority class the server actually applied to the handler
///               thread, filled in by the server on the reply
///               (`HINT_CLASS_IGNORED` if the server ignores hints)
///   bits 16..64 reserved (zero)
pub struct Payload {
    pub work_iterations: u64,
    pub index: u64,
    pub randomness: u64,
    pub hint: u64,
}

pub const PAYLOAD_SIZE: usize = 32;

/// Value of the applied-class field when the server did not apply any hint.
pub const HINT_CLASS_IGNORED: u8 = 0xff;

const HINT_KIND_SHIFT: u64 = 0;
const HINT_CLASS_SHIFT: u64 = 8;
/// Byte offset of the hint word in a serialized payload.
const HINT_OFFSET: usize = 24;

#[derive(Clone, Copy, Serialize, Deserialize)]
pub struct SyntheticProtocol {}

impl LoadgenProtocol for SyntheticProtocol {
    fn uses_ordered_requests(&self) -> bool {
        false
    }

    fn gen_req(&self, i: usize, p: &Packet, buf: &mut Vec<u8>) {
        Payload {
            work_iterations: p.work_iterations,
            index: i as u64,
            randomness: p.randomness,
            hint: Payload::hint_for_kind(p.kind),
        }
        .serialize_into(buf)
        .unwrap();
    }

    fn read_response(
        &self,
        mut sock: &Connection,
        buf: &mut Buffer,
    ) -> io::Result<(usize, u64, u8)> {
        let scratch = buf.get_empty_buf();
        sock.read_exact(&mut scratch[..PAYLOAD_SIZE])?;
        let payload = Payload::deserialize(&mut &scratch[..])?;
        Ok((
            payload.index as usize,
            payload.randomness,
            payload.class_applied(),
        ))
    }
}

impl SyntheticProtocol {
    pub fn with_args(_matches: &clap::ArgMatches, _tport: Transport) -> Self {
        SyntheticProtocol {}
    }

    pub fn args() -> Vec<clap::Arg> {
        vec![]
    }
}

impl Payload {
    /// Builds the hint word a client sends for request kind `kind`.
    pub fn hint_for_kind(kind: u8) -> u64 {
        (kind as u64) << HINT_KIND_SHIFT
    }

    /// The request kind chosen by the client.
    pub fn kind(&self) -> u8 {
        (self.hint >> HINT_KIND_SHIFT) as u8
    }

    /// The priority class the server reported applying (see `HINT_CLASS_IGNORED`).
    pub fn class_applied(&self) -> u8 {
        (self.hint >> HINT_CLASS_SHIFT) as u8
    }

    /// Records, on the server, which class was applied to the handler thread.
    pub fn set_class_applied(&mut self, class: u8) {
        self.hint &= !(0xffu64 << HINT_CLASS_SHIFT);
        self.hint |= (class as u64) << HINT_CLASS_SHIFT;
    }

    /// Reads the request kind straight from a serialized payload, without
    /// decoding the rest (used by the UDP classifier, which must be cheap).
    pub fn kind_from_wire(buf: &[u8]) -> Option<u8> {
        let w: [u8; 8] = buf.get(HINT_OFFSET..HINT_OFFSET + 8)?.try_into().ok()?;
        Some((u64::from_be_bytes(w) >> HINT_KIND_SHIFT) as u8)
    }

    /// Sets the applied-class field directly in a serialized payload.
    pub fn set_class_applied_on_wire(buf: &mut [u8], class: u8) {
        if let Some(w) = buf.get_mut(HINT_OFFSET..HINT_OFFSET + 8) {
            let mut h = u64::from_be_bytes((&*w).try_into().unwrap());
            h &= !(0xffu64 << HINT_CLASS_SHIFT);
            h |= (class as u64) << HINT_CLASS_SHIFT;
            w.copy_from_slice(&h.to_be_bytes());
        }
    }

    pub fn serialize_into<W: io::Write>(&self, writer: &mut W) -> io::Result<()> {
        writer.write_u64::<BigEndian>(self.work_iterations)?;
        writer.write_u64::<BigEndian>(self.index)?;
        writer.write_u64::<BigEndian>(self.randomness)?;
        writer.write_u64::<BigEndian>(self.hint)?;
        Ok(())
    }

    pub fn deserialize<R: io::Read>(reader: &mut R) -> io::Result<Payload> {
        let p = Payload {
            work_iterations: reader.read_u64::<BigEndian>()?,
            index: reader.read_u64::<BigEndian>()?,
            randomness: reader.read_u64::<BigEndian>()?,
            hint: reader.read_u64::<BigEndian>()?,
        };
        return Ok(p);
    }
}
