/*
 * sched_policy.h - intra-process scheduling policies (thread hints)
 *
 * When its hints are set, each thread's hints are packed once into one
 * 64-bit sort key, most important field first:
 *
 *   bits 62..63  class: 0 helper thread, 1 HIGH, 2 NORMAL, 3 LOW
 *   bits 20..61  deadline, in microtime() microseconds (none = all ones)
 *   bits  0..19  expected service time in microseconds (none = all ones)
 *
 * so a smaller key means "run sooner". A policy runs the queued thread with
 * the smallest value of some part of the key; equal values go to the
 * earliest ring slot (the oldest, except after a steal merges two rings).
 * The policies form a ladder, each reading one more hint than the last:
 *
 *   fifo      nothing: the earliest ring slot (stock Caladan)
 *   prio      class                           (key >> 62)
 *   prio_edf  class, then deadline            (key >> 20)
 *   hinted    class, then deadline, then size (the whole key)
 *
 * plus one foil that skips the class:
 *
 *   edf       deadline only                   ((key >> 20) & deadline mask)
 *
 * Every policy except fifo runs a queued runtime helper thread (packet,
 * timer and storage processing) first. One rung only breaks the ties the
 * rung below leaves, so a rung can never order two threads differently
 * from the rung below unless they tie there. All policies cost the same:
 * one shift, one compare and one load per queued thread.
 *
 * A policy is a choose function. Contract:
 *  - it is called with k->lock held and preemption disabled, only when the
 *    ring holds 2 or more ready threads
 *  - the ring holds n ready threads, 2 <= n <= RUNTIME_RQ_SIZE (32), in ring
 *    order: the i-th one (0 <= i < n) is sched_rq_at(k, i)
 *  - it returns the index i of the thread to run; the caller removes that
 *    thread and keeps the order of the others
 *  - it gets a read-only view of the kthread, must not block, allocate
 *    memory or take locks, and makes one pass over the ring
 *
 * This header is included by sched.c and by the stand-alone microbenchmark
 * and test in study/pickbench, which supply their own thread_t and kthread.
 */

#pragma once

#define SCHED_KEY_CLASS_SHIFT	62
#define SCHED_KEY_DL_SHIFT	20
#define SCHED_KEY_DL_BITS	42
#define SCHED_KEY_SVC_BITS	20
#define SCHED_KEY_DL_NONE	((1UL << SCHED_KEY_DL_BITS) - 1)
#define SCHED_KEY_SVC_NONE	((1UL << SCHED_KEY_SVC_BITS) - 1)

/* key position of each class: helper threads first, then HIGH, NORMAL, LOW */
static const uint8_t sched_key_class[THREAD_PRIO_NR] = {
	[THREAD_PRIO_SOFTIRQ] = 0,
	[THREAD_PRIO_HIGH] = 1,
	[THREAD_PRIO_NORMAL] = 2,
	[THREAD_PRIO_LOW] = 3,
};

/**
 * sched_key_make - packs a thread's hints into its sort key
 * @prio_class: THREAD_PRIO_*
 * @deadline_us: absolute deadline in microtime() microseconds (0 = none)
 * @service_us: expected service time in microseconds (0 = unknown)
 *
 * Deadlines wrap after 2^42 us (51 days of uptime); larger service times
 * saturate at about one second.
 */
static inline uint64_t sched_key_make(uint8_t prio_class, uint64_t deadline_us,
				      uint64_t service_us)
{
	uint64_t dl = deadline_us ? (deadline_us & SCHED_KEY_DL_NONE) : SCHED_KEY_DL_NONE;
	uint64_t svc = service_us ? service_us : SCHED_KEY_SVC_NONE;

	if (dl == SCHED_KEY_DL_NONE && deadline_us)
		dl--;		/* keep a real deadline distinct from "none" */
	if (svc >= SCHED_KEY_SVC_NONE && service_us)
		svc = SCHED_KEY_SVC_NONE - 1;
	return ((uint64_t)sched_key_class[prio_class] << SCHED_KEY_CLASS_SHIFT) |
	       (dl << SCHED_KEY_DL_SHIFT) | svc;
}

typedef uint32_t (*sched_choose_fn_t)(const struct kthread *k, uint32_t n);

/* the i-th ready thread in @k's ring */
static inline thread_t *sched_rq_at(const struct kthread *k, uint32_t i)
{
	return k->rq[(k->rq_tail + i) % RUNTIME_RQ_SIZE];
}

/*
 * The one scan every policy uses: the thread with the smallest
 * f(sched_key), earliest ring slot first among equals; a helper thread
 * (class field 0) is taken at once.
 */
#define SCHED_CHOOSE_MIN(k, n, f)					\
({									\
	uint32_t __i, __best = 0;					\
	uint64_t __min = UINT64_MAX;					\
									\
	for (__i = 0; __i < (n); __i++) {				\
		uint64_t key = sched_rq_at((k), __i)->sched_key;	\
		uint64_t __v = (f);					\
									\
		if ((key >> SCHED_KEY_CLASS_SHIFT) == 0) {		\
			__best = __i;					\
			break;						\
		}							\
		if (__v < __min) {					\
			__min = __v;					\
			__best = __i;					\
		}							\
	}								\
	__best;								\
})

/* "fifo": the earliest ring slot, ignoring hints (stock Caladan) */
static uint32_t choose_fifo(const struct kthread *k, uint32_t n)
{
	return 0;
}

/* "prio": the highest class (Cobham's priority queue) */
static uint32_t choose_prio(const struct kthread *k, uint32_t n)
{
	return SCHED_CHOOSE_MIN(k, n, key >> SCHED_KEY_CLASS_SHIFT);
}

/* "prio_edf": the highest class, then the earliest deadline within it */
static uint32_t choose_prio_edf(const struct kthread *k, uint32_t n)
{
	return SCHED_CHOOSE_MIN(k, n, key >> SCHED_KEY_DL_SHIFT);
}

/*
 * "hinted": the highest class, then the earliest deadline, then the
 * smallest expected service time. Size decides only between threads of
 * one class with equal (or no) deadlines.
 */
static uint32_t choose_hinted(const struct kthread *k, uint32_t n)
{
	return SCHED_CHOOSE_MIN(k, n, key);
}

/*
 * "edf": the earliest deadline, ignoring class (the foil: a thread without
 * a deadline runs after every thread with one, whatever its class).
 */
static uint32_t choose_edf(const struct kthread *k, uint32_t n)
{
	return SCHED_CHOOSE_MIN(k, n, (key >> SCHED_KEY_DL_SHIFT) & SCHED_KEY_DL_NONE);
}

static const struct {
	const char		*name;
	sched_choose_fn_t	choose;
} sched_policies[] = {
	{ "fifo",	choose_fifo },
	{ "prio",	choose_prio },
	{ "prio_edf",	choose_prio_edf },
	{ "hinted",	choose_hinted },
	{ "edf",	choose_edf },
};
