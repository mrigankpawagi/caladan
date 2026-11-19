# w4-wrong-hints, session v2

Wrong sizes: W2a with 10% of long requests claiming to be short

Scored kinds: short, long, liar (SLO short 100 us, long 550 us, liar 550 us). Price: none. 3 repeats; configurations in ladder order.

## SLO-load

Highest rho at which every scored kind's p99 <= its SLO, per repeat (>= means it never crossed within the grid). Compared by the paired rule; when the SLO-load cannot decide because of the grid top, by the worst scored p99/SLO at rho 0.90.

| config | SLO-load (median) | per repeat | worst p99/SLO at top | vs fifo | vs the rung below |
|---|---|---|---|---|---|
| fifo | 0.72 | 0.72, 0.72, 0.72 | 3.47 |  |  |
| prio | 0.72 | 0.72, 0.72, 0.72 | 3.67 | tie on SLO-load (1.00, 1.00, 0.99) | tie on SLO-load (1.00, 1.00, 0.99) |
| prio_edf | 0.72 | 0.72, 0.72, 0.72 | 3.66 | tie on SLO-load (1.00, 1.00, 1.00) | tie on SLO-load (1.00, 1.00, 1.00) |
| hinted | 0.90 | 0.90, >=0.90, >=0.90 | 0.96 | better on SLO-load (1.25, 1.25, 1.25) | better on SLO-load (1.25, 1.25, 1.25) |
| hinted+rx | 0.90 | 0.89, >=0.90, 0.90 | 1.03 | better on SLO-load (1.24, 1.25, 1.24) | tie on SLO-load (0.99, 1.00, 0.99) |
| edf | 0.72 | 0.72, 0.72, 0.72 | 3.64 | tie on SLO-load (1.00, 1.00, 1.00) | tie on SLO-load (1.00, 1.00, 1.00) |

## rho = 0.80

p99 per kind (median of repeats), its ratio to the SLO, mean wait (mean minus min latency) and the predicted mean wait (pooled / per core).

| config | short p99 | short wait (pred) | long p99 | long wait (pred) | liar p99 | liar wait (pred) |
|---|---|---|---|---|---|---|
| fifo | 144 (1.44) | 19.1 (13.8/74) | 188 (0.34) | 19.0 (13.8/74) | 190 (0.35) | 19.4 (13.8/74) |
| prio | 142 (1.42) | 18.7 (13.8/74) | 188 (0.34) | 18.7 (13.8/74) | 193 (0.35) | 18.7 (13.8/74) |
| prio_edf | 147 (1.47) | 19.2 (13.8/74) | 193 (0.35) | 19.2 (13.8/74) | 191 (0.35) | 19.1 (13.8/74) |
| hinted | 75 (0.75) | 13.7 (3.9/21) | 235 (0.43) | 22.7 (19.5/105) | 121 (0.22) | 13.8 (3.9/21) |
| hinted+rx | 62 (0.62) | 12.2 (3.9/21) | 249 (0.45) | 24.3 (19.5/105) | 107 (0.19) | 12.3 (3.9/21) |
| edf | 149 (1.49) | 19.3 (13.8/74) | 194 (0.35) | 19.5 (13.8/74) | 195 (0.35) | 19.3 (13.8/74) |

## rho = 0.85

p99 per kind (median of repeats), its ratio to the SLO, mean wait (mean minus min latency) and the predicted mean wait (pooled / per core).

| config | short p99 | short wait (pred) | long p99 | long wait (pred) | liar p99 | liar wait (pred) |
|---|---|---|---|---|---|---|
| fifo | 210 (2.10) | 30.2 (21.3/105) | 256 (0.47) | 30.2 (21.3/105) | 257 (0.47) | 30.1 (21.3/105) |
| prio | 205 (2.05) | 29.7 (21.3/105) | 251 (0.46) | 29.8 (21.3/105) | 251 (0.46) | 29.9 (21.3/105) |
| prio_edf | 207 (2.07) | 30.0 (21.3/105) | 253 (0.46) | 30.1 (21.3/105) | 251 (0.46) | 29.8 (21.3/105) |
| hinted | 85 (0.85) | 18.7 (4.6/23) | 323 (0.59) | 35.9 (30.8/152) | 131 (0.24) | 18.7 (4.6/23) |
| hinted+rx | 69 (0.69) | 15.7 (4.6/23) | 339 (0.62) | 39.2 (30.8/152) | 114 (0.21) | 15.7 (4.6/23) |
| edf | 211 (2.11) | 30.3 (21.3/105) | 256 (0.47) | 30.4 (21.3/105) | 256 (0.47) | 30.5 (21.3/105) |

## rho = 0.90

p99 per kind (median of repeats), its ratio to the SLO, mean wait (mean minus min latency) and the predicted mean wait (pooled / per core).

