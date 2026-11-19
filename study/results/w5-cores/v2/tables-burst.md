# w5-cores (burst), session v2

W2b's traffic on 2, 4 and 6 cores, and on 2 guaranteed + 2 burstable cores next to a batch job

Scored kinds: short (SLO short 100 us). Price: long. 3 repeats; configurations in ladder order.

## SLO-load

Highest rho at which every scored kind's p99 <= its SLO, per repeat (>= means it never crossed within the grid). Compared by the paired rule; when the SLO-load cannot decide because of the grid top, by the worst scored p99/SLO at rho 0.80.

| config | SLO-load (median) | per repeat | worst p99/SLO at top | vs fifo | vs the rung below |
|---|---|---|---|---|---|
| fifo | 0.60 | 0.67, 0.60, 0.60 | 1.67 |  |  |
| prio | 0.50 | 0.70, 0.50, 0.50 | inf | inconclusive on SLO-load (1.04, 0.83, 0.83) | inconclusive on SLO-load (1.04, 0.83, 0.83) |
| hinted | 0.70 | 0.70, 0.60, 0.70 | inf | inconclusive on SLO-load (1.04, 1.00, 1.17) |  |
| hinted+rx | 0.60 | 0.50, 0.60, 0.60 | inf | inconclusive on SLO-load (0.74, 1.00, 1.00) | inconclusive on SLO-load (0.71, 1.00, 0.86) |

## rho = 0.80

p99 per kind (median of repeats), its ratio to the SLO, mean wait (mean minus min latency) and the predicted mean wait (pooled / per core).

| config | short p99 | short wait (pred) | long p99 | long wait (pred) |
|---|---|---|---|---|
| fifo | 167 (1.67) | 29.7 (13.8/74) | 216 (0.39) | 28.9 (13.8/74) |
| prio | inf | 6531.7 (3.6/19) | inf | 6882.5 (18.0/97) |
| hinted | inf | 5379.4 (3.6/19) | inf | 5549.5 (18.0/97) |
| hinted+rx | inf | 17289.9 (3.6/19) | inf | 17288.8 (18.0/97) |

Price at rho 0.80: unscored kinds' p99 against fifo (paired).


## Where the time goes at rho = 0.80 (us; mean over repeats)

lag = client send minus schedule; in = send to server enqueue (delivery and RX-queue wait, plus classification); rq = runqueue; svc = handler; out = reply path; thread stolen = the handler ran on another kthread than the one that queued it; packet stolen = the packet was processed by another kthread than the owner of its RX queue.

| config | kind | part | lag | in | rq | svc | out | thread stolen % | packet stolen % |
|---|---|---|---|---|---|---|---|---|---|
| fifo | short | mean | -4.4 | 5765.1 | 1113.8 | 5.1 | 2.2 | 14 | 30 |
| fifo | short | tail99 | -4.4 | 41817.2 | 2298.5 | 5.6 | 2.4 | 29 | 34 |
| fifo | long | mean | -4.4 | 5780.1 | 1115.6 | 50.6 | 2.2 | 14 | 30 |
| fifo | long | tail99 | -4.4 | 41869.1 | 2291.8 | 58.1 | 2.4 | 29 | 35 |
| prio | short | mean | -4.4 | 16261.4 | 1833.0 | 5.1 | 2.1 | 4 | 33 |
| prio | short | tail99 | -4.4 | 115388.8 | 6723.7 | 5.1 | 2.0 | 0 | 100 |
| prio | long | mean | -4.4 | 16720.1 | 2274.1 | 51.2 | 2.2 | 14 | 33 |
| prio | long | tail99 | -4.4 | 117785.5 | 6953.3 | 55.7 | 2.1 | 6 | 100 |
| hinted | short | mean | -4.4 | 15981.6 | 1793.2 | 5.1 | 2.2 | 4 | 32 |
| hinted | short | tail99 | -4.4 | 83289.4 | 4438.2 | 5.4 | 2.2 | 1 | 68 |
| hinted | long | mean | -4.4 | 16371.1 | 2241.1 | 51.2 | 2.2 | 14 | 33 |
| hinted | long | tail99 | -4.4 | 83443.4 | 4715.5 | 70.9 | 2.2 | 11 | 67 |
| hinted+rx | short | mean | -4.4 | 30599.2 | 3360.3 | 5.1 | 2.1 | 2 | 22 |
| hinted+rx | short | tail99 | -4.3 | 129715.7 | 4534.2 | 5.3 | 2.3 | 3 | 68 |
| hinted+rx | long | mean | -4.4 | 31314.8 | 4080.7 | 53.3 | 2.1 | 9 | 22 |
| hinted+rx | long | tail99 | -4.4 | 130967.2 | 4751.4 | 100.5 | 2.2 | 11 | 67 |

## Mean-wait check (pre-registered)

dwait = growth of the kind's mean latency over rho 0.30, net of the change in its handler time, paired by repeat; predicted = pred(rho) - pred(0.30) pooled / per core.

| config | rho | short dwait meas (pooled / per core) ok | long dwait meas (pooled / per core) ok |
|---|---|---|---|
| fifo | 0.80 | 23.1 (13.6 / 66) NO | 23.2 (13.6 / 66) NO |
| prio | 0.80 | 6526.4 (3.4 / 13) NO | 6876.0 (17.8 / 88) NO |
| hinted | 0.80 | 5374.1 (3.4 / 13) NO | 5542.7 (17.8 / 88) NO |
| hinted+rx | 0.80 | 48133.6 (3.4 / 13) NO | 50414.2 (17.8 / 88) NO |

Pre-registered check passes in 0 of 6 cells (policies without +rx).

