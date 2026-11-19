# w6-mixed-hints, session v2

Every hint given, class and deadline disagree: NORMAL bulk work due before HIGH loose requests

Scored kinds: tight, loose (SLO tight 100 us, loose 300 us). Price: bulk. 3 repeats; configurations in ladder order.

## SLO-load

Highest rho at which every scored kind's p99 <= its SLO, per repeat (>= means it never crossed within the grid). Compared by the paired rule; when the SLO-load cannot decide because of the grid top, by the worst scored p99/SLO at rho 0.90.

| config | SLO-load (median) | per repeat | worst p99/SLO at top | vs fifo | vs the rung below |
|---|---|---|---|---|---|
| fifo | 0.72 | 0.72, 0.72, 0.72 | 3.45 |  |  |
| fifo+rx | 0.72 | 0.72, 0.72, 0.72 | 3.91 | tie on SLO-load (0.99, 0.99, 0.99) | tie on SLO-load (0.99, 0.99, 0.99) |
| prio | >=0.90 | >=0.90, >=0.90, >=0.90 | 0.85 | better on SLO-load (1.24, 1.24, 1.24) | better on SLO-load (1.24, 1.24, 1.24) |
| prio+rx | >=0.90 | >=0.90, >=0.90, >=0.90 | 0.60 | better on SLO-load (1.24, 1.24, 1.24) | better on p99/SLO at top load (0.71, 0.71, 0.71) |
| prio_edf | >=0.90 | >=0.90, >=0.90, >=0.90 | 0.82 | better on SLO-load (1.24, 1.24, 1.24) | tie on p99/SLO at top load (0.96, 0.96, 0.96) |
| prio_edf+rx | >=0.90 | >=0.90, >=0.90, >=0.90 | 0.58 | better on SLO-load (1.24, 1.24, 1.24) | better on p99/SLO at top load (0.71, 0.71, 0.71) |
| hinted | >=0.90 | >=0.90, >=0.90, >=0.90 | 0.82 | better on SLO-load (1.24, 1.24, 1.24) | tie on p99/SLO at top load (1.00, 1.00, 1.00) |
| hinted+rx | >=0.90 | >=0.90, >=0.90, >=0.90 | 0.58 | better on SLO-load (1.24, 1.24, 1.24) | better on p99/SLO at top load (0.71, 0.71, 0.71) |
| edf | 0.73 | 0.73, 0.73, 0.73 | 3.33 | tie on SLO-load (1.01, 1.01, 1.01) | worse on SLO-load (0.81, 0.82, 0.81) |
| edf+rx | 0.73 | 0.73, 0.73, 0.73 | 3.44 | tie on SLO-load (1.00, 1.01, 1.01) | worse on SLO-load (0.81, 0.81, 0.81) |

## rho = 0.80

p99 per kind (median of repeats), its ratio to the SLO, mean wait (mean minus min latency) and the predicted mean wait (pooled / per core).

| config | tight p99 | tight wait (pred) | loose p99 | loose wait (pred) | bulk p99 | bulk wait (pred) |
|---|---|---|---|---|---|---|
| fifo | 145 (1.45) | 19.2 (13.8/74) | 143 (0.48) | 19.1 (13.8/74) | 190 (1.90) | 19.2 (13.8/74) |
| fifo+rx | 151 (1.51) | 19.7 (13.8/74) | 150 (0.50) | 19.6 (13.8/74) | 196 (1.96) | 19.7 (13.8/74) |
| prio | 71 (0.71) | 13.2 (3.6/19) | 71 (0.24) | 13.3 (3.6/19) | 224 (2.24) | 21.7 (18.0/97) |
| prio+rx | 58 (0.58) | 11.7 (3.6/19) | 58 (0.19) | 11.7 (3.6/19) | 231 (2.31) | 23.3 (18.0/97) |
| prio_edf | 69 (0.69) | 11.8 (2.9/16) | 75 (0.25) | 14.0 (3.8/21) | 227 (2.27) | 22.2 (18.0/97) |
| prio_edf+rx | 57 (0.57) | 9.9 (2.9/16) | 62 (0.21) | 12.4 (3.8/21) | 235 (2.35) | 23.7 (18.0/97) |
| hinted | 68 (0.68) | 11.8 (2.9/16) | 75 (0.25) | 13.9 (3.8/21) | 221 (2.21) | 21.6 (18.0/97) |
| hinted+rx | 57 (0.57) | 9.8 (2.9/16) | 62 (0.21) | 12.3 (3.8/21) | 232 (2.32) | 23.1 (18.0/97) |
| edf | 134 (1.34) | 17.4 (7.3/39) | 263 (0.88) | 26.8 (36.7/197) | 180 (1.80) | 17.5 (7.3/39) |
| edf+rx | 139 (1.39) | 17.3 (7.3/39) | 284 (0.95) | 30.5 (36.7/197) | 184 (1.84) | 17.5 (7.3/39) |

