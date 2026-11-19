# w5-cores (cores2), session v2

W2b's traffic on 2, 4 and 6 cores, and on 2 guaranteed + 2 burstable cores next to a batch job

Scored kinds: short (SLO short 100 us). Price: long. 3 repeats; configurations in ladder order.

## SLO-load

Highest rho at which every scored kind's p99 <= its SLO, per repeat (>= means it never crossed within the grid). Compared by the paired rule; when the SLO-load cannot decide because of the grid top, by the worst scored p99/SLO at rho 0.90.

| config | SLO-load (median) | per repeat | worst p99/SLO at top | vs fifo | vs the rung below |
|---|---|---|---|---|---|
| fifo | 0.57 | 0.57, 0.57, 0.58 | 5.77 |  |  |
| prio | >=0.90 | >=0.90, >=0.90, >=0.90 | 0.89 | better on SLO-load (1.58, 1.57, 1.54) | better on SLO-load (1.58, 1.57, 1.54) |
| hinted | >=0.90 | >=0.90, >=0.90, >=0.90 | 0.89 | better on SLO-load (1.58, 1.57, 1.54) |  |
| hinted+rx | >=0.90 | >=0.90, >=0.90, >=0.90 | 0.60 | better on SLO-load (1.58, 1.57, 1.54) | better on p99/SLO at top load (0.67, 0.67, 0.67) |

## rho = 0.80

p99 per kind (median of repeats), its ratio to the SLO, mean wait (mean minus min latency) and the predicted mean wait (pooled / per core).

| config | short p99 | short wait (pred) | long p99 | long wait (pred) |
|---|---|---|---|---|
| fifo | 256 (2.56) | 40.5 (13.8/74) | 294 (0.53) | 40.1 (13.8/74) |
| prio | 79 (0.79) | 21.4 (3.6/19) | 370 (0.67) | 47.9 (18.0/97) |
| hinted | 79 (0.79) | 21.4 (3.6/19) | 372 (0.68) | 48.4 (18.0/97) |
| hinted+rx | 58 (0.58) | 16.9 (3.6/19) | 382 (0.69) | 50.8 (18.0/97) |

Price at rho 0.80: unscored kinds' p99 against fifo (paired).

- prio, long: higher (1.26, 1.33, 1.19)
- hinted, long: higher (1.27, 1.32, 1.20)
- hinted+rx, long: higher (1.36, 1.35, 1.21)

## rho = 0.85

p99 per kind (median of repeats), its ratio to the SLO, mean wait (mean minus min latency) and the predicted mean wait (pooled / per core).

| config | short p99 | short wait (pred) | long p99 | long wait (pred) |
|---|---|---|---|---|
| fifo | 365 (3.65) | 60.9 (21.3/105) | 410 (0.75) | 61.1 (21.3/105) |
| prio | 84 (0.84) | 26.2 (4.3/21) | 521 (0.95) | 74.7 (28.4/140) |
| hinted | 84 (0.84) | 26.2 (4.3/21) | 532 (0.97) | 75.1 (28.4/140) |
| hinted+rx | 59 (0.59) | 19.5 (4.3/21) | 529 (0.96) | 78.2 (28.4/140) |

Price at rho 0.85: unscored kinds' p99 against fifo (paired).

- prio, long: higher (1.24, 1.34, 1.30)
- hinted, long: higher (1.32, 1.36, 1.28)
- hinted+rx, long: higher (1.24, 1.36, 1.32)

## rho = 0.90

p99 per kind (median of repeats), its ratio to the SLO, mean wait (mean minus min latency) and the predicted mean wait (pooled / per core).

| config | short p99 | short wait (pred) | long p99 | long wait (pred) |
|---|---|---|---|---|
| fifo | 577 (5.77) | 105.5 (36.5/167) | 623 (1.13) | 104.5 (36.5/167) |
| prio | 89 (0.89) | 33.4 (5.0/23) | 909 (1.65) | 145.9 (49.6/227) |
| hinted | 89 (0.89) | 33.1 (5.0/23) | 922 (1.68) | 140.1 (49.6/227) |
| hinted+rx | 60 (0.60) | 22.8 (5.0/23) | 907 (1.65) | 150.4 (49.6/227) |

Price at rho 0.90: unscored kinds' p99 against fifo (paired).

- prio, long: higher (1.44, 1.35, 1.50)
- hinted, long: higher (1.41, 1.44, 1.48)
- hinted+rx, long: higher (1.68, 1.35, 1.34)

