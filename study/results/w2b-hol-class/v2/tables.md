# w2b-hol-class, session v2

Class only: short requests HIGH, long NORMAL

Scored kinds: short (SLO short 100 us). Price: long. 3 repeats; configurations in ladder order.

## SLO-load

Highest rho at which every scored kind's p99 <= its SLO, per repeat (>= means it never crossed within the grid). Compared by the paired rule; when the SLO-load cannot decide because of the grid top, by the worst scored p99/SLO at rho 0.90.

| config | SLO-load (median) | per repeat | worst p99/SLO at top | vs fifo | vs the rung below |
|---|---|---|---|---|---|
| fifo | 0.72 | 0.73, 0.72, 0.72 | 3.49 |  |  |
| fifo+rx | 0.72 | 0.72, 0.72, 0.72 | 3.66 | tie on SLO-load (0.99, 1.00, 1.00) | tie on SLO-load (0.99, 1.00, 1.00) |
| prio | >=0.90 | >=0.90, >=0.90, >=0.90 | 0.84 | better on SLO-load (1.24, 1.25, 1.25) | better on SLO-load (1.24, 1.25, 1.25) |
| prio+rx | >=0.90 | >=0.90, >=0.90, >=0.90 | 0.60 | better on SLO-load (1.24, 1.25, 1.25) | better on p99/SLO at top load (0.71, 0.71, 0.71) |
| prio_edf | >=0.90 | >=0.90, >=0.90, >=0.90 | 0.85 | better on SLO-load (1.24, 1.25, 1.25) | tie on p99/SLO at top load (1.00, 1.01, 1.01) |
| prio_edf+rx | >=0.90 | >=0.90, >=0.90, >=0.90 | 0.60 | better on SLO-load (1.24, 1.25, 1.25) | better on p99/SLO at top load (0.71, 0.71, 0.71) |
| hinted | >=0.90 | >=0.90, >=0.90, >=0.90 | 0.84 | better on SLO-load (1.24, 1.25, 1.25) | tie on p99/SLO at top load (1.00, 0.99, 0.99) |
| hinted+rx | >=0.90 | >=0.90, >=0.90, >=0.90 | 0.60 | better on SLO-load (1.24, 1.25, 1.25) | better on p99/SLO at top load (0.71, 0.71, 0.71) |
| edf | 0.72 | 0.72, 0.72, 0.72 | 3.37 | tie on SLO-load (0.99, 1.00, 1.00) | worse on SLO-load (0.80, 0.80, 0.80) |
| edf+rx | 0.72 | 0.72, 0.72, 0.72 | 3.85 | tie on SLO-load (1.00, 1.00, 0.99) | worse on SLO-load (0.80, 0.80, 0.80) |

## rho = 0.80

p99 per kind (median of repeats), its ratio to the SLO, mean wait (mean minus min latency) and the predicted mean wait (pooled / per core).

| config | short p99 | short wait (pred) | long p99 | long wait (pred) |
|---|---|---|---|---|
| fifo | 147 (1.47) | 19.2 (13.8/74) | 194 (0.35) | 19.2 (13.8/74) |
| fifo+rx | 150 (1.50) | 19.9 (13.8/74) | 197 (0.36) | 20.0 (13.8/74) |
| prio | 70 (0.70) | 13.1 (3.6/19) | 216 (0.39) | 21.1 (18.0/97) |
| prio+rx | 58 (0.58) | 11.6 (3.6/19) | 224 (0.41) | 23.0 (18.0/97) |
| prio_edf | 71 (0.71) | 13.2 (3.6/19) | 224 (0.41) | 21.6 (18.0/97) |
| prio_edf+rx | 58 (0.58) | 11.7 (3.6/19) | 230 (0.42) | 23.0 (18.0/97) |
| hinted | 71 (0.71) | 13.2 (3.6/19) | 229 (0.42) | 22.2 (18.0/97) |
| hinted+rx | 58 (0.58) | 11.7 (3.6/19) | 230 (0.42) | 23.2 (18.0/97) |
| edf | 146 (1.46) | 19.1 (13.8/74) | 193 (0.35) | 19.1 (13.8/74) |
| edf+rx | 149 (1.49) | 19.7 (13.8/74) | 195 (0.35) | 19.9 (13.8/74) |

Price at rho 0.80: unscored kinds' p99 against fifo (paired).

- fifo+rx, long: inconclusive (1.06, 0.99, 1.02)
- prio, long: higher (1.14, 1.16, 1.09)
- prio+rx, long: higher (1.19, 1.17, 1.15)
- prio_edf, long: higher (1.19, 1.14, 1.12)
- prio_edf+rx, long: higher (1.22, 1.18, 1.18)
- hinted, long: higher (1.21, 1.10, 1.20)
- hinted+rx, long: higher (1.22, 1.16, 1.25)
- edf, long: tie (1.01, 0.98, 1.01)
- edf+rx, long: tie (1.02, 1.00, 1.01)

