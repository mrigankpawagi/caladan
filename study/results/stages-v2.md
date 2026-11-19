# Two checks from the v2 data (stages.py, session v2)

## 1. Pre-registered secondary check: fifo against the pooled prediction at the measured busy fraction

| workload | kind | rho | busy | measured dwait (us) | pooled at rho | pooled at busy |
|---|---|---|---|---|---|---|
| w2b-hol-class | short | 0.80 | 0.838 | 15.8 | 12.2 (-23%) | 16.9 (+7%) |
| w2b-hol-class | short | 0.85 | 0.885 | 26.2 | 19.7 (-25%) | 28.4 (+8%) |
| w2b-hol-class | short | 0.90 | 0.932 | 51.2 | 34.9 (-32%) | 55.9 (+9%) |
| w3-deadlines | tight | 0.80 | 0.857 | 5.7 | 3.4 (-41%) | 5.6 (-1%) |
| w3-deadlines | tight | 0.85 | 0.903 | 9.5 | 5.4 (-43%) | 9.8 (+3%) |
| w3-deadlines | tight | 0.90 | 0.946 | 19.2 | 9.6 (-50%) | 20.2 (+5%) |
| w6-mixed-hints | tight | 0.80 | 0.840 | 15.8 | 12.2 (-23%) | 17.2 (+9%) |
| w6-mixed-hints | tight | 0.85 | 0.888 | 27.7 | 19.7 (-29%) | 29.4 (+6%) |
| w6-mixed-hints | tight | 0.90 | 0.934 | 52.2 | 34.9 (-33%) | 57.5 (+10%) |
| w2a-hol-service | short | 0.80 | 0.839 | 15.7 | 12.2 (-23%) | 17.0 (+8%) |
| w2a-hol-service | short | 0.85 | 0.887 | 26.5 | 19.7 (-26%) | 28.9 (+9%) |
| w2a-hol-service | short | 0.90 | 0.931 | 50.7 | 34.9 (-31%) | 54.9 (+8%) |
| w4-wrong-hints | short | 0.80 | 0.839 | 15.6 | 12.2 (-22%) | 17.1 (+9%) |
| w4-wrong-hints | short | 0.85 | 0.887 | 26.8 | 19.7 (-27%) | 28.9 (+8%) |
| w4-wrong-hints | short | 0.90 | 0.931 | 50.4 | 34.9 (-31%) | 54.9 (+9%) |

## 2. Post hoc: the runqueue stage of favoured kinds at rho 0.9

dwait minus the growth of send->enqueue (the stage every policy shares), against the priority model at the measured busy fraction (pooled / per core).

| workload | policy | kind | busy | dwait | minus send->enqueue growth | predicted pooled | predicted per core | inside |
|---|---|---|---|---|---|---|---|---|
| w2b-hol-class | prio | short | 0.930 | 21.6 | 4.8 | 4.2 | 11.8 | yes |
| w3-deadlines | prio_edf | tight | 0.945 | 10.8 | 1.8 | 1.0 | 2.7 | yes |
| w6-mixed-hints | prio_edf | tight | 0.933 | 18.6 | 1.4 | 3.2 | 8.1 | no |
| w6-mixed-hints | prio_edf | loose | 0.933 | 23.3 | 6.1 | 4.6 | 13.1 | yes |