Price at rho 0.80: unscored kinds' p99 against fifo (paired).

- fifo+rx, bulk: tie (1.00, 1.02, 1.04)
- prio, bulk: higher (1.14, 1.17, 1.18)
- prio+rx, bulk: higher (1.17, 1.25, 1.22)
- prio_edf, bulk: higher (1.10, 1.22, 1.19)
- prio_edf+rx, bulk: higher (1.20, 1.25, 1.23)
- hinted, bulk: higher (1.16, 1.16, 1.15)
- hinted+rx, bulk: higher (1.17, 1.24, 1.22)
- edf, bulk: inconclusive (0.91, 0.95, 0.96)
- edf+rx, bulk: inconclusive (0.94, 0.98, 0.96)

## rho = 0.85

p99 per kind (median of repeats), its ratio to the SLO, mean wait (mean minus min latency) and the predicted mean wait (pooled / per core).

| config | tight p99 | tight wait (pred) | loose p99 | loose wait (pred) | bulk p99 | bulk wait (pred) |
|---|---|---|---|---|---|---|
| fifo | 215 (2.15) | 31.1 (21.3/105) | 218 (0.73) | 31.2 (21.3/105) | 263 (2.63) | 31.3 (21.3/105) |
| fifo+rx | 223 (2.23) | 31.6 (21.3/105) | 222 (0.74) | 31.5 (21.3/105) | 268 (2.68) | 31.6 (21.3/105) |
| prio | 78 (0.78) | 17.8 (4.3/21) | 78 (0.26) | 17.8 (4.3/21) | 299 (2.99) | 34.0 (28.4/140) |
| prio+rx | 59 (0.59) | 14.7 (4.3/21) | 59 (0.20) | 14.8 (4.3/21) | 329 (3.29) | 38.3 (28.4/140) |
| prio_edf | 75 (0.75) | 15.6 (3.4/17) | 83 (0.28) | 18.7 (4.5/22) | 313 (3.13) | 35.3 (28.4/140) |
| prio_edf+rx | 58 (0.58) | 12.1 (3.4/17) | 65 (0.22) | 15.7 (4.5/22) | 322 (3.22) | 37.8 (28.4/140) |
| hinted | 75 (0.75) | 15.6 (3.4/17) | 83 (0.28) | 18.9 (4.5/22) | 308 (3.08) | 35.0 (28.4/140) |
| hinted+rx | 58 (0.58) | 12.4 (3.4/17) | 65 (0.22) | 16.0 (4.5/22) | 330 (3.30) | 39.6 (28.4/140) |
| edf | 197 (1.97) | 27.2 (9.5/47) | 368 (1.23) | 45.9 (63.1/311) | 242 (2.42) | 27.3 (9.5/47) |
| edf+rx | 194 (1.94) | 26.3 (9.5/47) | 375 (1.25) | 51.7 (63.1/311) | 245 (2.45) | 26.5 (9.5/47) |

Price at rho 0.85: unscored kinds' p99 against fifo (paired).

- fifo+rx, bulk: inconclusive (1.07, 0.96, 1.03)
- prio, bulk: higher (1.20, 1.14, 1.06)
- prio+rx, bulk: higher (1.32, 1.16, 1.25)
- prio_edf, bulk: higher (1.26, 1.16, 1.17)
- prio_edf+rx, bulk: higher (1.29, 1.21, 1.21)
- hinted, bulk: higher (1.30, 1.11, 1.17)
- hinted+rx, bulk: higher (1.42, 1.22, 1.23)
- edf, bulk: inconclusive (0.96, 0.90, 0.96)
- edf+rx, bulk: inconclusive (0.99, 0.89, 0.93)