## rho = 0.85

p99 per kind (median of repeats), its ratio to the SLO, mean wait (mean minus min latency) and the predicted mean wait (pooled / per core).

| config | short p99 | short wait (pred) | long p99 | long wait (pred) |
|---|---|---|---|---|
| fifo | 208 (2.08) | 29.5 (21.3/105) | 256 (0.47) | 29.6 (21.3/105) |
| fifo+rx | 220 (2.20) | 31.3 (21.3/105) | 265 (0.48) | 31.5 (21.3/105) |
| prio | 77 (0.77) | 17.6 (4.3/21) | 301 (0.55) | 33.9 (28.4/140) |
| prio+rx | 59 (0.59) | 14.7 (4.3/21) | 308 (0.56) | 36.7 (28.4/140) |
| prio_edf | 78 (0.78) | 17.8 (4.3/21) | 304 (0.55) | 34.4 (28.4/140) |
| prio_edf+rx | 59 (0.59) | 14.8 (4.3/21) | 321 (0.58) | 37.0 (28.4/140) |
| hinted | 78 (0.78) | 18.3 (4.3/21) | 323 (0.59) | 36.2 (28.4/140) |
| hinted+rx | 59 (0.59) | 14.7 (4.3/21) | 321 (0.58) | 36.7 (28.4/140) |
| edf | 212 (2.12) | 29.6 (21.3/105) | 258 (0.47) | 29.8 (21.3/105) |
| edf+rx | 214 (2.14) | 30.7 (21.3/105) | 260 (0.47) | 30.9 (21.3/105) |

Price at rho 0.85: unscored kinds' p99 against fifo (paired).

- fifo+rx, long: inconclusive (1.08, 1.02, 1.01)
- prio, long: higher (1.20, 1.15, 1.18)
- prio+rx, long: higher (1.23, 1.25, 1.18)
- prio_edf, long: higher (1.22, 1.18, 1.17)
- prio_edf+rx, long: higher (1.25, 1.23, 1.26)
- hinted, long: higher (1.29, 1.25, 1.23)
- hinted+rx, long: higher (1.24, 1.23, 1.29)
- edf, long: tie (1.02, 0.99, 1.03)
- edf+rx, long: tie (1.02, 1.00, 1.02)

## rho = 0.90

p99 per kind (median of repeats), its ratio to the SLO, mean wait (mean minus min latency) and the predicted mean wait (pooled / per core).

| config | short p99 | short wait (pred) | long p99 | long wait (pred) |
|---|---|---|---|---|
| fifo | 349 (3.49) | 54.6 (36.5/167) | 396 (0.72) | 55.0 (36.5/167) |
| fifo+rx | 366 (3.66) | 58.3 (36.5/167) | 413 (0.75) | 58.5 (36.5/167) |
| prio | 84 (0.84) | 24.8 (5.0/23) | 502 (0.91) | 65.6 (49.6/227) |
| prio+rx | 60 (0.60) | 19.1 (5.0/23) | 559 (1.02) | 77.3 (49.6/227) |
| prio_edf | 85 (0.85) | 25.4 (5.0/23) | 551 (1.00) | 70.2 (49.6/227) |
| prio_edf+rx | 60 (0.60) | 19.0 (5.0/23) | 525 (0.95) | 70.9 (49.6/227) |
| hinted | 84 (0.84) | 24.9 (5.0/23) | 501 (0.91) | 65.8 (49.6/227) |
| hinted+rx | 60 (0.60) | 18.8 (5.0/23) | 521 (0.95) | 69.7 (49.6/227) |
| edf | 337 (3.37) | 53.3 (36.5/167) | 385 (0.70) | 53.3 (36.5/167) |
| edf+rx | 385 (3.85) | 61.0 (36.5/167) | 427 (0.78) | 61.1 (36.5/167) |

Price at rho 0.90: unscored kinds' p99 against fifo (paired).

- fifo+rx, long: inconclusive (0.97, 1.04, 1.07)
- prio, long: higher (1.18, 1.18, 1.28)
- prio+rx, long: higher (1.14, 1.46, 1.44)
- prio_edf, long: higher (1.31, 1.44, 1.28)
- prio_edf+rx, long: higher (1.18, 1.42, 1.33)
- hinted, long: higher (1.18, 1.31, 1.24)
- hinted+rx, long: higher (1.19, 1.36, 1.36)
- edf, long: inconclusive (0.91, 1.01, 0.97)
- edf+rx, long: inconclusive (1.00, 1.22, 1.08)

## Where the time goes at rho = 0.90 (us; mean over repeats)