| config | short p99 | short wait (pred) | long p99 | long wait (pred) | liar p99 | liar wait (pred) |
|---|---|---|---|---|---|---|
| fifo | 347 (3.47) | 53.8 (36.5/167) | 393 (0.71) | 53.8 (36.5/167) | 391 (0.71) | 54.3 (36.5/167) |
| prio | 367 (3.67) | 57.2 (36.5/167) | 414 (0.75) | 57.6 (36.5/167) | 416 (0.76) | 57.3 (36.5/167) |
| prio_edf | 366 (3.66) | 57.0 (36.5/167) | 411 (0.75) | 57.2 (36.5/167) | 418 (0.76) | 57.0 (36.5/167) |
| hinted | 95 (0.95) | 26.2 (5.4/25) | 526 (0.96) | 67.3 (54.3/248) | 141 (0.26) | 26.3 (5.4/25) |
| hinted+rx | 80 (0.80) | 20.3 (5.4/25) | 567 (1.03) | 76.9 (54.3/248) | 125 (0.23) | 20.5 (5.4/25) |
| edf | 364 (3.64) | 55.8 (36.5/167) | 416 (0.76) | 56.5 (36.5/167) | 417 (0.76) | 56.6 (36.5/167) |

## Where the time goes at rho = 0.90 (us; mean over repeats)

lag = client send minus schedule; in = send to server enqueue (delivery and RX-queue wait, plus classification); rq = runqueue; svc = handler; out = reply path; thread stolen = the handler ran on another kthread than the one that queued it; packet stolen = the packet was processed by another kthread than the owner of its RX queue.

| config | kind | part | lag | in | rq | svc | out | thread stolen % | packet stolen % |
|---|---|---|---|---|---|---|---|---|---|
| fifo | short | mean | -4.2 | 18.9 | 35.2 | 5.1 | 2.1 | 15 | 24 |
| fifo | short | tail99 | -4.1 | 35.5 | 402.6 | 5.1 | 2.2 | 21 | 0 |
| fifo | long | mean | -4.2 | 18.9 | 35.1 | 50.2 | 2.2 | 15 | 24 |
| fifo | long | tail99 | -4.1 | 35.6 | 397.3 | 51.6 | 2.2 | 20 | 0 |
| fifo | liar | mean | -4.1 | 19.0 | 35.2 | 50.2 | 2.2 | 15 | 24 |
| fifo | liar | tail99 | -4.1 | 35.6 | 393.5 | 53.8 | 2.1 | 18 | 0 |
| prio | short | mean | -4.2 | 19.3 | 37.2 | 5.1 | 2.1 | 15 | 24 |
| prio | short | tail99 | -4.1 | 35.2 | 442.9 | 5.1 | 2.2 | 20 | 0 |
| prio | long | mean | -4.2 | 19.3 | 37.3 | 50.2 | 2.2 | 15 | 24 |
| prio | long | tail99 | -4.1 | 34.6 | 441.9 | 52.1 | 2.1 | 20 | 0 |
| prio | liar | mean | -4.2 | 19.3 | 37.2 | 50.1 | 2.2 | 15 | 24 |
| prio | liar | tail99 | -4.2 | 37.0 | 447.6 | 52.9 | 2.1 | 16 | 0 |
| prio_edf | short | mean | -4.2 | 19.3 | 37.5 | 5.1 | 2.1 | 15 | 24 |
| prio_edf | short | tail99 | -4.1 | 33.7 | 424.3 | 5.1 | 2.2 | 19 | 0 |
| prio_edf | long | mean | -4.2 | 19.3 | 37.6 | 50.2 | 2.2 | 15 | 24 |
| prio_edf | long | tail99 | -4.1 | 34.3 | 422.2 | 52.5 | 2.2 | 19 | 0 |
| prio_edf | liar | mean | -4.1 | 19.3 | 37.6 | 50.2 | 2.2 | 15 | 24 |
| prio_edf | liar | tail99 | -4.2 | 35.3 | 418.5 | 52.6 | 2.1 | 18 | 0 |
| hinted | short | mean | -4.2 | 19.8 | 6.6 | 5.1 | 2.1 | 7 | 26 |
| hinted | short | tail99 | -4.1 | 46.9 | 57.5 | 5.9 | 2.4 | 6 | 2 |
| hinted | long | mean | -4.2 | 19.8 | 49.1 | 50.2 | 2.2 | 21 | 26 |
| hinted | long | tail99 | -4.2 | 36.7 | 580.2 | 51.8 | 2.1 | 28 | 0 |
| hinted | liar | mean | -4.2 | 19.9 | 6.6 | 50.1 | 2.1 | 7 | 26 |
| hinted | liar | tail99 | -4.1 | 47.8 | 54.2 | 56.6 | 2.2 | 9 | 3 |
| hinted+rx | short | mean | -4.2 | 14.1 | 6.5 | 5.1 | 2.1 | 7 | 22 |
| hinted+rx | short | tail99 | -4.1 | 23.6 | 64.6 | 5.8 | 2.5 | 7 | 2 |
| hinted+rx | long | mean | -4.2 | 14.2 | 63.0 | 50.2 | 2.2 | 25 | 22 |
| hinted+rx | long | tail99 | -4.2 | 20.2 | 622.9 | 51.0 | 2.1 | 32 | 0 |
| hinted+rx | liar | mean | -4.2 | 14.2 | 6.4 | 50.2 | 2.2 | 7 | 22 |
| hinted+rx | liar | tail99 | -4.1 | 22.5 | 61.5 | 58.8 | 2.1 | 7 | 5 |
| edf | short | mean | -4.2 | 19.2 | 37.2 | 5.1 | 2.1 | 15 | 24 |
| edf | short | tail99 | -4.2 | 34.0 | 455.9 | 5.1 | 2.2 | 21 | 0 |
| edf | long | mean | -4.2 | 19.2 | 37.5 | 50.2 | 2.2 | 15 | 24 |
| edf | long | tail99 | -4.1 | 34.3 | 458.8 | 52.9 | 2.2 | 21 | 0 |
| edf | liar | mean | -4.2 | 19.2 | 37.4 | 50.2 | 2.2 | 16 | 24 |
| edf | liar | tail99 | -4.1 | 33.7 | 452.1 | 53.6 | 2.1 | 23 | 0 |

