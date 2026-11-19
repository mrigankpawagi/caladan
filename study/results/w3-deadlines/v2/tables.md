# w3-deadlines, session v2

Deadline within a class: equal work, 50 us vs 500 us deadlines, all HIGH

Scored kinds: tight, loose (SLO tight 50 us, loose 500 us). Price: none. 3 repeats; configurations in ladder order.

## SLO-load

Highest rho at which every scored kind's p99 <= its SLO, per repeat (>= means it never crossed within the grid). Compared by the paired rule; when the SLO-load cannot decide because of the grid top, by the worst scored p99/SLO at rho 0.90.

| config | SLO-load (median) | per repeat | worst p99/SLO at top | vs fifo | vs the rung below |
|---|---|---|---|---|---|
| fifo | 0.76 | 0.76, 0.76, 0.76 | 2.60 |  |  |
| fifo+rx | 0.76 | 0.76, 0.76, 0.76 | 2.88 | tie on SLO-load (0.99, 1.00, 1.00) | tie on SLO-load (0.99, 1.00, 1.00) |
| prio | 0.76 | 0.76, 0.76, 0.76 | 2.66 | tie on SLO-load (1.00, 1.00, 1.00) | tie on SLO-load (1.00, 1.00, 1.00) |
| prio+rx | 0.76 | 0.76, 0.76, 0.76 | 2.96 | tie on SLO-load (0.99, 1.00, 0.99) | tie on SLO-load (1.00, 0.99, 0.99) |
| prio_edf | 0.82 | 0.82, 0.82, 0.82 | 1.28 | better on SLO-load (1.08, 1.09, 1.08) | better on SLO-load (1.08, 1.08, 1.08) |
| prio_edf+rx | >=0.90 | >=0.90, >=0.90, >=0.90 | 0.66 | better on SLO-load (1.18, 1.18, 1.18) | better on SLO-load (1.09, 1.09, 1.09) |
| hinted | 0.82 | 0.82, 0.82, 0.82 | 1.28 | better on SLO-load (1.08, 1.08, 1.09) | tie on SLO-load (1.00, 1.00, 1.00) |
| hinted+rx | >=0.90 | >=0.90, >=0.90, >=0.90 | 0.66 | better on SLO-load (1.18, 1.18, 1.18) | better on SLO-load (1.09, 1.09, 1.09) |
| edf | 0.82 | 0.82, 0.82, 0.82 | 1.28 | better on SLO-load (1.07, 1.08, 1.09) | tie on SLO-load (1.00, 1.00, 1.00) |
| edf+rx | >=0.90 | >=0.90, >=0.90, >=0.90 | 0.66 | better on SLO-load (1.18, 1.18, 1.18) | better on SLO-load (1.09, 1.09, 1.09) |

## rho = 0.80

p99 per kind (median of repeats), its ratio to the SLO, mean wait (mean minus min latency) and the predicted mean wait (pooled / per core).

| config | tight p99 | tight wait (pred) | loose p99 | loose wait (pred) |
|---|---|---|---|---|
| fifo | 58 (1.16) | 8.0 (3.8/20) | 57 (0.11) | 8.0 (3.8/20) |
| fifo+rx | 59 (1.18) | 8.3 (3.8/20) | 59 (0.12) | 8.3 (3.8/20) |
| prio | 57 (1.14) | 8.0 (3.8/20) | 57 (0.11) | 8.0 (3.8/20) |
| prio+rx | 59 (1.18) | 8.3 (3.8/20) | 59 (0.12) | 8.3 (3.8/20) |
| prio_edf | 46 (0.92) | 6.2 (0.9/5) | 62 (0.12) | 8.6 (4.5/24) |
| prio_edf+rx | 30 (0.60) | 4.7 (0.9/5) | 70 (0.14) | 9.2 (4.5/24) |
| hinted | 45 (0.90) | 6.1 (0.9/5) | 61 (0.12) | 8.5 (4.5/24) |
| hinted+rx | 30 (0.60) | 4.8 (0.9/5) | 69 (0.14) | 9.3 (4.5/24) |
| edf | 45 (0.90) | 6.1 (0.9/5) | 62 (0.12) | 8.5 (4.5/24) |
| edf+rx | 30 (0.60) | 4.8 (0.9/5) | 69 (0.14) | 9.2 (4.5/24) |