lag = client send minus schedule; in = send to server enqueue (delivery and RX-queue wait, plus classification); rq = runqueue; svc = handler; out = reply path; thread stolen = the handler ran on another kthread than the one that queued it; packet stolen = the packet was processed by another kthread than the owner of its RX queue.

| config | kind | part | lag | in | rq | svc | out | thread stolen % | packet stolen % |
|---|---|---|---|---|---|---|---|---|---|
| fifo | short | mean | -4.2 | 19.1 | 36.0 | 5.1 | 2.1 | 15 | 24 |
| fifo | short | tail99 | -4.2 | 35.4 | 420.3 | 5.1 | 2.2 | 22 | 0 |
| fifo | long | mean | -4.2 | 19.1 | 36.2 | 50.2 | 2.2 | 15 | 24 |
| fifo | long | tail99 | -4.2 | 35.5 | 419.6 | 52.2 | 2.2 | 21 | 0 |
| fifo+rx | short | mean | -4.2 | 14.7 | 43.5 | 5.1 | 2.1 | 17 | 21 |
| fifo+rx | short | tail99 | -4.1 | 27.1 | 444.3 | 5.2 | 2.2 | 20 | 0 |
| fifo+rx | long | mean | -4.2 | 14.7 | 43.4 | 50.2 | 2.2 | 17 | 21 |
| fifo+rx | long | tail99 | -4.2 | 28.8 | 439.3 | 52.2 | 2.2 | 20 | 0 |
| prio | short | mean | -4.2 | 19.9 | 5.3 | 5.1 | 2.1 | 7 | 27 |
| prio | short | tail99 | -4.1 | 77.9 | 8.2 | 5.9 | 2.5 | 2 | 1 |
| prio | long | mean | -4.2 | 19.9 | 45.4 | 50.2 | 2.2 | 20 | 26 |
| prio | long | tail99 | -4.2 | 36.8 | 518.8 | 51.8 | 2.2 | 25 | 0 |
| prio+rx | short | mean | -4.2 | 14.1 | 5.1 | 5.1 | 2.1 | 7 | 22 |
| prio+rx | short | tail99 | -4.1 | 44.4 | 13.4 | 5.9 | 2.6 | 4 | 1 |
| prio+rx | long | mean | -4.2 | 14.1 | 59.9 | 50.2 | 2.2 | 24 | 22 |
| prio+rx | long | tail99 | -4.2 | 19.6 | 614.5 | 51.9 | 2.1 | 25 | 0 |
| prio_edf | short | mean | -4.2 | 20.2 | 5.4 | 5.1 | 2.1 | 6 | 26 |
| prio_edf | short | tail99 | -4.1 | 78.0 | 8.4 | 5.8 | 2.5 | 2 | 1 |
| prio_edf | long | mean | -4.2 | 20.2 | 49.5 | 50.2 | 2.2 | 20 | 26 |
| prio_edf | long | tail99 | -4.2 | 37.1 | 610.2 | 51.3 | 2.1 | 22 | 0 |
| prio_edf+rx | short | mean | -4.2 | 14.1 | 5.1 | 5.1 | 2.1 | 7 | 22 |
| prio_edf+rx | short | tail99 | -4.0 | 44.4 | 13.7 | 5.8 | 2.6 | 4 | 1 |
| prio_edf+rx | long | mean | -4.2 | 14.1 | 57.9 | 50.2 | 2.2 | 24 | 22 |
| prio_edf+rx | long | tail99 | -4.2 | 19.8 | 579.0 | 52.4 | 2.2 | 25 | 0 |
| hinted | short | mean | -4.2 | 19.9 | 5.3 | 5.1 | 2.1 | 7 | 27 |
| hinted | short | tail99 | -4.1 | 77.9 | 8.4 | 5.8 | 2.5 | 2 | 1 |
| hinted | long | mean | -4.2 | 19.8 | 45.8 | 50.2 | 2.2 | 20 | 27 |
| hinted | long | tail99 | -4.2 | 36.7 | 555.0 | 52.2 | 2.1 | 25 | 0 |
| hinted+rx | short | mean | -4.2 | 14.1 | 5.1 | 5.1 | 2.1 | 7 | 23 |
| hinted+rx | short | tail99 | -4.1 | 44.9 | 13.5 | 5.8 | 2.6 | 4 | 2 |
| hinted+rx | long | mean | -4.2 | 14.0 | 57.0 | 50.2 | 2.2 | 24 | 23 |
| hinted+rx | long | tail99 | -4.2 | 20.0 | 583.4 | 51.9 | 2.1 | 22 | 0 |
| edf | short | mean | -4.2 | 19.0 | 34.7 | 5.1 | 2.1 | 16 | 24 |
| edf | short | tail99 | -4.1 | 34.6 | 396.6 | 5.2 | 2.2 | 22 | 0 |
| edf | long | mean | -4.2 | 19.0 | 34.5 | 50.2 | 2.2 | 15 | 24 |
| edf | long | tail99 | -4.2 | 34.6 | 392.8 | 53.2 | 2.2 | 22 | 0 |
| edf+rx | short | mean | -4.2 | 14.7 | 46.3 | 5.1 | 2.2 | 17 | 20 |
| edf+rx | short | tail99 | -4.2 | 25.1 | 473.8 | 5.1 | 2.2 | 20 | 0 |
| edf+rx | long | mean | -4.2 | 14.7 | 46.3 | 50.2 | 2.2 | 17 | 20 |
| edf+rx | long | tail99 | -4.2 | 25.3 | 471.8 | 51.5 | 2.2 | 20 | 0 |