## Mean-wait check (pre-registered)

dwait = growth of the kind's mean latency over rho 0.50, net of the change in its handler time, paired by repeat; predicted = pred(rho) - pred(0.50) pooled / per core.

| config | rho | short dwait meas (pooled / per core) ok | long dwait meas (pooled / per core) ok | liar dwait meas (pooled / per core) ok |
|---|---|---|---|---|
| fifo | 0.80 | 15.6 (12.2 / 56) NO | 15.5 (12.2 / 56) NO | 15.9 (12.2 / 56) NO |
| fifo | 0.85 | 26.8 (19.7 / 86) NO | 26.8 (19.7 / 86) NO | 26.6 (19.7 / 86) NO |
| fifo | 0.90 | 50.4 (34.9 / 148) NO | 50.3 (34.9 / 148) NO | 50.8 (34.9 / 148) NO |
| prio | 0.80 | 15.2 (12.2 / 56) yes | 15.2 (12.2 / 56) yes | 15.2 (12.2 / 56) yes |
| prio | 0.85 | 26.3 (19.7 / 86) yes | 26.3 (19.7 / 86) yes | 26.4 (19.7 / 86) yes |
| prio | 0.90 | 53.8 (34.9 / 148) yes | 54.1 (34.9 / 148) yes | 54.0 (34.9 / 148) yes |
| prio_edf | 0.80 | 15.8 (12.2 / 56) yes | 15.8 (12.2 / 56) yes | 15.6 (12.2 / 56) yes |
| prio_edf | 0.85 | 26.6 (19.7 / 86) yes | 26.6 (19.7 / 86) yes | 26.5 (19.7 / 86) yes |
| prio_edf | 0.90 | 53.6 (34.9 / 148) yes | 53.7 (34.9 / 148) yes | 53.5 (34.9 / 148) yes |
| hinted | 0.80 | 10.5 (2.9 / 10) NO | 19.0 (17.5 / 82) yes | 10.5 (2.9 / 10) NO |
| hinted | 0.85 | 15.5 (3.6 / 11) NO | 32.2 (28.8 / 129) yes | 15.4 (3.6 / 11) NO |
| hinted | 0.90 | 22.9 (4.4 / 13) NO | 63.6 (52.3 / 225) yes | 22.9 (4.4 / 13) NO |
| hinted+rx | 0.80 | 9.0 (2.9 / 10) yes | 20.6 (17.5 / 82) yes | 8.8 (2.9 / 10) yes |
| hinted+rx | 0.85 | 12.5 (3.6 / 11) NO | 35.3 (28.8 / 129) yes | 12.2 (3.6 / 11) NO |
| hinted+rx | 0.90 | 17.1 (4.4 / 13) NO | 73.1 (52.3 / 225) yes | 17.0 (4.4 / 13) NO |
| edf | 0.80 | 15.9 (12.2 / 56) yes | 16.0 (12.2 / 56) yes | 15.7 (12.2 / 56) yes |
| edf | 0.85 | 26.8 (19.7 / 86) yes | 26.8 (19.7 / 86) yes | 26.8 (19.7 / 86) yes |
| edf | 0.90 | 52.3 (34.9 / 148) yes | 52.9 (34.9 / 148) yes | 53.0 (34.9 / 148) yes |

Pre-registered check passes in 30 of 45 cells (policies without +rx).