## rho = 0.85

p99 per kind (median of repeats), its ratio to the SLO, mean wait (mean minus min latency) and the predicted mean wait (pooled / per core).

| config | tight p99 | tight wait (pred) | loose p99 | loose wait (pred) |
|---|---|---|---|---|
| fifo | 78 (1.56) | 11.8 (5.9/29) | 78 (0.16) | 11.8 (5.9/29) |
| fifo+rx | 82 (1.64) | 12.5 (5.9/29) | 82 (0.16) | 12.5 (5.9/29) |
| prio | 79 (1.58) | 11.9 (5.9/29) | 79 (0.16) | 11.9 (5.9/29) |
| prio+rx | 82 (1.64) | 12.6 (5.9/29) | 83 (0.17) | 12.6 (5.9/29) |
| prio_edf | 55 (1.10) | 8.4 (1.1/5) | 86 (0.17) | 12.9 (7.1/35) |
| prio_edf+rx | 31 (0.62) | 5.6 (1.1/5) | 101 (0.20) | 14.4 (7.1/35) |
| hinted | 56 (1.12) | 8.4 (1.1/5) | 86 (0.17) | 12.8 (7.1/35) |
| hinted+rx | 31 (0.62) | 5.5 (1.1/5) | 99 (0.20) | 14.2 (7.1/35) |
| edf | 56 (1.12) | 8.5 (1.1/5) | 87 (0.17) | 12.9 (7.1/35) |
| edf+rx | 31 (0.62) | 5.5 (1.1/5) | 100 (0.20) | 14.4 (7.1/35) |

## rho = 0.90

p99 per kind (median of repeats), its ratio to the SLO, mean wait (mean minus min latency) and the predicted mean wait (pooled / per core).

| config | tight p99 | tight wait (pred) | loose p99 | loose wait (pred) |
|---|---|---|---|---|
| fifo | 130 (2.60) | 21.5 (10.1/46) | 130 (0.26) | 21.5 (10.1/46) |
| fifo+rx | 144 (2.88) | 23.6 (10.1/46) | 143 (0.29) | 23.5 (10.1/46) |
| prio | 133 (2.66) | 21.5 (10.1/46) | 132 (0.26) | 21.5 (10.1/46) |
| prio+rx | 148 (2.96) | 24.1 (10.1/46) | 148 (0.30) | 24.0 (10.1/46) |
| prio_edf | 64 (1.28) | 13.0 (1.2/6) | 155 (0.31) | 24.0 (12.3/56) |
| prio_edf+rx | 33 (0.66) | 6.5 (1.2/6) | 181 (0.36) | 28.4 (12.3/56) |
| hinted | 64 (1.28) | 12.9 (1.2/6) | 147 (0.29) | 23.5 (12.3/56) |
| hinted+rx | 33 (0.66) | 6.6 (1.2/6) | 190 (0.38) | 29.8 (12.3/56) |
| edf | 64 (1.28) | 13.0 (1.2/6) | 148 (0.30) | 23.5 (12.3/56) |
| edf+rx | 33 (0.66) | 6.5 (1.2/6) | 183 (0.37) | 28.7 (12.3/56) |

## Where the time goes at rho = 0.90 (us; mean over repeats)

lag = client send minus schedule; in = send to server enqueue (delivery and RX-queue wait, plus classification); rq = runqueue; svc = handler; out = reply path; thread stolen = the handler ran on another kthread than the one that queued it; packet stolen = the packet was processed by another kthread than the owner of its RX queue.