## Mean-wait check (pre-registered)

dwait = growth of the kind's mean latency over rho 0.50, net of the change in its handler time, paired by repeat; predicted = pred(rho) - pred(0.50) pooled / per core.

| config | rho | short dwait meas (pooled / per core) ok | long dwait meas (pooled / per core) ok |
|---|---|---|---|
| fifo | 0.80 | 15.8 (12.2 / 56) NO | 15.8 (12.2 / 56) NO |
| fifo | 0.85 | 26.2 (19.7 / 86) NO | 26.2 (19.7 / 86) NO |
| fifo | 0.90 | 51.2 (34.9 / 148) NO | 51.6 (34.9 / 148) NO |
| fifo+rx | 0.80 | 16.5 (12.2 / 56) NO | 16.5 (12.2 / 56) NO |
| fifo+rx | 0.85 | 27.8 (19.7 / 86) NO | 27.9 (19.7 / 86) NO |
| fifo+rx | 0.90 | 54.9 (34.9 / 148) NO | 54.9 (34.9 / 148) NO |
| prio | 0.80 | 10.0 (2.7 / 9) NO | 17.5 (16.2 / 75) yes |
| prio | 0.85 | 14.5 (3.3 / 10) NO | 30.3 (26.5 / 118) yes |
| prio | 0.90 | 21.6 (4.0 / 12) NO | 61.9 (47.7 / 205) yes |
| prio+rx | 0.80 | 8.4 (2.7 / 9) yes | 19.3 (16.2 / 75) yes |
| prio+rx | 0.85 | 11.5 (3.3 / 10) NO | 32.9 (26.5 / 118) yes |
| prio+rx | 0.90 | 15.9 (4.0 / 12) NO | 73.6 (47.7 / 205) yes |
| prio_edf | 0.80 | 10.0 (2.7 / 9) NO | 17.9 (16.2 / 75) yes |
| prio_edf | 0.85 | 14.6 (3.3 / 10) NO | 30.7 (26.5 / 118) yes |
| prio_edf | 0.90 | 22.3 (4.0 / 12) NO | 66.5 (47.7 / 205) yes |
| prio_edf+rx | 0.80 | 8.5 (2.7 / 9) yes | 19.2 (16.2 / 75) yes |
| prio_edf+rx | 0.85 | 11.6 (3.3 / 10) NO | 33.1 (26.5 / 118) yes |
| prio_edf+rx | 0.90 | 15.8 (4.0 / 12) NO | 67.1 (47.7 / 205) yes |
| hinted | 0.80 | 10.0 (2.7 / 9) NO | 18.6 (16.2 / 75) yes |
| hinted | 0.85 | 15.1 (3.3 / 10) NO | 32.6 (26.5 / 118) yes |
| hinted | 0.90 | 21.6 (4.0 / 12) NO | 62.2 (47.7 / 205) yes |
| hinted+rx | 0.80 | 8.5 (2.7 / 9) yes | 19.4 (16.2 / 75) yes |
| hinted+rx | 0.85 | 11.4 (3.3 / 10) NO | 32.9 (26.5 / 118) yes |
| hinted+rx | 0.90 | 15.6 (4.0 / 12) NO | 65.9 (47.7 / 205) yes |
| edf | 0.80 | 15.7 (12.2 / 56) yes | 15.6 (12.2 / 56) yes |
| edf | 0.85 | 26.2 (19.7 / 86) yes | 26.3 (19.7 / 86) yes |
| edf | 0.90 | 49.9 (34.9 / 148) yes | 49.8 (34.9 / 148) yes |
| edf+rx | 0.80 | 16.2 (12.2 / 56) yes | 16.3 (12.2 / 56) yes |
| edf+rx | 0.85 | 27.3 (19.7 / 86) yes | 27.3 (19.7 / 86) yes |
| edf+rx | 0.90 | 57.5 (34.9 / 148) yes | 57.5 (34.9 / 148) yes |

Pre-registered check passes in 15 of 30 cells (policies without +rx).

