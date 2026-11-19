# w2b-hol-class, session noise-a

Head-of-line blocking, hinted by class only

Median of 3 repeats per cell. *wait* = mean latency minus the kind's minimum latency; *pred* = predicted mean wait (see analyze.py). *p99 spread* = (max - min) / median of p99 across repeats.

## 140800 req/s (rho = 0.50)

| short | wait | pred | mean | p50 | p99 | p99.9 | p99 spread |
|---|---|---|---|---|---|---|---|
| fifo | 3.7 | 1.6 | 9.7 | 8 | 38 | 61 | 0% |

| long | wait | pred | mean | p50 | p99 | p99.9 | p99 spread |
|---|---|---|---|---|---|---|---|
| fifo | 3.4 | 1.6 | 52.4 | 51 | 81 | 107 | 2% |

| all | wait | pred | mean | p50 | p99 | p99.9 | p99 spread |
|---|---|---|---|---|---|---|---|
| fifo | - | - | 18.2 | 9 | 61 | 90 | 2% |

## 197200 req/s (rho = 0.70)

| short | wait | pred | mean | p50 | p99 | p99.9 | p99 spread |
|---|---|---|---|---|---|---|---|
| fifo | 8.1 | 6.6 | 14.1 | 9 | 71 | 120 | 1% |

| long | wait | pred | mean | p50 | p99 | p99.9 | p99 spread |
|---|---|---|---|---|---|---|---|
| fifo | 7.8 | 6.6 | 56.8 | 51 | 114 | 172 | 2% |

| all | wait | pred | mean | p50 | p99 | p99.9 | p99 spread |
|---|---|---|---|---|---|---|---|
| fifo | - | - | 22.6 | 9 | 91 | 140 | 1% |

## 225400 req/s (rho = 0.80)

| short | wait | pred | mean | p50 | p99 | p99.9 | p99 spread |
|---|---|---|---|---|---|---|---|
| fifo | 14.0 | 13.8 | 20.0 | 10 | 109 | 190 | 2% |

| long | wait | pred | mean | p50 | p99 | p99.9 | p99 spread |
|---|---|---|---|---|---|---|---|
| fifo | 13.7 | 13.8 | 62.7 | 53 | 152 | 247 | 1% |

| all | wait | pred | mean | p50 | p99 | p99.9 | p99 spread |
|---|---|---|---|---|---|---|---|
| fifo | - | - | 28.6 | 13 | 125 | 206 | 2% |

## 253500 req/s (rho = 0.90)

| short | wait | pred | mean | p50 | p99 | p99.9 | p99 spread |
|---|---|---|---|---|---|---|---|
| fifo | 30.1 | 36.5 | 36.1 | 18 | 204 | 357 | 4% |

| long | wait | pred | mean | p50 | p99 | p99.9 | p99 spread |
|---|---|---|---|---|---|---|---|
| fifo | 29.8 | 36.5 | 78.8 | 61 | 249 | 401 | 4% |

| all | wait | pred | mean | p50 | p99 | p99.9 | p99 spread |
|---|---|---|---|---|---|---|---|
| fifo | - | - | 44.6 | 30 | 217 | 368 | 4% |

