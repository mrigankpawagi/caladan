# w5-cores (cores6), session v2

W2b's traffic on 2, 4 and 6 cores, and on 2 guaranteed + 2 burstable cores next to a batch job

Scored kinds: short (SLO short 100 us). Price: long. 3 repeats; configurations in ladder order.

## SLO-load

Highest rho at which every scored kind's p99 <= its SLO, per repeat (>= means it never crossed within the grid). Compared by the paired rule; when the SLO-load cannot decide because of the grid top, by the worst scored p99/SLO at rho 0.90.

| config | SLO-load (median) | per repeat | worst p99/SLO at top | vs fifo | vs the rung below |
|---|---|---|---|---|---|
| fifo | 0.79 | 0.79, 0.79, 0.78 | 2.58 |  |  |
| prio | >=0.90 | >=0.90, >=0.90, >=0.90 | 0.84 | better on SLO-load (1.14, 1.14, 1.15) | better on SLO-load (1.14, 1.14, 1.15) |
| hinted | >=0.90 | >=0.90, >=0.90, >=0.90 | 0.84 | better on SLO-load (1.14, 1.14, 1.15) |  |
| hinted+rx | >=0.90 | >=0.90, >=0.90, >=0.90 | 0.60 | better on SLO-load (1.14, 1.14, 1.15) | better on p99/SLO at top load (0.70, 0.71, 0.71) |

## rho = 0.80

p99 per kind (median of repeats), its ratio to the SLO, mean wait (mean minus min latency) and the predicted mean wait (pooled / per core).

| config | short p99 | short wait (pred) | long p99 | long wait (pred) |
|---|---|---|---|---|
| fifo | 105 (1.05) | 13.4 (13.8/74) | 151 (0.27) | 13.5 (13.8/74) |
| prio | 64 (0.64) | 10.6 (3.6/19) | 171 (0.31) | 14.0 (18.0/97) |
| hinted | 64 (0.64) | 10.5 (3.6/19) | 169 (0.31) | 14.5 (18.0/97) |
| hinted+rx | 56 (0.56) | 9.7 (3.6/19) | 174 (0.32) | 14.9 (18.0/97) |

Price at rho 0.80: unscored kinds' p99 against fifo (paired).

- prio, long: higher (1.09, 1.13, 1.10)
- hinted, long: higher (1.11, 1.12, 1.09)
- hinted+rx, long: higher (1.14, 1.15, 1.13)

## rho = 0.85

p99 per kind (median of repeats), its ratio to the SLO, mean wait (mean minus min latency) and the predicted mean wait (pooled / per core).

| config | short p99 | short wait (pred) | long p99 | long wait (pred) |
|---|---|---|---|---|
| fifo | 152 (1.52) | 21.2 (21.3/105) | 199 (0.36) | 21.4 (21.3/105) |
| prio | 73 (0.73) | 14.8 (4.3/21) | 230 (0.42) | 23.6 (28.4/140) |
| hinted | 73 (0.73) | 14.6 (4.3/21) | 225 (0.41) | 23.0 (28.4/140) |
| hinted+rx | 58 (0.58) | 12.9 (4.3/21) | 246 (0.45) | 24.7 (28.4/140) |

Price at rho 0.85: unscored kinds' p99 against fifo (paired).

- prio, long: higher (1.16, 1.24, 1.14)
- hinted, long: higher (1.16, 1.15, 1.11)
- hinted+rx, long: higher (1.28, 1.18, 1.22)

## rho = 0.90

p99 per kind (median of repeats), its ratio to the SLO, mean wait (mean minus min latency) and the predicted mean wait (pooled / per core).

| config | short p99 | short wait (pred) | long p99 | long wait (pred) |
|---|---|---|---|---|
| fifo | 258 (2.58) | 38.5 (36.5/167) | 301 (0.55) | 37.6 (36.5/167) |
| prio | 84 (0.84) | 21.8 (5.0/23) | 375 (0.68) | 44.2 (49.6/227) |
| hinted | 84 (0.84) | 21.8 (5.0/23) | 384 (0.70) | 44.8 (49.6/227) |
| hinted+rx | 60 (0.60) | 17.7 (5.0/23) | 426 (0.77) | 51.4 (49.6/227) |

Price at rho 0.90: unscored kinds' p99 against fifo (paired).

- prio, long: higher (1.25, 1.21, 1.23)
- hinted, long: higher (1.28, 1.31, 1.19)
- hinted+rx, long: higher (1.32, 1.45, 1.32)

