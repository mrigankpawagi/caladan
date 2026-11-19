# w5-cores (burst), session v2b

W2b's traffic on 2, 4 and 6 cores, and on 2 guaranteed + 2 burstable cores next to a batch job

Scored kinds: short (SLO short 100 us). Price: long. 3 repeats; configurations in ladder order.

## SLO-load

Highest rho at which every scored kind's p99 <= its SLO, per repeat (>= means it never crossed within the grid). Compared by the paired rule; when the SLO-load cannot decide because of the grid top, by the worst scored p99/SLO at rho 0.80.

| config | SLO-load (median) | per repeat | worst p99/SLO at top | vs fifo | vs the rung below |
|---|---|---|---|---|---|
| fifo | 0.50 | 0.50, 0.50, 0.67 | 1.61 |  |  |
| prio | 0.60 | 0.50, >=0.80, 0.60 | inf | inconclusive on SLO-load (1.00, 1.60, 0.89) | inconclusive on SLO-load (1.00, 1.60, 0.89) |
| hinted | 0.60 | 0.50, >=0.80, 0.60 | 0.74 | inconclusive on SLO-load (1.00, 1.60, 0.89) |  |
| hinted+rx | 0.70 | 0.70, 0.50, 0.70 | inf | inconclusive on SLO-load (1.40, 1.00, 1.04) | inconclusive on SLO-load (1.40, 0.63, 1.17) |

## rho = 0.80

p99 per kind (median of repeats), its ratio to the SLO, mean wait (mean minus min latency) and the predicted mean wait (pooled / per core).

| config | short p99 | short wait (pred) | long p99 | long wait (pred) |
|---|---|---|---|---|
| fifo | 161 (1.61) | 28.5 (13.8/74) | 206 (0.37) | 28.4 (13.8/74) |
| prio | inf | 4810.5 (3.6/19) | inf | 5017.2 (18.0/97) |
| hinted | 74 (0.74) | 19.6 (3.6/19) | 240 (0.44) | 32.1 (18.0/97) |
| hinted+rx | inf | 20909.6 (3.6/19) | inf | 21852.4 (18.0/97) |

Price at rho 0.80: unscored kinds' p99 against fifo (paired).

- prio, long: higher (1.18)
- hinted, long: higher (1.17, 1.18)

## Where the time goes at rho = 0.80 (us; mean over repeats)

lag = client send minus schedule; in = send to server enqueue (delivery and RX-queue wait, plus classification); rq = runqueue; svc = handler; out = reply path; thread stolen = the handler ran on another kthread than the one that queued it; packet stolen = the packet was processed by another kthread than the owner of its RX queue.

| config | kind | part | lag | in | rq | svc | out | thread stolen % | packet stolen % |
|---|---|---|---|---|---|---|---|---|---|
| fifo | short | mean | -4.4 | 7580.6 | 867.9 | 5.1 | 2.2 | 13 | 33 |
| fifo | short | tail99 | -4.4 | 24405.2 | 2325.0 | 5.5 | 2.3 | 22 | 34 |
| fifo | long | mean | -4.4 | 7556.0 | 866.6 | 50.5 | 2.2 | 13 | 33 |
| fifo | long | tail99 | -4.4 | 24331.3 | 2318.1 | 57.8 | 2.5 | 23 | 35 |
| prio | short | mean | -4.4 | 11803.1 | 1354.3 | 5.1 | 2.1 | 5 | 34 |
| prio | short | tail99 | -4.4 | 73133.0 | 4496.4 | 5.3 | 2.2 | 2 | 68 |
| prio | long | mean | -4.4 | 12063.4 | 1679.8 | 51.0 | 2.2 | 17 | 34 |
| prio | long | tail99 | -4.4 | 74688.1 | 4707.0 | 65.4 | 2.2 | 21 | 67 |
| hinted | short | mean | -4.4 | 16.2 | 3.7 | 5.1 | 2.2 | 7 | 37 |
| hinted | short | tail99 | -4.3 | 69.7 | 6.8 | 5.8 | 2.5 | 4 | 4 |
| hinted | long | mean | -4.4 | 16.2 | 16.3 | 50.2 | 2.2 | 22 | 37 |
| hinted | long | tail99 | -4.4 | 37.6 | 196.7 | 57.5 | 2.5 | 38 | 2 |
| hinted+rx | short | mean | -4.4 | 30856.2 | 3480.5 | 5.1 | 2.1 | 2 | 28 |
| hinted+rx | short | tail99 | -4.4 | 141572.9 | 6574.9 | 5.1 | 2.0 | 0 | 100 |
| hinted+rx | long | mean | -4.4 | 31750.1 | 4156.6 | 52.3 | 2.1 | 12 | 28 |
| hinted+rx | long | tail99 | -4.4 | 142913.0 | 6890.1 | 68.6 | 2.1 | 17 | 100 |

## Batch job's work rate (units/s, median of repeats)

| config | 0.30 | 0.40 | 0.50 | 0.60 | 0.70 | 0.80 |
|---|---|---|---|---|---|---|
| fifo | 1781552 | 1754287 | 1710422 | 1810253 | 1605600 | 1555291 |
| prio | 1776666 | 1738964 | 1710632 | 1661601 | 1606722 | 1627623 |
| hinted | 1791137 | 1757426 | 1684350 | 1693739 | 1609740 | 1555858 |
| hinted+rx | 1783920 | 1758429 | 1712843 | 1660469 | 1607961 | 1824836 |

## Mean-wait check (pre-registered)

dwait = growth of the kind's mean latency over rho 0.30, net of the change in its handler time, paired by repeat; predicted = pred(rho) - pred(0.30) pooled / per core.

| config | rho | short dwait meas (pooled / per core) ok | long dwait meas (pooled / per core) ok |
|---|---|---|---|
| fifo | 0.80 | 22.9 (13.6 / 66) NO | 22.7 (13.6 / 66) NO |
| prio | 0.80 | 4805.2 (3.4 / 13) NO | 5010.8 (17.8 / 88) NO |
| hinted | 0.80 | 14.3 (3.4 / 13) NO | 26.0 (17.8 / 88) yes |
| hinted+rx | 0.80 | 34135.6 (3.4 / 13) NO | 35632.6 (17.8 / 88) NO |

Pre-registered check passes in 1 of 6 cells (policies without +rx).

