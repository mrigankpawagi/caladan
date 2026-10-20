use rand::Rng;
use rand_distr::{Distribution as DistR, Exp};
use serde::{Deserialize, Serialize};

#[derive(Copy, Clone, Debug, Serialize, Deserialize)]
pub enum Distribution {
    Zero,
    Constant(u64),
    Exponential(f64),
    Bimodal(f64, u64, u64),
}

impl Distribution {
    pub fn name(&self) -> &'static str {
        match *self {
            Distribution::Zero => "zero",
            Distribution::Constant(_) => "constant",
            Distribution::Exponential(_) => "exponential",
            Distribution::Bimodal(_, _, _) => "bimodal",
        }
    }
    pub fn sample<R: Rng>(&self, rng: &mut R) -> u64 {
        match *self {
            Distribution::Zero => 0,
            Distribution::Constant(m) => m,
            Distribution::Exponential(m) => Exp::new(1.0 / m).unwrap().sample(rng) as u64,
            Distribution::Bimodal(p, v1, v2) => {
                if rng.gen_bool(p) {
                    v1
                } else {
                    v2
                }
            }
        }
    }

    pub fn create(spec: &str) -> Result<Self, &str> {
        let tokens: Vec<&str> = spec.split(":").collect();
        assert!(tokens.len() > 0);
        match tokens[0] {
            "zero" => Ok(Distribution::Zero),
            "constant" => {
                assert!(tokens.len() == 2);
                let val: u64 = tokens[1].parse().unwrap();
                Ok(Distribution::Constant(val))
            }
            "exponential" => {
                assert!(tokens.len() == 2);
                let val: f64 = tokens[1].parse().unwrap();
                Ok(Distribution::Exponential(val))
            }
            "bimodal" => {
                assert!(tokens.len() == 4);
                let prob: f64 = tokens[1].parse().unwrap();
                let val1: u64 = tokens[2].parse().unwrap();
                let val2: u64 = tokens[3].parse().unwrap();
                Ok(Distribution::Bimodal(prob, val1, val2))
            }
            _ => Err("bad distribution spec"),
        }
    }
}

/// Bursty arrivals. Every `period_ns`, the first `duty` fraction of the period
/// runs at `factor` times the arrival rate of the rest, keeping the same
/// average rate. All client connections share the phase (it depends only on
/// time since the schedule start), so bursts hit the server together.
#[derive(Copy, Clone, Debug, Serialize, Deserialize)]
pub struct Burst {
    pub period_ns: u64,
    pub duty: f64,
    pub factor: f64,
}

impl Burst {
    /// Parses "period_us:duty:factor", e.g. "1000:0.2:4".
    pub fn parse(spec: &str) -> Result<Self, String> {
        let f: Vec<&str> = spec.split(':').collect();
        if f.len() != 3 {
            return Err(format!("bad burst spec '{}' (period_us:duty:factor)", spec));
        }
        let period_us: u64 = f[0].parse().map_err(|_| "bad burst period".to_string())?;
        let duty: f64 = f[1].parse().map_err(|_| "bad burst duty".to_string())?;
        let factor: f64 = f[2].parse().map_err(|_| "bad burst factor".to_string())?;
        if period_us < 10 || !(duty > 0.0 && duty < 1.0) || !(factor >= 1.0) {
            return Err("burst needs period_us >= 10, 0 < duty < 1, factor >= 1".to_string());
        }
        Ok(Burst { period_ns: period_us * 1000, duty, factor })
    }

    /// The next arrival time after `t_ns`, given an exponential gap `gap_ns`
    /// drawn at the average rate. The gap is spent at each phase's rate in
    /// turn, carrying over phase boundaries (exact time rescaling of a
    /// piecewise-constant rate), so the long-run average rate is preserved.
    pub fn advance(&self, t_ns: u64, gap_ns: u64) -> u64 {
        let norm = self.duty * self.factor + (1.0 - self.duty);
        let (m_on, m_off) = (self.factor / norm, 1.0 / norm);
        let on_len = ((self.duty * self.period_ns as f64) as u64).max(1);
        let mut t = t_ns;
        let mut budget = gap_ns as f64;
        loop {
            let pos = t % self.period_ns;
            let (m, remaining) = if pos < on_len {
                (m_on, on_len - pos)
            } else {
                (m_off, self.period_ns - pos)
            };
            let cap = remaining as f64 * m;
            if budget <= cap {
                return t + (budget / m) as u64;
            }
            budget -= cap;
            t += remaining;
        }
    }
}

/// One kind of request in a mix: a name, a service-time distribution (in
/// work iterations), a relative weight, and an optional client-side deadline
/// (microseconds, 0 = none) used only for reporting.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct KindSpec {
    pub name: String,
    pub dist: Distribution,
    pub weight: f64,
    pub deadline_us: u64,
}

/// A weighted mix of request kinds. Each generated request first draws a
/// kind, then its work amount from that kind's distribution. The kind's index
/// is sent to the server, which maps it to a scheduling hint.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct KindMix {
    pub kinds: Vec<KindSpec>,
    cdf: Vec<f64>,
}

impl KindMix {
    pub fn new(kinds: Vec<KindSpec>) -> Result<Self, String> {
        if kinds.is_empty() || kinds.len() > 255 {
            return Err("a kind mix needs between 1 and 255 kinds".to_string());
        }
        let total: f64 = kinds.iter().map(|k| k.weight).sum();
        if !(total > 0.0) {
            return Err("kind weights must sum to a positive number".to_string());
        }
        let mut acc = 0.0;
        let cdf = kinds
            .iter()
            .map(|k| {
                acc += k.weight / total;
                acc
            })
            .collect();
        Ok(KindMix { kinds, cdf })
    }

    /// A mix with a single kind, equivalent to the old single-distribution mode.
    pub fn from_distribution(dist: Distribution) -> Self {
        KindMix::new(vec![KindSpec {
            name: "default".to_string(),
            dist,
            weight: 1.0,
            deadline_us: 0,
        }])
        .unwrap()
    }

    /// Parses "name/distspec/weight[/deadline_us],..." e.g.
    /// "short/constant:170/0.2/60,long/exponential:1700/0.8".
    pub fn parse(spec: &str) -> Result<Self, String> {
        let mut kinds = Vec::new();
        for item in spec.split(',') {
            let f: Vec<&str> = item.split('/').collect();
            if f.len() < 3 || f.len() > 4 {
                return Err(format!("bad kind spec '{}'", item));
            }
            let dist = Distribution::create(f[1]).map_err(|e| e.to_string())?;
            let weight: f64 = f[2]
                .parse()
                .map_err(|_| format!("bad weight in '{}'", item))?;
            let deadline_us: u64 = if f.len() == 4 {
                f[3]
                    .parse()
                    .map_err(|_| format!("bad deadline in '{}'", item))?
            } else {
                0
            };
            kinds.push(KindSpec {
                name: f[0].to_string(),
                dist,
                weight,
                deadline_us,
            });
        }
        KindMix::new(kinds)
    }

    /// Draws a kind and a work amount; returns (kind index, work iterations).
    pub fn sample<R: Rng>(&self, rng: &mut R) -> (u8, u64) {
        let u: f64 = rng.gen();
        let idx = self.cdf.iter().position(|c| u < *c).unwrap_or(self.kinds.len() - 1);
        (idx as u8, self.kinds[idx].dist.sample(rng))
    }

    /// Name used in result rows: the distribution name for a single kind,
    /// "mix" otherwise.
    pub fn name(&self) -> &'static str {
        if self.kinds.len() == 1 {
            self.kinds[0].dist.name()
        } else {
            "mix"
        }
    }
}
