# w1-overhead, session s2

Overhead: 1 us requests on 2 cores, pushed to saturation

Median of 3 repeats per cell. *wait* = mean latency minus the kind's minimum latency; *pred* = predicted mean wait with the cores pooled into one queue, *pred/core* = with each core its own queue and no stealing (see analyze.py). *p99 spread* = (max - min) / median of p99 across repeats.

## 400000 req/s

| all | wait | pred | pred/core | mean | p50 | p99 | p99.9 | p99 spread |
|---|---|---|---|---|---|---|---|---|
| fifo | 2.3 | - | - | 4.3 | 4 | 7 | 8 | 0% |
| prio | 2.3 | - | - | 4.3 | 4 | 7 | 8 | 0% |
| sjf | 2.3 | - | - | 4.3 | 4 | 7 | 8 | 0% |
| edf | 2.3 | - | - | 4.3 | 4 | 7 | 8 | 0% |
| hinted | 2.3 | - | - | 4.3 | 4 | 7 | 8 | 0% |
| hinted+rx | 2.3 | - | - | 4.3 | 4 | 7 | 8 | 0% |

## 800000 req/s

| all | wait | pred | pred/core | mean | p50 | p99 | p99.9 | p99 spread |
|---|---|---|---|---|---|---|---|---|
| fifo | 3.3 | - | - | 5.3 | 5 | 10 | 13 | 0% |
| prio | 3.3 | - | - | 5.3 | 5 | 10 | 13 | 0% |
| sjf | 3.2 | - | - | 5.2 | 5 | 10 | 13 | 0% |
| edf | 3.3 | - | - | 5.3 | 5 | 10 | 13 | 0% |
| hinted | 3.3 | - | - | 5.3 | 5 | 10 | 13 | 0% |
| hinted+rx | 3.3 | - | - | 5.3 | 5 | 10 | 14 | 0% |

## 1000000 req/s

| all | wait | pred | pred/core | mean | p50 | p99 | p99.9 | p99 spread |
|---|---|---|---|---|---|---|---|---|
| fifo | 4.3 | - | - | 6.3 | 6 | 13 | 17 | 0% |
| prio | 4.2 | - | - | 6.2 | 6 | 13 | 18 | 0% |
| sjf | 4.3 | - | - | 6.3 | 6 | 13 | 18 | 0% |
| edf | 4.3 | - | - | 6.3 | 6 | 13 | 18 | 0% |
| hinted | 4.3 | - | - | 6.3 | 6 | 13 | 18 | 0% |
| hinted+rx | 4.5 | - | - | 6.5 | 6 | 15 | 22 | 0% |

## 1200000 req/s

| all | wait | pred | pred/core | mean | p50 | p99 | p99.9 | p99 spread |
|---|---|---|---|---|---|---|---|---|
| fifo | 6.4 | - | - | 8.4 | 8 | 21 | 30 | 0% |
| prio | 6.6 | - | - | 8.6 | 8 | 22 | 32 | 0% |
| sjf | 6.7 | - | - | 8.7 | 8 | 22 | 32 | 0% |
| edf | 6.7 | - | - | 8.7 | 8 | 22 | 33 | 5% |
| hinted | 6.8 | - | - | 8.8 | 8 | 23 | 35 | 4% |
| hinted+rx | 344.2 | - | - | 3510.6 | 3646 | inf | inf | - |

## 1300000 req/s

| all | wait | pred | pred/core | mean | p50 | p99 | p99.9 | p99 spread |
|---|---|---|---|---|---|---|---|---|
| fifo | 9.6 | - | - | 11.6 | 10 | 34 | 51 | 0% |
| prio | 10.6 | - | - | 12.6 | 10 | 41 | 64 | 5% |
| sjf | 10.9 | - | - | 12.9 | 11 | 44 | 93 | 7% |
| edf | 11.0 | - | - | 13.0 | 11 | 44 | 86 | 5% |
| hinted | 470.3 | - | - | 3649.4 | 3681 | inf | inf | - |
| hinted+rx | 481.2 | - | - | 3670.6 | 3705 | inf | inf | - |

## 1400000 req/s

| all | wait | pred | pred/core | mean | p50 | p99 | p99.9 | p99 spread |
|---|---|---|---|---|---|---|---|---|
| fifo | 461.2 | - | - | 3341.2 | 3367 | inf | inf | - |
| prio | 489.3 | - | - | 3517.5 | 3566 | inf | inf | - |
| sjf | 500.6 | - | - | 3511.5 | 3557 | inf | inf | - |
| edf | 499.7 | - | - | 3534.4 | 3586 | inf | inf | - |
| hinted | 553.3 | - | - | 3681.3 | 3761 | inf | inf | - |
| hinted+rx | 576.0 | - | - | 3705.2 | 3789 | inf | inf | - |

## 1500000 req/s

| all | wait | pred | pred/core | mean | p50 | p99 | p99.9 | p99 spread |
|---|---|---|---|---|---|---|---|---|
| fifo | 525.6 | - | - | 3371.9 | 3439 | inf | inf | - |
| prio | 552.2 | - | - | 3551.8 | 3651 | inf | inf | - |
| sjf | 575.4 | - | - | 3545.5 | 3643 | inf | inf | - |
| edf | 558.2 | - | - | 3571.2 | 3675 | inf | inf | - |
| hinted | 614.2 | - | - | 3709.6 | 3859 | inf | inf | - |
| hinted+rx | 628.2 | - | - | 3731.7 | 3887 | inf | inf | - |

## 1600000 req/s

| all | wait | pred | pred/core | mean | p50 | p99 | p99.9 | p99 spread |
|---|---|---|---|---|---|---|---|---|
| fifo | 548.2 | - | - | 3400.2 | 3522 | inf | inf | - |
| prio | 595.9 | - | - | 3576.9 | 3738 | inf | inf | - |
| sjf | 608.4 | - | - | 3566.4 | 3726 | inf | inf | - |
| edf | 618.9 | - | - | 3595.9 | 3765 | inf | inf | - |
| hinted | 632.5 | - | - | 3729.9 | 3945 | inf | inf | - |
| hinted+rx | 629.2 | - | - | 3750.2 | 3972 | inf | inf | - |