## rho = 0.90

p99 per kind (median of repeats), its ratio to the SLO, mean wait (mean minus min latency) and the predicted mean wait (pooled / per core).

| config | tight p99 | tight wait (pred) | loose p99 | loose wait (pred) | bulk p99 | bulk wait (pred) |
|---|---|---|---|---|---|---|
| fifo | 345 (3.45) | 55.6 (36.5/167) | 347 (1.16) | 55.4 (36.5/167) | 391 (3.91) | 55.5 (36.5/167) |
| fifo+rx | 391 (3.91) | 61.3 (36.5/167) | 394 (1.31) | 61.5 (36.5/167) | 437 (4.37) | 61.6 (36.5/167) |
| prio | 85 (0.85) | 25.4 (5.0/23) | 85 (0.28) | 25.4 (5.0/23) | 505 (5.05) | 67.8 (49.6/227) |
| prio+rx | 60 (0.60) | 19.1 (5.0/23) | 60 (0.20) | 19.2 (5.0/23) | 561 (5.61) | 77.5 (49.6/227) |
| prio_edf | 82 (0.82) | 21.7 (3.9/18) | 91 (0.30) | 26.6 (5.3/24) | 508 (5.08) | 68.3 (49.6/227) |
| prio_edf+rx | 58 (0.58) | 15.3 (3.9/18) | 68 (0.23) | 20.5 (5.3/24) | 553 (5.53) | 76.3 (49.6/227) |
| hinted | 82 (0.82) | 21.6 (3.9/18) | 91 (0.30) | 26.4 (5.3/24) | 491 (4.91) | 65.8 (49.6/227) |
| hinted+rx | 58 (0.58) | 15.3 (3.9/18) | 68 (0.23) | 20.3 (5.3/24) | 519 (5.19) | 72.5 (49.6/227) |
| edf | 333 (3.33) | 49.4 (12.2/56) | 539 (1.80) | 90.6 (122.3/559) | 383 (3.83) | 49.3 (12.2/56) |
| edf+rx | 344 (3.44) | 49.1 (12.2/56) | 551 (1.84) | 102.4 (122.3/559) | 392 (3.92) | 49.2 (12.2/56) |

Price at rho 0.90: unscored kinds' p99 against fifo (paired).

- fifo+rx, bulk: higher (1.05, 1.12, 1.12)
- prio, bulk: higher (1.27, 1.33, 1.29)
- prio+rx, bulk: higher (1.37, 1.46, 1.43)
- prio_edf, bulk: higher (1.35, 1.28, 1.30)
- prio_edf+rx, bulk: higher (1.40, 1.58, 1.41)
- hinted, bulk: higher (1.25, 1.25, 1.26)
- hinted+rx, bulk: higher (1.34, 1.37, 1.30)
- edf, bulk: tie (0.99, 0.98, 0.96)
- edf+rx, bulk: tie (1.00, 1.03, 1.00)

## Where the time goes at rho = 0.90 (us; mean over repeats)

lag = client send minus schedule; in = send to server enqueue (delivery and RX-queue wait, plus classification); rq = runqueue; svc = handler; out = reply path; thread stolen = the handler ran on another kthread than the one that queued it; packet stolen = the packet was processed by another kthread than the owner of its RX queue.

