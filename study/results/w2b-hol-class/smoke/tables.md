# w2b-hol-class, session smoke

Class only: short requests HIGH, long NORMAL

Scored kinds: short (SLO short 100 us). Price: long. 1 repeats; configurations in ladder order.

## SLO-load

Highest rho at which every scored kind's p99 <= its SLO, per repeat (>= means it never crossed within the grid). Compared by the paired rule; when the SLO-load cannot decide because of the grid top, by the worst scored p99/SLO at rho 0.90.

| config | SLO-load (median) | per repeat | worst p99/SLO at top | vs fifo | vs the rung below |
|---|---|---|---|---|---|
| fifo | 0.72 | 0.72 | 3.69 |  |  |
| hinted+rx | >=0.90 | >=0.90 | 0.60 | better on SLO-load (1.25) |  |

## rho = 0.80

p99 per kind (median of repeats), its ratio to the SLO, mean wait (mean minus min latency) and the predicted mean wait (pooled / per core).

| config | short p99 | short wait (pred) | long p99 | long wait (pred) |
|---|---|---|---|---|
| fifo | 145 (1.45) | 18.9 (13.8/74) | 191 (0.35) | 18.9 (13.8/74) |
| hinted+rx | 58 (0.58) | 11.5 (3.6/19) | 227 (0.41) | 22.8 (18.0/97) |

Price at rho 0.80: unscored kinds' p99 against fifo (paired).

- hinted+rx, long: higher (1.19)

## rho = 0.85

p99 per kind (median of repeats), its ratio to the SLO, mean wait (mean minus min latency) and the predicted mean wait (pooled / per core).

| config | short p99 | short wait (pred) | long p99 | long wait (pred) |
|---|---|---|---|---|
| fifo | 203 (2.03) | 28.8 (21.3/105) | 250 (0.45) | 29.2 (21.3/105) |
| hinted+rx | 59 (0.59) | 14.8 (4.3/21) | 322 (0.59) | 37.7 (28.4/140) |

Price at rho 0.85: unscored kinds' p99 against fifo (paired).

- hinted+rx, long: higher (1.29)

## rho = 0.90

p99 per kind (median of repeats), its ratio to the SLO, mean wait (mean minus min latency) and the predicted mean wait (pooled / per core).

| config | short p99 | short wait (pred) | long p99 | long wait (pred) |
|---|---|---|---|---|
| fifo | 369 (3.69) | 57.3 (36.5/167) | 414 (0.75) | 58.7 (36.5/167) |
| hinted+rx | 60 (0.60) | 18.9 (5.0/23) | 582 (1.06) | 76.5 (49.6/227) |

Price at rho 0.90: unscored kinds' p99 against fifo (paired).

- hinted+rx, long: higher (1.41)

## Where the time goes at rho = 0.90 (us; mean over repeats)

lag = client send minus schedule; in = send to server enqueue (delivery and RX-queue wait, plus classification); rq = runqueue; svc = handler; out = reply path; thread stolen = the handler ran on another kthread than the one that queued it; packet stolen = the packet was processed by another kthread than the owner of its RX queue.

| config | kind | part | lag | in | rq | svc | out | thread stolen % | packet stolen % |
|---|---|---|---|---|---|---|---|---|---|
| fifo | short | mean | -4.2 | 19.2 | 38.4 | 5.1 | 2.1 | 15 | - |
| fifo | short | tail99 | -4.2 | 35.0 | 441.6 | 5.1 | 2.1 | 19 | - |
| fifo | long | mean | -4.2 | 19.3 | 38.6 | 50.1 | 2.1 | 15 | - |
| fifo | long | tail99 | -4.2 | 35.4 | 440.6 | 51.0 | 2.1 | 19 | - |
| hinted+rx | short | mean | -4.1 | 14.1 | 5.1 | 5.1 | 2.1 | 6 | - |
| hinted+rx | short | tail99 | -4.0 | 44.9 | 12.8 | 5.6 | 2.5 | 4 | - |
| hinted+rx | long | mean | -4.1 | 14.1 | 62.5 | 50.2 | 2.2 | 23 | - |
| hinted+rx | long | tail99 | -4.1 | 19.9 | 682.0 | 53.4 | 2.2 | 18 | - |