## Where the time goes at rho = 0.90 (us; mean over repeats)

lag = client send minus schedule; in = send to server enqueue (delivery and RX-queue wait, plus classification); rq = runqueue; svc = handler; out = reply path; thread stolen = the handler ran on another kthread than the one that queued it; packet stolen = the packet was processed by another kthread than the owner of its RX queue.

| config | kind | part | lag | in | rq | svc | out | thread stolen % | packet stolen % |
|---|---|---|---|---|---|---|---|---|---|
| fifo | short | mean | -4.3 | 16.2 | 22.3 | 5.1 | 2.0 | 19 | 34 |
| fifo | short | tail99 | -4.3 | 36.0 | 307.4 | 5.2 | 2.1 | 45 | 0 |
| fifo | long | mean | -4.3 | 16.2 | 22.2 | 50.2 | 2.0 | 19 | 34 |
| fifo | long | tail99 | -4.3 | 36.1 | 305.4 | 52.7 | 2.0 | 44 | 0 |
| prio | short | mean | -4.3 | 16.7 | 4.5 | 5.1 | 2.0 | 8 | 37 |
| prio | short | tail99 | -4.3 | 74.8 | 11.2 | 5.8 | 2.3 | 5 | 3 |
| prio | long | mean | -4.3 | 16.7 | 27.8 | 50.2 | 2.0 | 25 | 37 |
| prio | long | tail99 | -4.3 | 38.5 | 397.7 | 52.1 | 2.0 | 51 | 0 |
| hinted | short | mean | -4.3 | 16.8 | 4.6 | 5.1 | 2.0 | 8 | 37 |
| hinted | short | tail99 | -4.3 | 74.7 | 11.0 | 5.8 | 2.4 | 5 | 2 |
| hinted | long | mean | -4.3 | 16.8 | 28.3 | 50.2 | 2.0 | 25 | 37 |
| hinted | long | tail99 | -4.3 | 38.5 | 416.6 | 51.2 | 2.0 | 52 | 0 |
| hinted+rx | short | mean | -4.3 | 12.5 | 4.7 | 5.1 | 2.0 | 9 | 31 |
| hinted+rx | short | tail99 | -4.1 | 43.3 | 14.2 | 5.9 | 2.6 | 7 | 2 |
| hinted+rx | long | mean | -4.3 | 12.5 | 38.6 | 50.2 | 2.0 | 30 | 31 |
| hinted+rx | long | tail99 | -4.3 | 18.5 | 471.3 | 51.6 | 2.0 | 52 | 0 |

## Mean-wait check (pre-registered)

dwait = growth of the kind's mean latency over rho 0.50, net of the change in its handler time, paired by repeat; predicted = pred(rho) - pred(0.50) pooled / per core.

| config | rho | short dwait meas (pooled / per core) ok | long dwait meas (pooled / per core) ok |
|---|---|---|---|
| fifo | 0.80 | 10.3 (12.2 / 56) yes | 10.3 (12.2 / 56) yes |
| fifo | 0.85 | 18.1 (19.7 / 86) yes | 18.2 (19.7 / 86) yes |
| fifo | 0.90 | 35.4 (34.9 / 148) yes | 35.5 (34.9 / 148) yes |
| prio | 0.80 | 7.6 (2.7 / 9) yes | 11.7 (16.2 / 75) NO |
| prio | 0.85 | 11.8 (3.3 / 10) NO | 20.4 (26.5 / 118) NO |
| prio | 0.90 | 18.7 (4.0 / 12) NO | 41.3 (47.7 / 205) NO |
| hinted | 0.80 | 7.5 (2.7 / 9) yes | 11.5 (16.2 / 75) NO |
| hinted | 0.85 | 11.6 (3.3 / 10) NO | 20.0 (26.5 / 118) NO |
| hinted | 0.90 | 18.8 (4.0 / 12) NO | 42.5 (47.7 / 205) NO |
| hinted+rx | 0.80 | 6.7 (2.7 / 9) yes | 12.5 (16.2 / 75) NO |
| hinted+rx | 0.85 | 9.8 (3.3 / 10) yes | 22.4 (26.5 / 118) NO |
| hinted+rx | 0.90 | 14.7 (4.0 / 12) NO | 49.1 (47.7 / 205) yes |

Pre-registered check passes in 8 of 18 cells (policies without +rx).

