# w5-cores (cores4), session v2

W2b's traffic on 2, 4 and 6 cores, and on 2 guaranteed + 2 burstable cores next to a batch job

Scored kinds: short (SLO short 100 us). Price: long. 3 repeats; configurations in ladder order.

## SLO-load

Highest rho at which every scored kind's p99 <= its SLO, per repeat (>= means it never crossed within the grid). Compared by the paired rule; when the SLO-load cannot decide because of the grid top, by the worst scored p99/SLO at rho 0.90.

| config | SLO-load (median) | per repeat | worst p99/SLO at top | vs fifo | vs the rung below |
|---|---|---|---|---|---|
| fifo | 0.73 | 0.72, 0.73, 0.73 | 3.60 |  |  |
| prio | >=0.90 | >=0.90, >=0.90, >=0.90 | 0.84 | better on SLO-load (1.24, 1.24, 1.24) | better on SLO-load (1.24, 1.24, 1.24) |
| hinted | >=0.90 | >=0.90, >=0.90, >=0.90 | 0.84 | better on SLO-load (1.24, 1.24, 1.24) |  |
| hinted+rx | >=0.90 | >=0.90, >=0.90, >=0.90 | 0.59 | better on SLO-load (1.24, 1.24, 1.24) | better on p99/SLO at top load (0.70, 0.70, 0.70) |

## rho = 0.80

p99 per kind (median of repeats), its ratio to the SLO, mean wait (mean minus min latency) and the predicted mean wait (pooled / per core).

| config | short p99 | short wait (pred) | long p99 | long wait (pred) |
|---|---|---|---|---|
| fifo | 142 (1.42) | 19.6 (13.8/74) | 188 (0.34) | 19.6 (13.8/74) |
| prio | 70 (0.70) | 13.8 (3.6/19) | 222 (0.40) | 21.8 (18.0/97) |
| hinted | 70 (0.70) | 13.9 (3.6/19) | 221 (0.40) | 22.6 (18.0/97) |
| hinted+rx | 57 (0.57) | 12.2 (3.6/19) | 226 (0.41) | 23.1 (18.0/97) |

Price at rho 0.80: unscored kinds' p99 against fifo (paired).

- prio, long: higher (1.16, 1.18, 1.19)
- hinted, long: higher (1.22, 1.17, 1.17)
- hinted+rx, long: higher (1.20, 1.20, 1.23)

## rho = 0.85

p99 per kind (median of repeats), its ratio to the SLO, mean wait (mean minus min latency) and the predicted mean wait (pooled / per core).

| config | short p99 | short wait (pred) | long p99 | long wait (pred) |
|---|---|---|---|---|
| fifo | 206 (2.06) | 30.1 (21.3/105) | 249 (0.45) | 30.1 (21.3/105) |
| prio | 77 (0.77) | 18.4 (4.3/21) | 294 (0.53) | 34.4 (28.4/140) |
| hinted | 77 (0.77) | 18.3 (4.3/21) | 301 (0.55) | 34.9 (28.4/140) |
| hinted+rx | 58 (0.58) | 15.4 (4.3/21) | 324 (0.59) | 39.0 (28.4/140) |

Price at rho 0.85: unscored kinds' p99 against fifo (paired).

- prio, long: higher (1.16, 1.23, 1.18)
- hinted, long: higher (1.15, 1.26, 1.21)
- hinted+rx, long: higher (1.30, 1.36, 1.30)

## rho = 0.90

p99 per kind (median of repeats), its ratio to the SLO, mean wait (mean minus min latency) and the predicted mean wait (pooled / per core).

| config | short p99 | short wait (pred) | long p99 | long wait (pred) |
|---|---|---|---|---|
| fifo | 360 (3.60) | 55.7 (36.5/167) | 408 (0.74) | 55.1 (36.5/167) |
| prio | 84 (0.84) | 25.3 (5.0/23) | 466 (0.85) | 64.4 (49.6/227) |
| hinted | 84 (0.84) | 25.6 (5.0/23) | 501 (0.91) | 66.8 (49.6/227) |
| hinted+rx | 59 (0.59) | 19.4 (5.0/23) | 537 (0.98) | 73.9 (49.6/227) |

Price at rho 0.90: unscored kinds' p99 against fifo (paired).

- prio, long: higher (1.11, 1.19, 1.22)
- hinted, long: higher (1.20, 1.27, 1.19)
- hinted+rx, long: higher (1.28, 1.49, 1.29)