| config | kind | part | lag | in | rq | svc | out | thread stolen % | packet stolen % |
|---|---|---|---|---|---|---|---|---|---|
| fifo | tight | mean | -4.2 | 11.1 | 10.5 | 10.1 | 2.2 | 14 | 23 |
| fifo | tight | tail99 | -4.1 | 28.9 | 120.0 | 11.5 | 2.7 | 17 | 0 |
| fifo | loose | mean | -4.2 | 11.1 | 10.5 | 10.1 | 2.2 | 14 | 23 |
| fifo | loose | tail99 | -4.1 | 28.4 | 119.0 | 11.7 | 2.5 | 17 | 0 |
| fifo+rx | tight | mean | -4.2 | 5.6 | 18.0 | 10.1 | 2.2 | 16 | 16 |
| fifo+rx | tight | tail99 | -4.2 | 12.6 | 172.0 | 11.6 | 2.5 | 17 | 0 |
| fifo+rx | loose | mean | -4.2 | 5.6 | 17.9 | 10.1 | 2.2 | 16 | 16 |
| fifo+rx | loose | tail99 | -4.2 | 11.9 | 169.3 | 11.7 | 2.6 | 17 | 0 |
| prio | tight | mean | -4.2 | 11.2 | 10.7 | 10.1 | 2.2 | 14 | 23 |
| prio | tight | tail99 | -4.1 | 28.7 | 125.4 | 11.4 | 2.6 | 16 | 0 |
| prio | loose | mean | -4.2 | 11.2 | 10.7 | 10.1 | 2.2 | 14 | 23 |
| prio | loose | tail99 | -4.2 | 28.4 | 125.5 | 11.6 | 2.6 | 16 | 0 |
| prio+rx | tight | mean | -4.2 | 5.5 | 18.6 | 10.1 | 2.2 | 16 | 15 |
| prio+rx | tight | tail99 | -4.1 | 7.7 | 166.6 | 11.7 | 2.5 | 17 | 0 |
| prio+rx | loose | mean | -4.2 | 5.5 | 18.6 | 10.1 | 2.2 | 16 | 15 |
| prio+rx | loose | tail99 | -4.1 | 7.4 | 166.7 | 11.7 | 2.5 | 18 | 0 |
| prio_edf | tight | mean | -4.2 | 11.2 | 2.0 | 10.1 | 2.2 | 5 | 23 |
| prio_edf | tight | tail99 | -4.1 | 46.9 | 9.5 | 11.4 | 2.6 | 2 | 1 |
| prio_edf | loose | mean | -4.2 | 11.1 | 12.9 | 10.1 | 2.2 | 16 | 23 |
| prio_edf | loose | tail99 | -4.2 | 28.2 | 156.2 | 11.6 | 2.5 | 19 | 0 |
| prio_edf+rx | tight | mean | -4.2 | 5.5 | 1.2 | 10.1 | 2.2 | 4 | 16 |
| prio_edf+rx | tight | tail99 | -4.1 | 8.2 | 18.3 | 11.3 | 2.8 | 3 | 1 |
| prio_edf+rx | loose | mean | -4.2 | 5.5 | 23.1 | 10.1 | 2.2 | 19 | 16 |
| prio_edf+rx | loose | tail99 | -4.2 | 7.5 | 216.2 | 11.6 | 2.6 | 20 | 0 |
| hinted | tight | mean | -4.2 | 11.2 | 2.0 | 10.1 | 2.2 | 5 | 23 |
| hinted | tight | tail99 | -4.1 | 47.1 | 9.6 | 11.7 | 2.5 | 3 | 1 |
| hinted | loose | mean | -4.2 | 11.2 | 12.6 | 10.1 | 2.2 | 16 | 23 |
| hinted | loose | tail99 | -4.1 | 28.1 | 147.8 | 11.6 | 2.5 | 19 | 0 |
| hinted+rx | tight | mean | -4.2 | 5.6 | 1.3 | 10.1 | 2.2 | 4 | 15 |
| hinted+rx | tight | tail99 | -4.1 | 9.5 | 22.4 | 11.8 | 2.6 | 4 | 1 |
| hinted+rx | loose | mean | -4.2 | 5.6 | 24.2 | 10.1 | 2.2 | 19 | 15 |
| hinted+rx | loose | tail99 | -4.2 | 8.5 | 234.1 | 11.3 | 2.6 | 19 | 0 |
| edf | tight | mean | -4.2 | 11.1 | 2.0 | 10.1 | 2.2 | 5 | 23 |
| edf | tight | tail99 | -4.1 | 47.3 | 9.7 | 11.6 | 2.6 | 3 | 2 |
| edf | loose | mean | -4.2 | 11.1 | 12.6 | 10.1 | 2.2 | 16 | 23 |
| edf | loose | tail99 | -4.2 | 28.6 | 153.0 | 11.6 | 2.6 | 18 | 0 |
| edf+rx | tight | mean | -4.2 | 5.5 | 1.2 | 10.1 | 2.2 | 4 | 16 |
| edf+rx | tight | tail99 | -4.1 | 8.7 | 20.7 | 11.4 | 2.7 | 4 | 1 |
| edf+rx | loose | mean | -4.2 | 5.5 | 23.2 | 10.1 | 2.2 | 19 | 16 |
| edf+rx | loose | tail99 | -4.2 | 8.1 | 222.4 | 11.6 | 2.6 | 20 | 0 |

