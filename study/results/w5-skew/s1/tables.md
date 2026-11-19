# w5-skew, session s1

W2b over 4 connections: uneven arrivals across 4 cores

Median of 3 repeats per cell. *wait* = mean latency minus the kind's minimum latency; *pred* = predicted mean wait with the cores pooled into one queue, *pred/core* = with each core its own queue and no stealing (see analyze.py). *p99 spread* = (max - min) / median of p99 across repeats.

## 140800 req/s (rho = 0.50)

| short | wait | pred | pred/core | mean | p50 | p99 | p99.9 | p99 spread |
|---|---|---|---|---|---|---|---|---|
| fifo | 3.7 | 1.6 | 18.5 | 9.7 | 8 | 38 | 62 | 3% |
| prio | 3.5 | 0.9 | 10.8 | 9.5 | 8 | 35 | 53 | 3% |
| prio+steal | 3.5 | 0.9 | 10.8 | 9.5 | 8 | 35 | 53 | 0% |

| long | wait | pred | pred/core | mean | p50 | p99 | p99.9 | p99 spread |
|---|---|---|---|---|---|---|---|---|
| fifo | 3.3 | 1.6 | 18.5 | 52.3 | 51 | 82 | 112 | 1% |
| prio | 3.4 | 1.9 | 21.7 | 52.4 | 51 | 84 | 115 | 1% |
| prio+steal | 3.4 | 1.9 | 21.7 | 52.4 | 51 | 83 | 117 | 1% |

| all | wait | pred | pred/core | mean | p50 | p99 | p99.9 | p99 spread |
|---|---|---|---|---|---|---|---|---|
| fifo | - | - | - | 18.2 | 9 | 61 | 92 | 0% |
| prio | - | - | - | 18.1 | 9 | 61 | 93 | 0% |
| prio+steal | - | - | - | 18.1 | 8 | 61 | 93 | 2% |

## 197200 req/s (rho = 0.70)

| short | wait | pred | pred/core | mean | p50 | p99 | p99.9 | p99 spread |
|---|---|---|---|---|---|---|---|---|
| fifo | 7.9 | 6.6 | 43.2 | 13.9 | 9 | 70 | 117 | 3% |
| prio | 6.8 | 2.5 | 16.3 | 12.8 | 9 | 53 | 72 | 0% |
| prio+steal | 6.8 | 2.5 | 16.3 | 12.8 | 9 | 53 | 72 | 0% |

| long | wait | pred | pred/core | mean | p50 | p99 | p99.9 | p99 spread |
|---|---|---|---|---|---|---|---|---|
| fifo | 7.6 | 6.6 | 43.2 | 56.6 | 51 | 113 | 176 | 2% |
| prio | 8.2 | 8.3 | 54.3 | 57.2 | 51 | 121 | 196 | 2% |
| prio+steal | 8.2 | 8.3 | 54.3 | 57.2 | 51 | 120 | 188 | 1% |

| all | wait | pred | pred/core | mean | p50 | p99 | p99.9 | p99 spread |
|---|---|---|---|---|---|---|---|---|
| fifo | - | - | - | 22.4 | 9 | 91 | 137 | 2% |
| prio | - | - | - | 21.7 | 9 | 88 | 141 | 0% |
| prio+steal | - | - | - | 21.7 | 9 | 89 | 142 | 1% |

## 225400 req/s (rho = 0.80)

| short | wait | pred | pred/core | mean | p50 | p99 | p99.9 | p99 spread |
|---|---|---|---|---|---|---|---|---|
| fifo | 13.8 | 13.8 | 74.0 | 19.8 | 10 | 106 | 179 | 2% |
| prio | 10.9 | 3.6 | 19.3 | 16.9 | 10 | 65 | 92 | 2% |
| prio+steal | 10.5 | 3.6 | 19.3 | 16.5 | 10 | 63 | 86 | 2% |

| long | wait | pred | pred/core | mean | p50 | p99 | p99.9 | p99 spread |
|---|---|---|---|---|---|---|---|---|
| fifo | 13.5 | 13.8 | 74.0 | 62.5 | 53 | 150 | 249 | 3% |
| prio | 15.2 | 18.0 | 96.7 | 64.2 | 53 | 172 | 296 | 4% |
| prio+steal | 14.8 | 18.0 | 96.7 | 63.8 | 53 | 168 | 267 | 3% |

| all | wait | pred | pred/core | mean | p50 | p99 | p99.9 | p99 spread |
|---|---|---|---|---|---|---|---|---|
| fifo | - | - | - | 28.3 | 13 | 122 | 198 | 2% |
| prio | - | - | - | 26.4 | 13 | 113 | 206 | 2% |
| prio+steal | - | - | - | 25.9 | 13 | 111 | 202 | 3% |

## 253500 req/s (rho = 0.90)

| short | wait | pred | pred/core | mean | p50 | p99 | p99.9 | p99 spread |
|---|---|---|---|---|---|---|---|---|
| fifo | 29.7 | 36.5 | 166.6 | 35.7 | 18 | 207 | 353 | 2% |
| prio | 18.3 | 5.0 | 22.6 | 24.3 | 17 | 80 | 102 | 0% |
| prio+steal | 18.1 | 5.0 | 22.6 | 24.1 | 17 | 77 | 98 | 0% |

| long | wait | pred | pred/core | mean | p50 | p99 | p99.9 | p99 spread |
|---|---|---|---|---|---|---|---|---|
| fifo | 29.5 | 36.5 | 166.6 | 78.5 | 60 | 251 | 406 | 4% |
| prio | 34.3 | 49.5 | 226.2 | 83.3 | 62 | 300 | 468 | 9% |
| prio+steal | 34.7 | 49.5 | 226.2 | 83.7 | 62 | 306 | 522 | 5% |

| all | wait | pred | pred/core | mean | p50 | p99 | p99.9 | p99 spread |
|---|---|---|---|---|---|---|---|---|
| fifo | - | - | - | 44.2 | 29 | 219 | 367 | 2% |
| prio | - | - | - | 36.1 | 25 | 186 | 354 | 4% |
| prio+steal | - | - | - | 36.1 | 25 | 189 | 365 | 4% |