| config | kind | part | lag | in | rq | svc | out | thread stolen % | packet stolen % |
|---|---|---|---|---|---|---|---|---|---|
| fifo | tight | mean | -4.2 | 19.3 | 36.5 | 5.1 | 2.1 | 15 | 24 |
| fifo | tight | tail99 | -4.1 | 37.5 | 399.6 | 5.1 | 2.1 | 23 | 0 |
| fifo | loose | mean | -4.2 | 19.3 | 36.4 | 5.1 | 2.1 | 15 | 24 |
| fifo | loose | tail99 | -4.2 | 37.3 | 399.0 | 5.2 | 2.2 | 22 | 0 |
| fifo | bulk | mean | -4.2 | 19.4 | 36.4 | 50.2 | 2.2 | 15 | 24 |
| fifo | bulk | tail99 | -4.1 | 37.2 | 397.6 | 52.4 | 2.2 | 23 | 0 |
| fifo+rx | tight | mean | -4.2 | 14.7 | 46.1 | 5.1 | 2.1 | 17 | 20 |
| fifo+rx | tight | tail99 | -4.2 | 24.3 | 453.2 | 5.1 | 2.1 | 18 | 0 |
| fifo+rx | loose | mean | -4.2 | 14.8 | 46.1 | 5.1 | 2.1 | 17 | 20 |
| fifo+rx | loose | tail99 | -4.2 | 24.6 | 452.0 | 5.1 | 2.2 | 19 | 0 |
| fifo+rx | bulk | mean | -4.2 | 14.8 | 46.0 | 50.2 | 2.2 | 16 | 20 |
| fifo+rx | bulk | tail99 | -4.2 | 24.1 | 447.2 | 52.5 | 2.2 | 19 | 0 |
| prio | tight | mean | -4.2 | 20.4 | 5.4 | 5.1 | 2.1 | 7 | 26 |
| prio | tight | tail99 | -4.1 | 78.1 | 8.0 | 5.6 | 2.6 | 2 | 1 |
| prio | loose | mean | -4.2 | 20.4 | 5.4 | 5.1 | 2.1 | 7 | 26 |
| prio | loose | tail99 | -4.1 | 78.4 | 8.2 | 5.9 | 2.6 | 2 | 1 |
| prio | bulk | mean | -4.2 | 20.4 | 49.0 | 50.2 | 2.2 | 20 | 26 |
| prio | bulk | tail99 | -4.2 | 37.4 | 537.7 | 52.1 | 2.2 | 25 | 0 |
| prio+rx | tight | mean | -4.2 | 14.3 | 5.2 | 5.1 | 2.1 | 7 | 22 |
| prio+rx | tight | tail99 | -4.1 | 44.0 | 13.6 | 5.6 | 2.5 | 4 | 1 |
| prio+rx | loose | mean | -4.2 | 14.3 | 5.2 | 5.1 | 2.1 | 7 | 22 |
| prio+rx | loose | tail99 | -4.1 | 44.6 | 13.7 | 5.9 | 2.5 | 4 | 1 |
| prio+rx | bulk | mean | -4.2 | 14.3 | 62.6 | 50.2 | 2.2 | 24 | 22 |
| prio+rx | bulk | tail99 | -4.1 | 19.8 | 620.3 | 51.8 | 2.1 | 24 | 0 |
| prio_edf | tight | mean | -4.2 | 20.3 | 1.7 | 5.1 | 2.1 | 4 | 26 |
| prio_edf | tight | tail99 | -4.1 | 81.2 | 2.7 | 5.6 | 2.4 | 1 | 1 |
| prio_edf | loose | mean | -4.2 | 20.3 | 6.6 | 5.1 | 2.1 | 8 | 26 |
| prio_edf | loose | tail99 | -4.1 | 76.3 | 17.2 | 5.9 | 2.5 | 3 | 1 |
| prio_edf | bulk | mean | -4.2 | 20.3 | 48.4 | 50.2 | 2.2 | 20 | 26 |
| prio_edf | bulk | tail99 | -4.2 | 37.1 | 551.0 | 50.7 | 2.1 | 24 | 0 |
| prio_edf+rx | tight | mean | -4.2 | 14.3 | 1.3 | 5.1 | 2.1 | 4 | 22 |
| prio_edf+rx | tight | tail99 | -4.0 | 51.3 | 3.1 | 5.9 | 2.7 | 1 | 1 |
| prio_edf+rx | loose | mean | -4.1 | 14.3 | 6.5 | 5.1 | 2.1 | 8 | 22 |
| prio_edf+rx | loose | tail99 | -4.1 | 44.8 | 23.4 | 5.7 | 2.5 | 5 | 1 |
| prio_edf+rx | bulk | mean | -4.1 | 14.3 | 63.9 | 50.2 | 2.2 | 23 | 22 |
| prio_edf+rx | bulk | tail99 | -4.1 | 19.8 | 659.2 | 50.5 | 2.1 | 23 | 0 |
| hinted | tight | mean | -4.2 | 20.1 | 1.7 | 5.1 | 2.1 | 4 | 26 |
| hinted | tight | tail99 | -4.1 | 80.4 | 2.5 | 5.7 | 2.3 | 1 | 1 |
| hinted | loose | mean | -4.2 | 20.1 | 6.6 | 5.1 | 2.1 | 8 | 26 |
| hinted | loose | tail99 | -4.1 | 76.1 | 17.0 | 5.8 | 2.5 | 4 | 1 |
| hinted | bulk | mean | -4.2 | 20.1 | 46.0 | 50.2 | 2.2 | 20 | 26 |
| hinted | bulk | tail99 | -4.2 | 37.1 | 532.1 | 50.5 | 2.1 | 24 | 0 |
| hinted+rx | tight | mean | -4.2 | 14.2 | 1.3 | 5.1 | 2.1 | 4 | 22 |
| hinted+rx | tight | tail99 | -4.0 | 51.8 | 2.8 | 5.7 | 2.6 | 1 | 1 |
| hinted+rx | loose | mean | -4.2 | 14.2 | 6.5 | 5.1 | 2.1 | 8 | 22 |
| hinted+rx | loose | tail99 | -4.1 | 45.0 | 22.9 | 5.8 | 2.5 | 5 | 1 |
| hinted+rx | bulk | mean | -4.2 | 14.2 | 58.5 | 50.2 | 2.2 | 24 | 22 |
| hinted+rx | bulk | tail99 | -4.2 | 19.0 | 583.7 | 50.4 | 2.1 | 28 | 0 |
| edf | tight | mean | -4.2 | 18.4 | 31.7 | 5.1 | 2.1 | 11 | 21 |
| edf | tight | tail99 | -4.1 | 33.8 | 399.2 | 5.2 | 2.2 | 15 | 0 |
| edf | loose | mean | -4.2 | 18.4 | 73.3 | 5.1 | 2.2 | 27 | 21 |
| edf | loose | tail99 | -4.2 | 36.4 | 607.9 | 5.1 | 2.2 | 24 | 0 |
| edf | bulk | mean | -4.2 | 18.4 | 31.6 | 50.2 | 2.2 | 10 | 21 |
| edf | bulk | tail99 | -4.1 | 34.3 | 400.7 | 50.9 | 2.2 | 16 | 0 |
| edf+rx | tight | mean | -4.1 | 15.1 | 34.5 | 5.1 | 2.2 | 10 | 19 |
| edf+rx | tight | tail99 | -4.2 | 27.8 | 416.6 | 5.1 | 2.3 | 15 | 0 |
| edf+rx | loose | mean | -4.2 | 15.1 | 87.7 | 5.1 | 2.2 | 30 | 19 |
| edf+rx | loose | tail99 | -4.2 | 28.3 | 625.5 | 5.1 | 2.2 | 23 | 0 |
| edf+rx | bulk | mean | -4.1 | 15.1 | 34.5 | 50.2 | 2.2 | 10 | 19 |
| edf+rx | bulk | tail99 | -4.1 | 27.8 | 419.1 | 50.8 | 2.2 | 15 | 0 |

