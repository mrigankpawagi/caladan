# w5-even, session s1

W2b over 64 connections: the even reference for W5

Median of 3 repeats per cell. *wait* = mean latency minus the kind's minimum latency; *pred* = predicted mean wait with the cores pooled into one queue, *pred/core* = with each core its own queue and no stealing (see analyze.py). *p99 spread* = (max - min) / median of p99 across repeats.

## 140800 req/s (rho = 0.50)

| short | wait | pred | pred/core | mean | p50 | p99 | p99.9 | p99 spread |
|---|---|---|---|---|---|---|---|---|
| fifo | 3.6 | 1.6 | 18.5 | 9.6 | 8 | 38 | 60 | 0% |
| prio | 3.4 | 0.9 | 10.8 | 9.4 | 8 | 34 | 52 | 3% |
| prio+steal | 3.4 | 0.9 | 10.8 | 9.4 | 8 | 35 | 52 | 0% |

| long | wait | pred | pred/core | mean | p50 | p99 | p99.9 | p99 spread |
|---|---|---|---|---|---|---|---|---|
| fifo | 3.3 | 1.6 | 18.5 | 52.3 | 51 | 81 | 109 | 0% |
| prio | 3.3 | 1.9 | 21.7 | 52.3 | 51 | 82 | 112 | 1% |
| prio+steal | 3.3 | 1.9 | 21.7 | 52.3 | 51 | 83 | 111 | 2% |

| all | wait | pred | pred/core | mean | p50 | p99 | p99.9 | p99 spread |
|---|---|---|---|---|---|---|---|---|
| fifo | - | - | - | 18.1 | 9 | 61 | 91 | 0% |
| prio | - | - | - | 18.0 | 9 | 60 | 92 | 0% |
| prio+steal | - | - | - | 18.0 | 8 | 61 | 92 | 2% |

## 197200 req/s (rho = 0.70)

| short | wait | pred | pred/core | mean | p50 | p99 | p99.9 | p99 spread |
|---|---|---|---|---|---|---|---|---|
| fifo | 7.8 | 6.6 | 43.2 | 13.8 | 9 | 69 | 118 | 4% |
| prio | 6.8 | 2.5 | 16.3 | 12.8 | 9 | 53 | 73 | 0% |
| prio+steal | 6.8 | 2.5 | 16.3 | 12.8 | 9 | 53 | 72 | 0% |

| long | wait | pred | pred/core | mean | p50 | p99 | p99.9 | p99 spread |
|---|---|---|---|---|---|---|---|---|
| fifo | 7.5 | 6.6 | 43.2 | 56.5 | 51 | 113 | 166 | 4% |
| prio | 8.1 | 8.3 | 54.3 | 57.1 | 51 | 119 | 191 | 3% |
| prio+steal | 8.2 | 8.3 | 54.3 | 57.2 | 51 | 120 | 193 | 2% |

| all | wait | pred | pred/core | mean | p50 | p99 | p99.9 | p99 spread |
|---|---|---|---|---|---|---|---|---|
| fifo | - | - | - | 22.3 | 9 | 90 | 138 | 3% |
| prio | - | - | - | 21.7 | 9 | 88 | 141 | 1% |
| prio+steal | - | - | - | 21.7 | 9 | 88 | 143 | 1% |

## 225400 req/s (rho = 0.80)

| short | wait | pred | pred/core | mean | p50 | p99 | p99.9 | p99 spread |
|---|---|---|---|---|---|---|---|---|
| fifo | 14.0 | 13.8 | 74.0 | 20.0 | 10 | 110 | 191 | 2% |
| prio | 10.8 | 3.6 | 19.3 | 16.8 | 10 | 65 | 92 | 2% |
| prio+steal | 10.6 | 3.6 | 19.3 | 16.6 | 10 | 63 | 87 | 2% |

| long | wait | pred | pred/core | mean | p50 | p99 | p99.9 | p99 spread |
|---|---|---|---|---|---|---|---|---|
| fifo | 13.7 | 13.8 | 74.0 | 62.7 | 53 | 153 | 249 | 0% |
| prio | 15.0 | 18.0 | 96.7 | 64.0 | 53 | 170 | 288 | 1% |
| prio+steal | 15.0 | 18.0 | 96.7 | 64.0 | 53 | 172 | 304 | 4% |

| all | wait | pred | pred/core | mean | p50 | p99 | p99.9 | p99 spread |
|---|---|---|---|---|---|---|---|---|
| fifo | - | - | - | 28.5 | 13 | 125 | 207 | 1% |
| prio | - | - | - | 26.2 | 13 | 112 | 203 | 2% |
| prio+steal | - | - | - | 26.1 | 13 | 112 | 208 | 4% |

## 253500 req/s (rho = 0.90)

| short | wait | pred | pred/core | mean | p50 | p99 | p99.9 | p99 spread |
|---|---|---|---|---|---|---|---|---|
| fifo | 29.1 | 36.5 | 166.6 | 35.1 | 18 | 196 | 313 | 2% |
| prio | 18.2 | 5.0 | 22.6 | 24.2 | 17 | 80 | 102 | 1% |
| prio+steal | 18.0 | 5.0 | 22.6 | 24.0 | 16 | 77 | 98 | 0% |

| long | wait | pred | pred/core | mean | p50 | p99 | p99.9 | p99 spread |
|---|---|---|---|---|---|---|---|---|
| fifo | 28.6 | 36.5 | 166.6 | 77.6 | 60 | 239 | 361 | 3% |
| prio | 33.9 | 49.5 | 226.2 | 82.9 | 62 | 298 | 503 | 9% |
| prio+steal | 34.3 | 49.5 | 226.2 | 83.3 | 62 | 309 | 498 | 6% |

| all | wait | pred | pred/core | mean | p50 | p99 | p99.9 | p99 spread |
|---|---|---|---|---|---|---|---|---|
| fifo | - | - | - | 43.5 | 29 | 208 | 327 | 2% |
| prio | - | - | - | 35.9 | 25 | 184 | 353 | 8% |
| prio+steal | - | - | - | 35.9 | 25 | 188 | 366 | 3% |

