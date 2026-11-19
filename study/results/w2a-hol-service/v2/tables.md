# w2a-hol-service, session v2

Size only: 5 us vs 50 us requests, no class, no deadline

Scored kinds: short, long (SLO short 100 us, long 550 us). Price: none. 3 repeats; configurations in ladder order.

## SLO-load

Highest rho at which every scored kind's p99 <= its SLO, per repeat (>= means it never crossed within the grid). Compared by the paired rule; when the SLO-load cannot decide because of the grid top, by the worst scored p99/SLO at rho 0.90.

| config | SLO-load (median) | per repeat | worst p99/SLO at top | vs fifo | vs the rung below |
|---|---|---|---|---|---|
| fifo | 0.72 | 0.72, 0.72, 0.72 | 3.48 |  |  |
| prio | 0.72 | 0.72, 0.73, 0.72 | 3.59 | tie on SLO-load (1.00, 1.00, 1.00) | tie on SLO-load (1.00, 1.00, 1.00) |
| prio_edf | 0.72 | 0.72, 0.72, 0.72 | 3.58 | tie on SLO-load (1.00, 0.99, 1.00) | tie on SLO-load (1.00, 0.99, 1.00) |
| hinted | 0.90 | >=0.90, >=0.90, 0.90 | 0.91 | better on SLO-load (1.25, 1.24, 1.24) | better on SLO-load (1.24, 1.25, 1.24) |
| hinted+rx | >=0.90 | >=0.90, >=0.90, >=0.90 | 0.98 | better on SLO-load (1.25, 1.24, 1.25) | inconclusive on p99/SLO at top load (1.13, 1.08, 0.98) |
| edf | 0.72 | 0.72, 0.72, 0.72 | 3.47 | tie on SLO-load (1.00, 1.00, 1.00) | tie on SLO-load (1.00, 1.00, 1.00) |

## rho = 0.80

p99 per kind (median of repeats), its ratio to the SLO, mean wait (mean minus min latency) and the predicted mean wait (pooled / per core).

| config | short p99 | short wait (pred) | long p99 | long wait (pred) |
|---|---|---|---|---|
| fifo | 146 (1.46) | 19.1 (13.8/74) | 193 (0.35) | 19.2 (13.8/74) |
| prio | 141 (1.41) | 18.7 (13.8/74) | 188 (0.34) | 18.8 (13.8/74) |
| prio_edf | 146 (1.46) | 18.9 (13.8/74) | 193 (0.35) | 19.0 (13.8/74) |
| hinted | 71 (0.71) | 13.3 (3.6/19) | 221 (0.40) | 21.6 (18.0/97) |
| hinted+rx | 58 (0.58) | 11.5 (3.6/19) | 230 (0.42) | 23.0 (18.0/97) |
| edf | 148 (1.48) | 19.4 (13.8/74) | 192 (0.35) | 19.4 (13.8/74) |

## rho = 0.85

p99 per kind (median of repeats), its ratio to the SLO, mean wait (mean minus min latency) and the predicted mean wait (pooled / per core).

| config | short p99 | short wait (pred) | long p99 | long wait (pred) |
|---|---|---|---|---|
| fifo | 208 (2.08) | 29.8 (21.3/105) | 257 (0.47) | 30.1 (21.3/105) |
| prio | 210 (2.10) | 30.3 (21.3/105) | 256 (0.47) | 30.4 (21.3/105) |
| prio_edf | 214 (2.14) | 30.4 (21.3/105) | 259 (0.47) | 30.5 (21.3/105) |
| hinted | 78 (0.78) | 18.0 (4.3/21) | 306 (0.56) | 35.0 (28.4/140) |
| hinted+rx | 59 (0.59) | 14.7 (4.3/21) | 316 (0.57) | 37.2 (28.4/140) |
| edf | 206 (2.06) | 29.4 (21.3/105) | 251 (0.46) | 29.4 (21.3/105) |

## rho = 0.90

p99 per kind (median of repeats), its ratio to the SLO, mean wait (mean minus min latency) and the predicted mean wait (pooled / per core).

| config | short p99 | short wait (pred) | long p99 | long wait (pred) |
|---|---|---|---|---|
| fifo | 348 (3.48) | 54.0 (36.5/167) | 392 (0.71) | 54.0 (36.5/167) |
| prio | 359 (3.59) | 54.3 (36.5/167) | 406 (0.74) | 54.6 (36.5/167) |
| prio_edf | 358 (3.58) | 55.0 (36.5/167) | 402 (0.73) | 55.0 (36.5/167) |
| hinted | 85 (0.85) | 25.0 (5.0/23) | 498 (0.91) | 66.2 (49.6/227) |
| hinted+rx | 60 (0.60) | 19.0 (5.0/23) | 540 (0.98) | 74.0 (49.6/227) |
| edf | 347 (3.47) | 55.6 (36.5/167) | 396 (0.72) | 55.6 (36.5/167) |

## Where the time goes at rho = 0.90 (us; mean over repeats)

lag = client send minus schedule; in = send to server enqueue (delivery and RX-queue wait, plus classification); rq = runqueue; svc = handler; out = reply path; thread stolen = the handler ran on another kthread than the one that queued it; packet stolen = the packet was processed by another kthread than the owner of its RX queue.

