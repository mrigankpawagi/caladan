# w2b-hol-class, session noise-b

Head-of-line blocking, hinted by class only

Median of 3 repeats per cell. *wait* = mean latency minus the kind's minimum latency; *pred* = predicted mean wait (see analyze.py). *p99 spread* = (max - min) / median of p99 across repeats.

## 140800 req/s (rho = 0.50)

| short | wait | pred | mean | p50 | p99 | p99.9 | p99 spread |
|---|---|---|---|---|---|---|---|
| fifo | 3.7 | 1.6 | 9.7 | 8 | 38 | 62 | 3% |

| long | wait | pred | mean | p50 | p99 | p99.9 | p99 spread |
|---|---|---|---|---|---|---|---|
| fifo | 3.4 | 1.6 | 52.4 | 51 | 81 | 113 | 2% |

| all | wait | pred | mean | p50 | p99 | p99.9 | p99 spread |
|---|---|---|---|---|---|---|---|
| fifo | - | - | 18.2 | 9 | 61 | 92 | 2% |

## 197200 req/s (rho = 0.70)

| short | wait | pred | mean | p50 | p99 | p99.9 | p99 spread |
|---|---|---|---|---|---|---|---|
| fifo | 8.0 | 6.6 | 14.0 | 9 | 70 | 121 | 1% |

| long | wait | pred | mean | p50 | p99 | p99.9 | p99 spread |
|---|---|---|---|---|---|---|---|
| fifo | 7.7 | 6.6 | 56.7 | 51 | 113 | 175 | 1% |

| all | wait | pred | mean | p50 | p99 | p99.9 | p99 spread |
|---|---|---|---|---|---|---|---|
| fifo | - | - | 22.5 | 9 | 91 | 139 | 0% |

## 225400 req/s (rho = 0.80)

| short | wait | pred | mean | p50 | p99 | p99.9 | p99 spread |
|---|---|---|---|---|---|---|---|
| fifo | 13.9 | 13.8 | 19.9 | 10 | 107 | 180 | 7% |

| long | wait | pred | mean | p50 | p99 | p99.9 | p99 spread |
|---|---|---|---|---|---|---|---|
| fifo | 13.5 | 13.8 | 62.5 | 53 | 149 | 237 | 5% |

| all | wait | pred | mean | p50 | p99 | p99.9 | p99 spread |
|---|---|---|---|---|---|---|---|
| fifo | - | - | 28.4 | 13 | 122 | 197 | 6% |

## 253500 req/s (rho = 0.90)

| short | wait | pred | mean | p50 | p99 | p99.9 | p99 spread |
|---|---|---|---|---|---|---|---|
| fifo | 29.1 | 36.5 | 35.1 | 18 | 197 | 324 | 7% |

| long | wait | pred | mean | p50 | p99 | p99.9 | p99 spread |
|---|---|---|---|---|---|---|---|
| fifo | 28.6 | 36.5 | 77.6 | 60 | 241 | 370 | 4% |

| all | wait | pred | mean | p50 | p99 | p99.9 | p99 spread |
|---|---|---|---|---|---|---|---|
| fifo | - | - | 43.6 | 29 | 209 | 336 | 6% |

