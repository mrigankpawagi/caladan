//! Server-side mapping from request kind to scheduling hints.
//!
//! The client only says which kind each request is; the server decides which
//! scheduling hints that kind gets. Spec format:
//!
//!   kind=class[:deadline_us[:service_us]],...
//!
//! where kind is the index of the kind in the client's --kinds list, class is
//! normal, high, or low, deadline_us is relative to when the hint is applied
//! (0 or omitted = none), and service_us is the expected run time (0 or
//! omitted = unknown). Example: "0=high:60:10,1=normal". Kinds not listed run
//! without hints.

use shenango::thread::{Hints, PRIO_HIGH, PRIO_LOW, PRIO_NORMAL};

#[derive(Clone, Debug, Default)]
pub struct HintMap {
    table: Vec<Hints>,
}

impl HintMap {
    pub fn parse(spec: &str) -> Result<Self, String> {
        let mut table: Vec<Hints> = Vec::new();
        for item in spec.split(',').filter(|s| !s.is_empty()) {
            let (kind, rest) = item
                .split_once('=')
                .ok_or_else(|| format!("bad hint map entry '{}'", item))?;
            let kind: usize = kind
                .parse()
                .map_err(|_| format!("bad kind index in '{}'", item))?;
            if kind > 255 {
                return Err(format!("kind index too large in '{}'", item));
            }
            let f: Vec<&str> = rest.split(':').collect();
            if f.len() > 3 {
                return Err(format!("too many fields in '{}'", item));
            }
            let class = match f[0] {
                "normal" => PRIO_NORMAL,
                "high" => PRIO_HIGH,
                "low" => PRIO_LOW,
                c => return Err(format!("unknown class '{}' in '{}'", c, item)),
            };
            let num = |i: usize| -> Result<u64, String> {
                match f.get(i) {
                    Some(v) => v.parse().map_err(|_| format!("bad number in '{}'", item)),
                    None => Ok(0),
                }
            };
            if table.len() <= kind {
                table.resize(kind + 1, Hints::default());
            }
            table[kind] = Hints {
                class,
                deadline_us: num(1)?,
                service_us: num(2)?,
            };
        }
        Ok(HintMap { table })
    }

    /// The hints for request kind `kind` (no hints if the kind is unlisted).
    pub fn get(&self, kind: u8) -> Hints {
        self.table.get(kind as usize).copied().unwrap_or_default()
    }

    pub fn is_empty(&self) -> bool {
        self.table.iter().all(|h| *h == Hints::default())
    }
}
