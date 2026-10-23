# What the first loop learned about this system

Twenty generations of the first loop (PR #5) measured 21 workloads and 22
policies on the same two nodes. Its policies and tooling are not reused; these
facts about the system are. Treat them as prior knowledge, not as rules.

## The runtime
- A core's ready queue holds 32 threads; beyond that, threads go to an
  overflow list the policy cannot see. Overflow appeared only with 128
  connections, and then for about 0.1% of threads.
- The IOKernel's time slice is 100 µs. A thread that runs longer is re-queued
  with a new ready time, so anything built on "time since ready" must tolerate
  that; a thread's accumulated run time does not reset.
- Work stealing moves about 10–25% of hinted threads between cores. More
  connections do not even the cores out.
- The policy's own cost per pick was never measurable: the scheduler's share
  of CPU was the same for every policy within 0.5 points.
- 35–95 µs of a tail request's latency is spent outside the run queue (the
  request itself, a running request it waited for, the network). No ordering
  policy can recover that part; only the run-queue wait is in play.

## Hints and deadlines
- The server-side deadline clock starts when the hint is applied, not when
  the request arrives, so a "late at pick" counter undercounts misses about
  five times. Judge on the client's numbers.
- Deadline-met rates drift about 1.5 points between sessions, and p99 about
  6% with two repeats. Compare only within one session.

## What ordering did
- Priority class alone (prio, oldest first within a class) halves the
  latency-critical p99 against fifo on simple mixes and is hard to beat when
  deadlines and lengths do not conflict.
- Ranking latency-critical threads by deadline plus a multiple of expected
  length helped on key-value mixes where short lookups shared a budget with
  long queries, but it lets a request with a tighter deadline run ahead of an
  older one with a looser deadline; on fan-out services that cost frontend
  reads 30–40% of p99 while cutting the sub-requests' deadline misses 4–11×.
- Learned run times per hint caught requests hiding behind a short label, but
  learning that could only raise a length inflated honest labels; capping the
  learned length near the hint fixed that.
- Each later rule was a pass (a thread may run ahead of the order's choice if
  the passed thread keeps a reserve of its window). Every fixed ratio in such
  a rule invited a workload built just outside it.
- With one tight-deadline kind and one loose-deadline kind, the trade-off is
  real: oldest-first favours the loose kind's p99, deadline order favours the
  tight kind's misses. A policy can hold both only by spending the tight
  kind's measured slack and no more.

## Workloads
- A hidden long request (1% of lookups 100× longer under the same hint) hurts
  only policies that trust the label, and only in the tail.
- Burst length matters: with 1 ms bursts, oldest-first already met nearly all
  tight deadlines; with 4 ms bursts it did not.
- A cache-thrashing neighbour matters only when the server has burstable
  cores to lose; on all-guaranteed cores it did nothing.
