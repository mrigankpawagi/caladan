/*
 * sched_policy.h - intra-process scheduling policies (thread hints)
 *
 * An intra-process scheduling policy decides which ready thread in a
 * kthread's runqueue runs next. Every policy here is compiled in and one is
 * selected at startup with the runtime config option
 * "runtime_sched_policy <name>". Each is a single rule from the scheduling
 * literature; study/DESIGN.md explains when each one should win.
 *
 * A policy is a choose function. Contract:
 *  - it is called with k->lock held and preemption disabled, only when the
 *    ring holds 2 or more ready threads
 *  - the ring holds n ready threads, 2 <= n <= RUNTIME_RQ_SIZE (32), oldest
 *    first: the i-th one (0 <= i < n) is sched_rq_at(k, i)
 *  - it returns the index i of the thread to run; the caller removes that
 *    thread and keeps the order of the others
 *  - it gets a read-only view of the kthread, must not block, allocate
 *    memory or take locks, and
 *    must make one pass over the ring (O(n), so at most 32 threads)
 *  - it may read any thread field (prio_class, ready_tsc, deadline_tsc,
 *    service_tsc, ...)
 *  - runtime helper threads (prio_class THREAD_PRIO_SOFTIRQ) carry packet,
 *    timer, and storage processing; every policy except fifo runs them first
 *  - ties go to the oldest thread, so with no hints every policy is FIFO
 *
 * This header is included by sched.c and by the stand-alone microbenchmark
 * in study/pickbench, which supplies its own thread_t and struct kthread.
 */

#pragma once

typedef uint32_t (*sched_choose_fn_t)(const struct kthread *k, uint32_t n);

/* the i-th oldest ready thread in @k's ring */
static inline thread_t *sched_rq_at(const struct kthread *k, uint32_t i)
{
	return k->rq[(k->rq_tail + i) % RUNTIME_RQ_SIZE];
}

/* "fifo": run the oldest ready thread, ignoring hints (stock Caladan) */
static uint32_t choose_fifo(const struct kthread *k, uint32_t n)
{
	return 0;
}

/* run order by priority class: higher rank runs first */
static const uint8_t prio_rank[THREAD_PRIO_NR] = {
	[THREAD_PRIO_LOW] = 0,
	[THREAD_PRIO_NORMAL] = 1,
	[THREAD_PRIO_HIGH] = 2,
	[THREAD_PRIO_SOFTIRQ] = 3,
};

/*
 * "prio": strict priority by class (helper threads, then HIGH, NORMAL, LOW),
 * oldest first within a class.
 */
static uint32_t choose_prio(const struct kthread *k, uint32_t n)
{
	uint32_t i, best = 0;
	uint8_t rank = prio_rank[sched_rq_at(k, 0)->prio_class];

	for (i = 1; i < n && rank < prio_rank[THREAD_PRIO_SOFTIRQ]; i++) {
		uint8_t r = prio_rank[sched_rq_at(k, i)->prio_class];

		if (r > rank) {
			rank = r;
			best = i;
		}
	}
	return best;
}

/*
 * Runs a helper thread if one is queued; otherwise the thread with the
 * smallest key, oldest first among equal keys. A key of 0 means "not
 * hinted" and sorts last.
 */
#define SCHED_CHOOSE_MIN_KEY(k, n, field)				\
({									\
	uint32_t __i, __best = 0;					\
	uint64_t __key = UINT64_MAX;					\
									\
	for (__i = 0; __i < (n); __i++) {				\
		thread_t *__th = sched_rq_at((k), __i);			\
		uint64_t __v = __th->field ? __th->field : UINT64_MAX;	\
									\
		if (__th->prio_class == THREAD_PRIO_SOFTIRQ) {		\
			__best = __i;					\
			break;						\
		}							\
		if (__v < __key) {					\
			__key = __v;					\
			__best = __i;					\
		}							\
	}								\
	__best;								\
})

/*
 * "sjf": shortest job first. Runs the thread with the smallest hinted
 * service time; threads without one count as longest. Among orders that
 * never preempt, this minimises the mean wait when service times are known.
 */
static uint32_t choose_sjf(const struct kthread *k, uint32_t n)
{
	return SCHED_CHOOSE_MIN_KEY(k, n, service_tsc);
}

/*
 * "edf": earliest deadline first. Runs the thread with the earliest hinted
 * deadline; threads without one count as latest. When all requests are
 * waiting, this meets every deadline whenever any order can (Jackson's
 * rule).
 */
static uint32_t choose_edf(const struct kthread *k, uint32_t n)
{
	return SCHED_CHOOSE_MIN_KEY(k, n, deadline_tsc);
}

/* a missing hint (0) sorts after every given one */
static inline uint64_t sched_hint_key(uint64_t v)
{
	return v ? v : UINT64_MAX;
}

/* true if @a should run before @b under "hinted" (ties keep the older) */
static inline bool sched_hinted_before(thread_t *a, thread_t *b)
{
	uint64_t ka, kb;

	if (prio_rank[a->prio_class] != prio_rank[b->prio_class])
		return prio_rank[a->prio_class] > prio_rank[b->prio_class];
	ka = sched_hint_key(a->deadline_tsc);
	kb = sched_hint_key(b->deadline_tsc);
	if (ka != kb)
		return ka < kb;
	return sched_hint_key(a->service_tsc) < sched_hint_key(b->service_tsc);
}

/*
 * "hinted": every hint, in order of what it says. Helper threads first;
 * then the highest class (how important the work is); within a class the
 * earliest deadline (how urgent it is); then the smallest service time (how
 * much it delays others); then the oldest. With only one kind of hint it
 * picks exactly what prio, edf or sjf would.
 */
static uint32_t choose_hinted(const struct kthread *k, uint32_t n)
{
	uint32_t i, best = 0;
	thread_t *b = sched_rq_at(k, 0);

	for (i = 1; i < n && b->prio_class != THREAD_PRIO_SOFTIRQ; i++) {
		thread_t *th = sched_rq_at(k, i);

		if (sched_hinted_before(th, b)) {
			b = th;
			best = i;
		}
	}
	return best;
}

static const struct {
	const char		*name;
	sched_choose_fn_t	choose;
} sched_policies[] = {
	{ "fifo",	choose_fifo },
	{ "prio",	choose_prio },
	{ "sjf",	choose_sjf },
	{ "edf",	choose_edf },
	{ "hinted",	choose_hinted },
};