## Mean-wait check (pre-registered)

dwait = growth of the kind's mean latency over rho 0.50, net of the change in its handler time, paired by repeat; predicted = pred(rho) - pred(0.50) pooled / per core.

| config | rho | tight dwait meas (pooled / per core) ok | loose dwait meas (pooled / per core) ok | bulk dwait meas (pooled / per core) ok |
|---|---|---|---|---|
| fifo | 0.80 | 15.8 (12.2 / 56) NO | 15.7 (12.2 / 56) NO | 15.7 (12.2 / 56) NO |
| fifo | 0.85 | 27.7 (19.7 / 86) NO | 27.8 (19.7 / 86) NO | 27.8 (19.7 / 86) NO |
| fifo | 0.90 | 52.2 (34.9 / 148) NO | 52.0 (34.9 / 148) NO | 51.9 (34.9 / 148) NO |
| fifo+rx | 0.80 | 16.2 (12.2 / 56) NO | 16.1 (12.2 / 56) NO | 16.1 (12.2 / 56) NO |
| fifo+rx | 0.85 | 28.1 (19.7 / 86) NO | 27.9 (19.7 / 86) NO | 28.0 (19.7 / 86) NO |
| fifo+rx | 0.90 | 57.7 (34.9 / 148) NO | 58.0 (34.9 / 148) NO | 57.9 (34.9 / 148) NO |
| prio | 0.80 | 10.0 (2.7 / 9) NO | 10.1 (2.7 / 9) NO | 18.0 (16.2 / 75) yes |
| prio | 0.85 | 14.5 (3.3 / 10) NO | 14.5 (3.3 / 10) NO | 30.3 (26.5 / 118) yes |
| prio | 0.90 | 22.2 (4.0 / 12) NO | 22.2 (4.0 / 12) NO | 64.2 (47.7 / 205) yes |
| prio+rx | 0.80 | 8.5 (2.7 / 9) yes | 8.5 (2.7 / 9) yes | 19.6 (16.2 / 75) yes |
| prio+rx | 0.85 | 11.5 (3.3 / 10) NO | 11.5 (3.3 / 10) NO | 34.4 (26.5 / 118) yes |
| prio+rx | 0.90 | 15.9 (4.0 / 12) NO | 16.0 (4.0 / 12) NO | 73.6 (47.7 / 205) yes |
| prio_edf | 0.80 | 8.7 (2.1 / 6) NO | 10.7 (2.9 / 9) NO | 18.5 (16.2 / 75) yes |
| prio_edf | 0.85 | 12.5 (2.6 / 7) NO | 15.4 (3.6 / 11) NO | 31.6 (26.5 / 118) yes |
| prio_edf | 0.90 | 18.6 (3.1 / 8) NO | 23.3 (4.3 / 13) NO | 64.6 (47.7 / 205) yes |
| prio_edf+rx | 0.80 | 6.8 (2.1 / 6) NO | 9.0 (2.9 / 9) yes | 19.9 (16.2 / 75) yes |
| prio_edf+rx | 0.85 | 9.1 (2.6 / 7) NO | 12.4 (3.6 / 11) NO | 33.9 (26.5 / 118) yes |
| prio_edf+rx | 0.90 | 12.3 (3.1 / 8) NO | 17.3 (4.3 / 13) NO | 72.5 (47.7 / 205) yes |
| hinted | 0.80 | 8.7 (2.1 / 6) NO | 10.6 (2.9 / 9) NO | 17.9 (16.2 / 75) yes |
| hinted | 0.85 | 12.6 (2.6 / 7) NO | 15.5 (3.6 / 11) NO | 31.3 (26.5 / 118) yes |
| hinted | 0.90 | 18.5 (3.1 / 8) NO | 23.2 (4.3 / 13) NO | 62.1 (47.7 / 205) yes |
| hinted+rx | 0.80 | 6.8 (2.1 / 6) NO | 9.0 (2.9 / 9) yes | 19.3 (16.2 / 75) yes |
| hinted+rx | 0.85 | 9.4 (2.6 / 7) NO | 12.8 (3.6 / 11) NO | 35.8 (26.5 / 118) yes |
| hinted+rx | 0.90 | 12.2 (3.1 / 8) NO | 17.1 (4.3 / 13) NO | 68.7 (47.7 / 205) yes |
| edf | 0.80 | 14.1 (6.0 / 24) yes | 23.1 (34.1 / 167) NO | 14.1 (6.0 / 24) yes |
| edf | 0.85 | 24.0 (8.1 / 31) yes | 42.2 (60.4 / 281) NO | 23.8 (8.1 / 31) yes |
| edf | 0.90 | 46.1 (10.9 / 41) NO | 86.9 (119.6 / 528) NO | 46.0 (10.9 / 41) NO |
| edf+rx | 0.80 | 13.9 (6.0 / 24) yes | 26.6 (34.1 / 167) NO | 14.1 (6.0 / 24) yes |
| edf+rx | 0.85 | 23.0 (8.1 / 31) yes | 47.9 (60.4 / 281) NO | 23.0 (8.1 / 31) yes |
| edf+rx | 0.90 | 45.8 (10.9 / 41) NO | 98.6 (119.6 / 528) NO | 45.8 (10.9 / 41) NO |

Pre-registered check passes in 13 of 45 cells (policies without +rx).

