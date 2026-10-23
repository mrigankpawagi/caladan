# Generation 0 (loop 2): calibration

Measured in one session each, 3 repeats, full sweeps: fifo on w0 (hint build
with and without per-pick statistics, and the stock build), fifo and prio on
w1. Code 68cf2c1.

- **Headline loads:** w0 350k req/s, w1 400k.
- **Noise with 3 repeats:** ranges are 1–6% of the median at and below the
  headline load (w1 fifo short p99 93 [92–98], prio 52 [52–53]); above the
  headline they widen past 25%. The 5% / non-overlap rule is workable here.
- **w1:** prio cuts the short requests' p99 from 93 to 52 µs (×1.55 → ×0.87 of
  the 60 µs budget) and leaves the long requests within 4% (113 vs 117).
  prio is the champion to beat.
- **Overhead of the hint build (outside the policy region):** on w0, where
  no request carries a hint, the hint build's p99 is 71 µs against stock
  Caladan's 67 at 0.8 load (+6%), and 192 against 163 at 0.93 (+18%; 179 with
  per-pick statistics off). The per-packet classifier call and the policy
  hook cost this; it is not a policy's cost and no policy can remove it.
  Reported to the owner; left as is.
- The counters agree with the client: delivered rate within 0.5% of the
  offered load at every level up to the headline, cores busy 7.98 of 8.

Node time: about 25 minutes including three builds.