## Mean-wait check (pre-registered)

dwait = growth of the kind's mean latency over rho 0.50, net of the change in its handler time, paired by repeat; predicted = pred(rho) - pred(0.50) pooled / per core.

| config | rho | tight dwait meas (pooled / per core) ok | loose dwait meas (pooled / per core) ok |
|---|---|---|---|
| fifo | 0.80 | 5.7 (3.4 / 15) NO | 5.7 (3.4 / 15) NO |
| fifo | 0.85 | 9.5 (5.4 / 24) NO | 9.5 (5.4 / 24) NO |
| fifo | 0.90 | 19.2 (9.6 / 41) NO | 19.1 (9.6 / 41) NO |
| fifo+rx | 0.80 | 5.9 (3.4 / 15) NO | 5.9 (3.4 / 15) NO |
| fifo+rx | 0.85 | 10.1 (5.4 / 24) NO | 10.1 (5.4 / 24) NO |
| fifo+rx | 0.90 | 21.2 (9.6 / 41) NO | 21.2 (9.6 / 41) NO |
| prio | 0.80 | 5.7 (3.4 / 15) yes | 5.7 (3.4 / 15) yes |
| prio | 0.85 | 9.6 (5.4 / 24) yes | 9.6 (5.4 / 24) yes |
| prio | 0.90 | 19.1 (9.6 / 41) yes | 19.2 (9.6 / 41) yes |
| prio+rx | 0.80 | 5.9 (3.4 / 15) yes | 5.9 (3.4 / 15) yes |
| prio+rx | 0.85 | 10.2 (5.4 / 24) yes | 10.2 (5.4 / 24) yes |
| prio+rx | 0.90 | 21.7 (9.6 / 41) yes | 21.6 (9.6 / 41) yes |
| prio_edf | 0.80 | 3.9 (0.7 / 2) NO | 6.2 (4.0 / 19) yes |
| prio_edf | 0.85 | 6.3 (0.8 / 2) NO | 10.5 (6.6 / 29) yes |
| prio_edf | 0.90 | 10.8 (1.0 / 3) NO | 21.6 (11.8 / 50) yes |
| prio_edf+rx | 0.80 | 2.5 (0.7 / 2) NO | 6.8 (4.0 / 19) yes |
| prio_edf+rx | 0.85 | 3.3 (0.8 / 2) NO | 12.0 (6.6 / 29) yes |
| prio_edf+rx | 0.90 | 4.3 (1.0 / 3) NO | 26.0 (11.8 / 50) yes |
| hinted | 0.80 | 3.8 (0.7 / 2) NO | 6.1 (4.0 / 19) yes |
| hinted | 0.85 | 6.2 (0.8 / 2) NO | 10.4 (6.6 / 29) yes |
| hinted | 0.90 | 10.7 (1.0 / 3) NO | 21.2 (11.8 / 50) yes |
| hinted+rx | 0.80 | 2.6 (0.7 / 2) NO | 6.8 (4.0 / 19) yes |
| hinted+rx | 0.85 | 3.3 (0.8 / 2) NO | 11.7 (6.6 / 29) yes |
| hinted+rx | 0.90 | 4.4 (1.0 / 3) NO | 27.4 (11.8 / 50) yes |
| edf | 0.80 | 3.9 (0.7 / 2) NO | 6.1 (4.0 / 19) yes |
| edf | 0.85 | 6.2 (0.8 / 2) NO | 10.5 (6.6 / 29) yes |
| edf | 0.90 | 10.7 (1.0 / 3) NO | 21.1 (11.8 / 50) yes |
| edf+rx | 0.80 | 2.5 (0.7 / 2) NO | 6.8 (4.0 / 19) yes |
| edf+rx | 0.85 | 3.3 (0.8 / 2) NO | 12.0 (6.6 / 29) yes |
| edf+rx | 0.90 | 4.3 (1.0 / 3) NO | 26.3 (11.8 / 50) yes |

Pre-registered check passes in 15 of 30 cells (policies without +rx).

