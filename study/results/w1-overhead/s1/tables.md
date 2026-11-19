# w1-overhead, session s1

Overhead: 1 us requests on 2 cores, pushed to saturation

Median of 3 repeats per cell. *wait* = mean latency minus the kind's minimum latency; *pred* = predicted mean wait with the cores pooled into one queue, *pred/core* = with each core its own queue and no stealing (see analyze.py). *p99 spread* = (max - min) / median of p99 across repeats.

## 400000 req/s

| all | wait | pred | pred/core | mean | p50 | p99 | p99.9 | p99 spread |
|---|---|---|---|---|---|---|---|---|
| stock | 2.2 | - | - | 4.2 | 4 | 7 | 8 | 0% |
| fifo (no hints) | 2.3 | - | - | 4.3 | 4 | 7 | 8 | 0% |
| fifo | 2.4 | - | - | 4.4 | 4 | 7 | 8 | 0% |
| prio | 2.4 | - | - | 4.4 | 4 | 7 | 8 | 0% |
| sjf | 2.4 | - | - | 4.4 | 4 | 7 | 8 | 0% |
| edf | 2.4 | - | - | 4.4 | 4 | 7 | 8 | 0% |

## 800000 req/s

| all | wait | pred | pred/core | mean | p50 | p99 | p99.9 | p99 spread |
|---|---|---|---|---|---|---|---|---|
| stock | 3.1 | - | - | 5.1 | 5 | 9 | 12 | 0% |
| fifo (no hints) | 3.2 | - | - | 5.2 | 5 | 10 | 12 | 0% |
| fifo | 3.4 | - | - | 5.4 | 5 | 10 | 13 | 0% |
| prio | 3.4 | - | - | 5.4 | 5 | 10 | 13 | 0% |
| sjf | 3.4 | - | - | 5.4 | 5 | 10 | 13 | 0% |
| edf | 3.3 | - | - | 5.3 | 5 | 10 | 13 | 0% |

## 1000000 req/s

| all | wait | pred | pred/core | mean | p50 | p99 | p99.9 | p99 spread |
|---|---|---|---|---|---|---|---|---|
| stock | 3.9 | - | - | 5.9 | 6 | 12 | 16 | 0% |
| fifo (no hints) | 4.1 | - | - | 6.1 | 6 | 12 | 16 | 0% |
| fifo | 4.3 | - | - | 6.3 | 6 | 13 | 17 | 0% |
| prio | 4.3 | - | - | 6.3 | 6 | 13 | 18 | 0% |
| sjf | 4.4 | - | - | 6.4 | 6 | 13 | 18 | 0% |
| edf | 4.3 | - | - | 6.3 | 6 | 13 | 18 | 0% |

## 1200000 req/s

| all | wait | pred | pred/core | mean | p50 | p99 | p99.9 | p99 spread |
|---|---|---|---|---|---|---|---|---|
| stock | 5.6 | - | - | 7.6 | 7 | 18 | 25 | 0% |
| fifo (no hints) | 5.8 | - | - | 7.8 | 7 | 18 | 25 | 0% |
| fifo | 6.5 | - | - | 8.5 | 8 | 21 | 29 | 0% |
| prio | 6.7 | - | - | 8.7 | 8 | 22 | 32 | 0% |
| sjf | 6.7 | - | - | 8.7 | 8 | 22 | 32 | 0% |
| edf | 6.7 | - | - | 8.7 | 8 | 22 | 32 | 0% |

## 1300000 req/s

| all | wait | pred | pred/core | mean | p50 | p99 | p99.9 | p99 spread |
|---|---|---|---|---|---|---|---|---|
| stock | 7.4 | - | - | 9.4 | 8 | 24 | 35 | 4% |
| fifo (no hints) | 7.7 | - | - | 9.7 | 9 | 25 | 37 | 4% |
| fifo | 9.5 | - | - | 11.5 | 10 | 33 | 48 | 0% |
| prio | 10.3 | - | - | 12.3 | 10 | 38 | 60 | 3% |
| sjf | 10.7 | - | - | 12.7 | 11 | 41 | 70 | 12% |
| edf | 10.6 | - | - | 12.6 | 11 | 41 | 71 | 5% |

## 1400000 req/s

| all | wait | pred | pred/core | mean | p50 | p99 | p99.9 | p99 spread |
|---|---|---|---|---|---|---|---|---|
| stock | 12.6 | - | - | 14.6 | 12 | 50 | 98 | 8% |
| fifo (no hints) | 14.2 | - | - | 16.2 | 13 | 60 | 136 | 3% |
| fifo | 452.1 | - | - | 3338.0 | 3364 | inf | inf | - |
| prio | 572.1 | - | - | 3519.7 | 3569 | inf | inf | - |
| sjf | 516.7 | - | - | 3540.6 | 3595 | inf | inf | - |
| edf | 531.9 | - | - | 3508.9 | 3556 | inf | inf | - |

## 1500000 req/s

| all | wait | pred | pred/core | mean | p50 | p99 | p99.9 | p99 spread |
|---|---|---|---|---|---|---|---|---|
| stock | 310.2 | - | - | 3283.2 | 3282 | inf | inf | - |
| fifo (no hints) | 337.0 | - | - | 3304.5 | 3303 | inf | inf | - |
| fifo | 519.7 | - | - | 3365.7 | 3433 | inf | inf | - |
| prio | 592.7 | - | - | 3552.2 | 3653 | inf | inf | - |
| sjf | 572.9 | - | - | 3576.2 | 3682 | inf | inf | - |
| edf | 560.5 | - | - | 3543.4 | 3643 | inf | inf | - |

## 1600000 req/s

| all | wait | pred | pred/core | mean | p50 | p99 | p99.9 | p99 spread |
|---|---|---|---|---|---|---|---|---|
| stock | 297.6 | - | - | 3307.5 | 3309 | inf | inf | - |
| fifo (no hints) | 358.1 | - | - | 3331.6 | 3336 | inf | inf | - |
| fifo | 579.3 | - | - | 3392.2 | 3515 | inf | inf | - |
| prio | 598.2 | - | - | 3576.2 | 3744 | inf | inf | - |
| sjf | 601.1 | - | - | 3602.0 | 3776 | inf | inf | - |
| edf | 598.1 | - | - | 3565.1 | 3729 | inf | inf | - |