## Where the time goes at rho = 0.90 (us; mean over repeats)

lag = client send minus schedule; in = send to server enqueue (delivery and RX-queue wait, plus classification); rq = runqueue; svc = handler; out = reply path; thread stolen = the handler ran on another kthread than the one that queued it; packet stolen = the packet was processed by another kthread than the owner of its RX queue.

| config | kind | part | lag | in | rq | svc | out | thread stolen % | packet stolen % |
|---|---|---|---|---|---|---|---|---|---|
| fifo | short | mean | -4.4 | 24.1 | 81.1 | 5.1 | 1.6 | 9 | 10 |
| fifo | short | tail99 | -4.4 | 39.8 | 689.6 | 5.1 | 1.7 | 13 | 0 |
| fifo | long | mean | -4.4 | 24.1 | 80.7 | 50.2 | 1.7 | 9 | 10 |
| fifo | long | tail99 | -4.4 | 40.2 | 687.1 | 53.4 | 1.7 | 11 | 0 |
| prio | short | mean | -4.4 | 26.1 | 7.2 | 5.1 | 1.6 | 3 | 11 |
| prio | short | tail99 | -4.4 | 82.3 | 8.4 | 5.7 | 1.9 | 1 | 0 |
| prio | long | mean | -4.4 | 26.1 | 120.7 | 50.2 | 1.6 | 12 | 11 |
| prio | long | tail99 | -4.4 | 37.0 | 1022.7 | 52.1 | 1.6 | 13 | 0 |
| hinted | short | mean | -4.4 | 25.7 | 7.1 | 5.1 | 1.6 | 3 | 11 |
| hinted | short | tail99 | -4.4 | 82.2 | 8.7 | 5.8 | 2.0 | 1 | 0 |
| hinted | long | mean | -4.4 | 25.8 | 117.1 | 50.2 | 1.7 | 12 | 11 |
| hinted | long | tail99 | -4.4 | 36.5 | 1068.9 | 52.4 | 1.7 | 12 | 0 |
| hinted+rx | short | mean | -4.4 | 16.4 | 6.3 | 5.1 | 1.6 | 3 | 9 |
| hinted+rx | short | tail99 | -4.3 | 44.4 | 15.2 | 5.7 | 2.0 | 2 | 0 |
| hinted+rx | long | mean | -4.4 | 16.4 | 139.4 | 50.2 | 1.7 | 13 | 9 |
| hinted+rx | long | tail99 | -4.4 | 19.9 | 1047.0 | 52.3 | 1.7 | 10 | 0 |

## Mean-wait check (pre-registered)

dwait = growth of the kind's mean latency over rho 0.50, net of the change in its handler time, paired by repeat; predicted = pred(rho) - pred(0.50) pooled / per core.

| config | rho | short dwait meas (pooled / per core) ok | long dwait meas (pooled / per core) ok |
|---|---|---|---|
| fifo | 0.80 | 32.2 (12.2 / 56) NO | 31.7 (12.2 / 56) NO |
| fifo | 0.85 | 52.6 (19.7 / 86) NO | 52.7 (19.7 / 86) NO |
| fifo | 0.90 | 97.5 (34.9 / 148) NO | 97.3 (34.9 / 148) NO |
| prio | 0.80 | 14.5 (2.7 / 9) NO | 38.6 (16.2 / 75) yes |
| prio | 0.85 | 19.4 (3.3 / 10) NO | 65.6 (26.5 / 118) yes |
| prio | 0.90 | 26.5 (4.0 / 12) NO | 136.6 (47.7 / 205) yes |
| hinted | 0.80 | 14.4 (2.7 / 9) NO | 39.2 (16.2 / 75) yes |
| hinted | 0.85 | 19.2 (3.3 / 10) NO | 65.7 (26.5 / 118) yes |
| hinted | 0.90 | 26.1 (4.0 / 12) NO | 131.1 (47.7 / 205) yes |
| hinted+rx | 0.80 | 10.2 (2.7 / 9) NO | 41.3 (16.2 / 75) yes |
| hinted+rx | 0.85 | 12.9 (3.3 / 10) NO | 68.9 (26.5 / 118) yes |
| hinted+rx | 0.90 | 16.1 (4.0 / 12) NO | 141.1 (47.7 / 205) yes |

Pre-registered check passes in 6 of 18 cells (policies without +rx).