## Where the time goes at rho = 0.90 (us; mean over repeats)

lag = client send minus schedule; in = send to server enqueue (delivery and RX-queue wait, plus classification); rq = runqueue; svc = handler; out = reply path; thread stolen = the handler ran on another kthread than the one that queued it; packet stolen = the packet was processed by another kthread than the owner of its RX queue.

| config | kind | part | lag | in | rq | svc | out | thread stolen % | packet stolen % |
|---|---|---|---|---|---|---|---|---|---|
| fifo | short | mean | -4.4 | 18.9 | 35.8 | 5.1 | 1.8 | 15 | 25 |
| fifo | short | tail99 | -4.4 | 41.8 | 460.2 | 5.1 | 1.8 | 19 | 0 |
| fifo | long | mean | -4.4 | 18.9 | 35.9 | 50.2 | 1.8 | 15 | 24 |
| fifo | long | tail99 | -4.4 | 41.7 | 460.2 | 53.3 | 1.8 | 20 | 0 |
| prio | short | mean | -4.4 | 19.7 | 5.2 | 5.1 | 1.8 | 7 | 27 |
| prio | short | tail99 | -4.3 | 77.6 | 8.1 | 5.7 | 2.1 | 2 | 1 |
| prio | long | mean | -4.4 | 19.7 | 43.8 | 50.2 | 1.8 | 20 | 27 |
| prio | long | tail99 | -4.4 | 37.3 | 509.9 | 51.2 | 1.8 | 25 | 0 |
| hinted | short | mean | -4.4 | 20.0 | 5.3 | 5.1 | 1.8 | 6 | 26 |
| hinted | short | tail99 | -4.3 | 77.7 | 8.3 | 5.8 | 2.2 | 2 | 1 |
| hinted | long | mean | -4.4 | 20.0 | 46.4 | 50.2 | 1.8 | 20 | 26 |
| hinted | long | tail99 | -4.4 | 37.2 | 546.6 | 52.1 | 1.9 | 25 | 0 |
| hinted+rx | short | mean | -4.4 | 14.0 | 5.1 | 5.1 | 1.8 | 7 | 23 |
| hinted+rx | short | tail99 | -4.2 | 44.5 | 13.3 | 5.8 | 2.2 | 4 | 1 |
| hinted+rx | long | mean | -4.4 | 14.0 | 60.1 | 50.2 | 1.8 | 24 | 23 |
| hinted+rx | long | tail99 | -4.4 | 20.0 | 626.0 | 52.1 | 1.8 | 24 | 0 |

## Mean-wait check (pre-registered)

dwait = growth of the kind's mean latency over rho 0.50, net of the change in its handler time, paired by repeat; predicted = pred(rho) - pred(0.50) pooled / per core.

| config | rho | short dwait meas (pooled / per core) ok | long dwait meas (pooled / per core) ok |
|---|---|---|---|
| fifo | 0.80 | 15.7 (12.2 / 56) NO | 15.7 (12.2 / 56) NO |
| fifo | 0.85 | 26.2 (19.7 / 86) NO | 26.2 (19.7 / 86) NO |
| fifo | 0.90 | 51.8 (34.9 / 148) NO | 52.1 (34.9 / 148) NO |
| prio | 0.80 | 10.0 (2.7 / 9) NO | 18.0 (16.2 / 75) yes |
| prio | 0.85 | 14.7 (3.3 / 10) NO | 30.3 (26.5 / 118) yes |
| prio | 0.90 | 21.6 (4.0 / 12) NO | 60.3 (47.7 / 205) yes |
| hinted | 0.80 | 10.3 (2.7 / 9) NO | 18.5 (16.2 / 75) yes |
| hinted | 0.85 | 14.6 (3.3 / 10) NO | 30.7 (26.5 / 118) yes |
| hinted | 0.90 | 22.0 (4.0 / 12) NO | 62.7 (47.7 / 205) yes |
| hinted+rx | 0.80 | 8.6 (2.7 / 9) NO | 19.6 (16.2 / 75) yes |
| hinted+rx | 0.85 | 11.8 (3.3 / 10) NO | 34.8 (26.5 / 118) yes |
| hinted+rx | 0.90 | 15.7 (4.0 / 12) NO | 69.6 (47.7 / 205) yes |

Pre-registered check passes in 6 of 18 cells (policies without +rx).

