# p1: prio

- id: p1
- config: prio
- generation: 0
- status: baseline
- builds_on: p0
- changed_from_previous: Look through the whole queue and run the highest priority class first (helpers, HIGH, NORMAL, LOW); oldest first within a class.
- commit: 2ce9967

## What it does
Each core looks at all its ready threads and runs one of the most important
class: runtime helper threads, then HIGH, then NORMAL, then LOW. Among threads
of the same class it runs the one that has waited longest. Deadlines and
expected service times are ignored.

## Why (hypothesis)
Under FIFO a short HIGH request waits behind every long NORMAL request queued
before it on the same core. Letting HIGH jump the queue should cut its tail
latency sharply once the server is busy enough for queues to form, at a small
cost to NORMAL requests.

## Cost
NORMAL and LOW requests wait a little longer; LOW can starve if HIGH and
NORMAL keep a core busy. Each pick scans the queue (at most 32 threads).
A HIGH thread that wakes while a NORMAL one is running still waits for it to
finish or be preempted by the IOKernel's time slice; there is no preemption.

## Results
See LEADERBOARD.md and results/gen0/.
