# Ladder scorecard, session v2

SLO-load (median of repeats; >= means it never crossed within the grid). Workloads ordered by the information they need. Cells marked = must tie with the others marked = in the same column by construction.

| config | W2b class | W3 deadline | W2a size | W4 wrong size | W6 all hints |
|---|---|---|---|---|---|
| fifo | 0.72 = | 0.76 = | 0.72 = | 0.72 = | 0.72 |
| fifo+rx | 0.72 | 0.76 | - | - | 0.72 |
| prio | >=0.90 = | 0.76 = | 0.72 = | 0.72 = | >=0.90 |
| prio+rx | >=0.90 | 0.76 | - | - | >=0.90 |
| prio_edf | >=0.90 = | 0.82 = | 0.72 = | 0.72 = | >=0.90 = |
| prio_edf+rx | >=0.90 | >=0.90 | - | - | >=0.90 |
| hinted | >=0.90 = | 0.82 = | 0.90 | 0.90 | >=0.90 = |
| hinted+rx | >=0.90 | >=0.90 | >=0.90 | 0.90 | >=0.90 |
| edf | 0.72 = | 0.82 = | 0.72 = | 0.72 = | 0.73 |
| edf+rx | 0.72 | >=0.90 | - | - | 0.73 |