| config | kind | part | lag | in | rq | svc | out | thread stolen % | packet stolen % |
|---|---|---|---|---|---|---|---|---|---|
| fifo | short | mean | -4.1 | 19.0 | 35.5 | 5.1 | 2.2 | 15 | 24 |
| fifo | short | tail99 | -4.1 | 35.1 | 411.7 | 5.1 | 2.2 | 19 | 0 |
| fifo | long | mean | -4.1 | 19.1 | 35.5 | 50.2 | 2.2 | 15 | 24 |
| fifo | long | tail99 | -4.1 | 35.2 | 408.3 | 51.6 | 2.2 | 19 | 0 |
| prio | short | mean | -4.2 | 19.0 | 35.9 | 5.1 | 2.1 | 15 | 24 |
| prio | short | tail99 | -4.1 | 34.4 | 419.0 | 5.1 | 2.2 | 21 | 0 |
| prio | long | mean | -4.2 | 19.0 | 36.1 | 50.2 | 2.2 | 15 | 24 |
| prio | long | tail99 | -4.1 | 34.3 | 420.7 | 53.0 | 2.2 | 22 | 0 |
| prio_edf | short | mean | -4.2 | 19.2 | 36.8 | 5.1 | 2.1 | 15 | 24 |
| prio_edf | short | tail99 | -4.2 | 34.5 | 432.7 | 5.1 | 2.2 | 19 | 0 |
| prio_edf | long | mean | -4.2 | 19.2 | 36.8 | 50.2 | 2.2 | 15 | 24 |
| prio_edf | long | tail99 | -4.2 | 34.3 | 430.5 | 52.6 | 2.1 | 19 | 0 |
| hinted | short | mean | -4.2 | 20.0 | 5.3 | 5.1 | 2.1 | 6 | 26 |
| hinted | short | tail99 | -4.1 | 78.1 | 8.4 | 5.8 | 2.5 | 2 | 1 |
| hinted | long | mean | -4.1 | 20.0 | 47.0 | 50.2 | 2.2 | 20 | 26 |
| hinted | long | tail99 | -4.2 | 37.2 | 556.9 | 51.7 | 2.2 | 25 | 0 |
| hinted+rx | short | mean | -4.2 | 14.1 | 5.1 | 5.1 | 2.1 | 7 | 22 |
| hinted+rx | short | tail99 | -4.1 | 44.3 | 13.4 | 6.0 | 2.5 | 4 | 1 |
| hinted+rx | long | mean | -4.2 | 14.1 | 60.3 | 50.2 | 2.2 | 24 | 22 |
| hinted+rx | long | tail99 | -4.2 | 19.8 | 618.9 | 51.4 | 2.2 | 26 | 0 |
| edf | short | mean | -4.2 | 19.1 | 35.9 | 5.1 | 2.2 | 15 | 24 |
| edf | short | tail99 | -4.1 | 35.1 | 422.7 | 5.2 | 2.2 | 22 | 0 |
| edf | long | mean | -4.2 | 19.1 | 35.9 | 50.2 | 2.2 | 15 | 24 |
| edf | long | tail99 | -4.1 | 34.8 | 425.1 | 52.6 | 2.2 | 21 | 0 |

## Mean-wait check (pre-registered)

dwait = growth of the kind's mean latency over rho 0.50, net of the change in its handler time, paired by repeat; predicted = pred(rho) - pred(0.50) pooled / per core.

| config | rho | short dwait meas (pooled / per core) ok | long dwait meas (pooled / per core) ok |
|---|---|---|---|
| fifo | 0.80 | 15.7 (12.2 / 56) NO | 15.8 (12.2 / 56) NO |
| fifo | 0.85 | 26.5 (19.7 / 86) NO | 26.7 (19.7 / 86) NO |
| fifo | 0.90 | 50.7 (34.9 / 148) NO | 50.5 (34.9 / 148) NO |
| prio | 0.80 | 15.4 (12.2 / 56) yes | 15.4 (12.2 / 56) yes |
| prio | 0.85 | 26.9 (19.7 / 86) yes | 26.9 (19.7 / 86) yes |
| prio | 0.90 | 50.9 (34.9 / 148) yes | 51.0 (34.9 / 148) yes |
| prio_edf | 0.80 | 15.4 (12.2 / 56) yes | 15.4 (12.2 / 56) yes |
| prio_edf | 0.85 | 26.9 (19.7 / 86) yes | 27.0 (19.7 / 86) yes |
| prio_edf | 0.90 | 51.5 (34.9 / 148) yes | 51.4 (34.9 / 148) yes |
| hinted | 0.80 | 10.1 (2.7 / 9) NO | 18.0 (16.2 / 75) yes |
| hinted | 0.85 | 14.8 (3.3 / 10) NO | 31.4 (26.5 / 118) yes |
| hinted | 0.90 | 21.8 (4.0 / 12) NO | 62.5 (47.7 / 205) yes |
| hinted+rx | 0.80 | 8.4 (2.7 / 9) yes | 19.2 (16.2 / 75) yes |
| hinted+rx | 0.85 | 11.5 (3.3 / 10) NO | 33.4 (26.5 / 118) yes |
| hinted+rx | 0.90 | 15.8 (4.0 / 12) NO | 70.2 (47.7 / 205) yes |
| edf | 0.80 | 15.9 (12.2 / 56) yes | 15.9 (12.2 / 56) yes |
| edf | 0.85 | 26.0 (19.7 / 86) yes | 25.9 (19.7 / 86) yes |
| edf | 0.90 | 52.2 (34.9 / 148) yes | 52.1 (34.9 / 148) yes |

Pre-registered check passes in 21 of 30 cells (policies without +rx).

