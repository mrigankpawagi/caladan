/*
 * sched.c - a scheduler for user-level threads
 */

#include <sched.h>
#include <string.h>
#include <immintrin.h>

#include <base/stddef.h>
#include <base/lock.h>
#include <base/list.h>
#include <base/hash.h>
#include <base/limits.h>
#include <base/tcache.h>
#include <base/slab.h>
#include <base/log.h>
#include <runtime/sync.h>
#include <runtime/thread.h>
#include <runtime/interruptible_wait.h>

#include "defs.h"

/* the current running thread, or NULL if there isn't one */
DEFINE_PERTHREAD(thread_t *, __self);
DEFINE_PERTHREAD_ALIAS(thread_t * const, __self, __const_self);

/* a pointer to the top of the per-kthread (TLS) runtime stack */
DEFINE_PERTHREAD(void *, runtime_stack);
DEFINE_PERTHREAD(uint64_t, runtime_fsbase);
/* Flag to prevent watchdog from running */
bool disable_watchdog;

/* real-time compute congestion signals (shared with the iokernel) */
struct runtime_info *runtime_info;

/* fast allocation of struct thread */
static struct slab thread_slab;
static struct tcache *thread_tcache;
static DEFINE_PERTHREAD(struct tcache_perthread, thread_pt);

/* used to track cycle usage in scheduler */
static DEFINE_PERTHREAD(uint64_t, last_tsc);

/**
 * In inc/runtime/thread.h, this function is declared inline (rather than static
 * inline) so that it is accessible to the Rust bindings. As a result, it must
 * also appear in a source file to avoid linker errors.
 */
thread_t *thread_self(void);

void thread_set_fsbase(thread_t *th, uint64_t fsbase)
{
	th->fsbase = fsbase;
	barrier();
	th->has_fsbase = true;
	if (thread_self() == th)
		set_fsbase(fsbase);
}

/**
 * cores_have_affinity - returns true if two cores have cache affinity
 * @cpua: the first core
 * @cpub: the second core
 */
static inline bool cores_have_affinity(unsigned int cpua, unsigned int cpub)
{
	return cpua == cpub ||
	       cpu_map[cpua].sibling_core == cpub;
}

/**
 * jmp_thread - runs a thread, popping its trap frame
 * @th: the thread to run
 *
 * This function restores the state of the thread and switches from the runtime
 * stack to the thread's stack. Runtime state is not saved.
 */
static void jmp_thread(thread_t *th)
{
	assert_preempt_disabled();
	assert(th->thread_ready == true);

	perthread_store(__self, th);
	th->thread_ready = false;
	if (unlikely(load_acquire(&th->thread_running))) {
		/* wait until the scheduler finishes switching stacks */
		while (load_acquire(&th->thread_running))
			cpu_relax();
	}

	if (!th->has_fsbase)
		th->fsbase = perthread_read(runtime_fsbase);

	set_fsbase(th->fsbase);

	th->thread_running = true;
	__jmp_thread(&th->tf);
}

/**
 * jmp_thread_direct - runs a thread, popping its trap frame
 * @oldth: the last thread to run
 * @newth: the next thread to run
 *
 * This function restores the state of the thread and switches from the runtime
 * stack to the thread's stack. Runtime state is not saved.
 */
static void jmp_thread_direct(thread_t *oldth, thread_t *newth)
{
	assert_preempt_disabled();
	assert(newth->thread_ready == true);

	perthread_store(__self, newth);
	newth->thread_ready = false;
	if (unlikely(load_acquire(&newth->thread_running))) {
		/* wait until the scheduler finishes switching stacks */
		while (load_acquire(&newth->thread_running))
			cpu_relax();
	}

	if (!newth->has_fsbase)
		newth->fsbase = perthread_read(runtime_fsbase);

	set_fsbase(newth->fsbase);

	newth->thread_running = true;
	__jmp_thread_direct(&oldth->tf, &newth->tf, &oldth->thread_running);
}

/**
 * jmp_runtime - saves the current trap frame and jumps to a function in the
 *               runtime
 * @fn: the runtime function to call
 *
 * WARNING: Only threads can call this function.
 *
 * This function saves state of the running thread and switches to the runtime
 * stack, making it safe to run the thread elsewhere.
 */
static void jmp_runtime(runtime_fn_t fn)
{
	assert_preempt_disabled();
	assert(thread_self() != NULL);

	set_fsbase(perthread_read(runtime_fsbase));

	__jmp_runtime(&thread_self()->tf, fn, perthread_read(runtime_stack));
}

/**
 * jmp_runtime_nosave - jumps to a function in the runtime without saving the
 *			caller's state
 * @fn: the runtime function to call
 */
static __noreturn void jmp_runtime_nosave(runtime_fn_t fn)
{
	assert_preempt_disabled();

	set_fsbase(perthread_read(runtime_fsbase));
	__jmp_runtime_nosave(fn, perthread_read(runtime_stack));
}

static void drain_overflow(struct kthread *l)
{
	thread_t *th;

	assert_spin_lock_held(&l->lock);
	assert(myk() == l || l->parked);

	while (l->rq_head - l->rq_tail < RUNTIME_RQ_SIZE) {
		th = list_pop(&l->rq_overflow, thread_t, link);
		if (!th)
			break;
		l->rq[l->rq_head++ % RUNTIME_RQ_SIZE] = th;
	}
}

/*
 * Whether to record per-pick statistics (sched_count_pick; hint builds only). Off by default so
 * applications do not pay for measurement; experiments turn it on with the
 * runtime config line "runtime_sched_stats 1".
 */
bool cfg_sched_stats;

#ifdef CONFIG_THREAD_HINTS
/* ===== BEGIN SCHEDULING POLICY REGION ======================================
 *
 * An intra-process scheduling policy decides which ready thread in this
 * kthread's runqueue runs next. Policies are described in
 * autoresearch/policies/ and selected at startup with the runtime config
 * option "runtime_sched_policy <name>"; all of them are compiled in.
 *
 * A policy is a choose function. Contract:
 *  - it is called with k->lock held and preemption disabled
 *  - the ring holds n ready threads, 1 <= n <= RUNTIME_RQ_SIZE, oldest first:
 *    the i-th one (0 <= i < n) is sched_rq_at(k, i)
 *  - it returns the index i of the thread to run; sched_pop_next() removes
 *    that thread and keeps the order of the others
 *  - it must not block, allocate memory, take locks, or modify the ring or
 *    the overflow list, and must run in O(n) time
 *  - it may read any thread field (prio_class, ready_tsc, deadline_tsc,
 *    service_tsc, ...), call rdtsc(), and use k->policy_state[]
 *  - runtime helper threads (prio_class THREAD_PRIO_SOFTIRQ) carry packet,
 *    timer, and storage processing; a policy should run them first
 */
typedef uint32_t (*sched_choose_fn_t)(struct kthread *k, uint32_t n);

/* the i-th oldest ready thread in @k's ring */
static inline thread_t *sched_rq_at(struct kthread *k, uint32_t i)
{
	return k->rq[(k->rq_tail + i) % RUNTIME_RQ_SIZE];
}

/* p0 "fifo": run the oldest ready thread, ignoring hints (stock Caladan) */
static uint32_t choose_fifo(struct kthread *k, uint32_t n)
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
 * p1 "prio": strict priority by class (helper threads, then HIGH, NORMAL,
 * LOW), oldest first within a class.
 */
static uint32_t choose_prio(struct kthread *k, uint32_t n)
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

/* implied deadline of a HIGH thread that carries none, after it became ready */
#define POLICY_EDF_NODL_US	1000

/* when a HIGH thread is due: its deadline, or POLICY_EDF_NODL_US after it
 * became ready if it has none */
static inline uint64_t edf_due(const thread_t *th)
{
	if (th->deadline_tsc)
		return th->deadline_tsc;
	return th->ready_tsc + (uint64_t)POLICY_EDF_NODL_US * cycles_per_us;
}

/*
 * p2 "edf_high": strict priority by class as in p1 (helper threads, then
 * HIGH, NORMAL, LOW), but among HIGH threads the one due first runs first
 * (earliest deadline first, oldest first on ties). NORMAL and LOW threads
 * keep their oldest-first order.
 */
static uint32_t choose_edf_high(struct kthread *k, uint32_t n)
{
	thread_t *th = sched_rq_at(k, 0);
	uint8_t r, rank = prio_rank[th->prio_class];
	uint32_t i, best = 0;
	uint64_t d, due = 0;

	if (rank == prio_rank[THREAD_PRIO_SOFTIRQ])
		return 0;
	if (rank == prio_rank[THREAD_PRIO_HIGH])
		due = edf_due(th);

	for (i = 1; i < n; i++) {
		th = sched_rq_at(k, i);
		r = prio_rank[th->prio_class];
		if (r > rank) {
			/* a more important class: helpers run at once */
			if (r == prio_rank[THREAD_PRIO_SOFTIRQ])
				return i;
			rank = r;
			best = i;
			if (r == prio_rank[THREAD_PRIO_HIGH])
				due = edf_due(th);
		} else if (r == rank && r == prio_rank[THREAD_PRIO_HIGH]) {
			/* among HIGH, strictly earlier due time wins */
			d = edf_due(th);
			if ((int64_t)(d - due) < 0) {
				due = d;
				best = i;
			}
		}
	}
	return best;
}

/* p3: a HIGH thread is urgent when it must start within this many us to
 * finish by its due time */
#define POLICY_SJF_GUARD_US	20
/* p3: each us of expected run time moves a HIGH thread's turn back this many us */
#define POLICY_SJF_WEIGHT	8
/* p3: run-time hints longer than this count as this (keeps the sums small) */
#define POLICY_SJF_SVC_MAX_US	1000

/* expected run time of @th in cycles, capped; 0 if unknown */
static inline uint64_t sjf_service(const thread_t *th)
{
	return MIN(th->service_tsc,
		   (uint64_t)POLICY_SJF_SVC_MAX_US * cycles_per_us);
}

/* the last moment @th can start and still finish by its due time */
static inline uint64_t sjf_latest_start(const thread_t *th)
{
	return edf_due(th) - sjf_service(th);
}

/* turn of a HIGH thread that is not urgent (earlier runs first): its due
 * time, pushed back by POLICY_SJF_WEIGHT times its expected run time */
static inline uint64_t sjf_turn(const thread_t *th)
{
	return edf_due(th) + POLICY_SJF_WEIGHT * sjf_service(th);
}

/*
 * true if @th can still finish by its due time, but only if it starts within
 * POLICY_SJF_GUARD_US of @now; once its latest start has passed, the unsigned
 * difference wraps to a huge value and the test fails
 */
static inline bool sjf_urgent(const thread_t *th, uint64_t now)
{
	return sjf_latest_start(th) - now <
	       (uint64_t)POLICY_SJF_GUARD_US * cycles_per_us;
}

/* true if HIGH thread @a (urgent if @ua) should run before HIGH thread @b
 * (urgent if @ub): urgent ones first, least slack first among them,
 * otherwise the earlier turn */
static inline bool sjf_before(const thread_t *a, bool ua,
			      const thread_t *b, bool ub)
{
	if (ua != ub)
		return ua;
	if (ua)
		return (int64_t)(sjf_latest_start(a) - sjf_latest_start(b)) < 0;
	return (int64_t)(sjf_turn(a) - sjf_turn(b)) < 0;
}

/*
 * p3 "sjf_guard": class order as in p2 (helper threads, then HIGH, NORMAL,
 * LOW; NORMAL and LOW oldest first). Among HIGH threads, an urgent one (see
 * sjf_urgent()) runs first, the one with the least slack first; otherwise
 * the one with the earliest sjf_turn(), so a short thread passes a longer one
 * due up to POLICY_SJF_WEIGHT times their difference in run time earlier.
 * Ties keep the oldest. The clock is read at most once, and only when two
 * HIGH threads are queued.
 */
static uint32_t choose_sjf_guard(struct kthread *k, uint32_t n)
{
	thread_t *th = sched_rq_at(k, 0), *bth = th;
	uint8_t r, rank = prio_rank[th->prio_class];
	bool have_now = false, bu = false, u;
	uint32_t i, best = 0;
	uint64_t now = 0;

	if (rank == prio_rank[THREAD_PRIO_SOFTIRQ])
		return 0;

	for (i = 1; i < n; i++) {
		th = sched_rq_at(k, i);
		r = prio_rank[th->prio_class];
		if (r > rank) {
			/* a more important class: helpers run at once */
			if (r == prio_rank[THREAD_PRIO_SOFTIRQ])
				return i;
			rank = r;
			best = i;
			bth = th;
		} else if (r == rank && r == prio_rank[THREAD_PRIO_HIGH]) {
			if (!have_now) {
				/* a second HIGH thread: read the clock once */
				now = rdtsc();
				have_now = true;
				bu = sjf_urgent(bth, now);
			}
			u = sjf_urgent(th, now);
			if (sjf_before(th, u, bth, bu)) {
				best = i;
				bth = th;
				bu = u;
			}
		}
	}
	return best;
}

/* p4: a HIGH thread with less slack than this can no longer finish in time
 * as the client sees it: at light load about 13 us of a request's latency
 * is spent outside the run queue (network, runtime) */
#define POLICY_RESCUE_LATE_US	13
/* p4: what running a request costs beyond its run-time hint (thread
 * creation, network stack; about 4 us per request in calibration.json) */
#define POLICY_RESCUE_COST_US	4

/* slack of HIGH thread @th at @now: how long it can still wait and start in
 * time to finish by its due time; negative once that moment has passed */
static inline int64_t rescue_slack(const thread_t *th, uint64_t now)
{
	return (int64_t)(sjf_latest_start(th) - now);
}

/* true if HIGH thread @a (too late if @al) goes before HIGH thread @b (too
 * late if @bl) in p4's base order: a thread that is too late waits for any
 * shorter one; otherwise the earlier sjf_turn() goes first */
static inline bool rescue_before(const thread_t *a, bool al,
				 const thread_t *b, bool bl)
{
	uint64_t sa = sjf_service(a), sb = sjf_service(b);

	if ((al || bl) && sa != sb)
		return sa < sb;
	return (int64_t)(sjf_turn(a) - sjf_turn(b)) < 0;
}

/*
 * p4 "sjf_rescue": class order as in p3 (helper threads, then HIGH, NORMAL,
 * LOW; NORMAL and LOW oldest first). Among HIGH threads, one with less than
 * POLICY_RESCUE_LATE_US of slack is too late to save: it waits for any
 * shorter HIGH thread. The others keep p3's sjf_turn() order. p3's fixed
 * urgency guard becomes a check against that order's choice: the HIGH
 * thread with the least slack among those not too late runs first only if
 * waiting for the choice (its expected run time plus POLICY_RESCUE_COST_US)
 * would leave it too late. Ties keep the oldest. The clock is read at most
 * once, and only when two HIGH threads are queued.
 */
static uint32_t choose_sjf_rescue(struct kthread *k, uint32_t n)
{
	thread_t *th = sched_rq_at(k, 0), *bth = th, *uth = NULL;
	uint8_t r, rank = prio_rank[th->prio_class];
	uint32_t i, best = 0, ubest = 0;
	int64_t s, bs = 0, us = 0, late = 0;
	bool have_now = false;
	uint64_t now = 0, cost;

	if (rank == prio_rank[THREAD_PRIO_SOFTIRQ])
		return 0;

	for (i = 1; i < n; i++) {
		th = sched_rq_at(k, i);
		r = prio_rank[th->prio_class];
		if (r > rank) {
			/* a more important class: helpers run at once */
			if (r == prio_rank[THREAD_PRIO_SOFTIRQ])
				return i;
			rank = r;
			best = i;
			bth = th;
		} else if (r == rank && r == prio_rank[THREAD_PRIO_HIGH]) {
			if (!have_now) {
				/* a second HIGH thread: read the clock once */
				now = rdtsc();
				have_now = true;
				late = (int64_t)POLICY_RESCUE_LATE_US *
				       cycles_per_us;
				bs = rescue_slack(bth, now);
				if (bs >= late) {
					uth = bth;
					ubest = best;
					us = bs;
				}
			}
			s = rescue_slack(th, now);
			/* least slack among the threads not too late */
			if (s >= late && (!uth || s < us)) {
				uth = th;
				ubest = i;
				us = s;
			}
			if (rescue_before(th, s < late, bth, bs < late)) {
				best = i;
				bth = th;
				bs = s;
			}
		}
	}

	/* it goes first if waiting for the chosen thread would make it late */
	if (uth && uth != bth) {
		cost = sjf_service(bth) +
		       (uint64_t)POLICY_RESCUE_COST_US * cycles_per_us;
		if (us < late + (int64_t)cost)
			return ubest;
	}
	return best;
}

/*
 * p5: per-core learned run times in k->policy_state[]:
 *  [0] when the timed pick was made (0 = none pending)
 *  [1] the run-time hint (sjf_service()) of the thread it chose
 *  [2] learn_mark() of a thread it left queued
 *  [POLICY_LEARN_FIRST..7] one slot per hint value: the hint in the high 32
 *  bits, the learned run time in cycles in the low 32 bits (0 = free slot)
 */
#define POLICY_LEARN_FIRST	3
#define POLICY_LEARN_SLOTS	5
/* p5: a run longer than the estimate pulls it up by 1/2^4 of the gap and a
 * shorter one pulls it down by 1/2^6, so the estimate leans to long runs */
#define POLICY_LEARN_UP_SHIFT	4
#define POLICY_LEARN_DOWN_SHIFT	6
/* p5: a sample longer than twice learn_floor() plus this many us is not one
 * run (the core was parked or the thread blocked) and is dropped */
#define POLICY_LEARN_CAP_US	50
/* p5: a pick is timed only if it leaves at least this many threads queued;
 * with one left, the next pick reaches the policy only when the watchdog
 * adds a helper thread, which would favour long runs */
#define POLICY_LEARN_MIN_LEFT	2

/* p5: reads the clock at most once per pick (0 in @now = not read yet) */
static inline uint64_t learn_clock(uint64_t *now)
{
	if (!*now)
		*now = rdtsc();
	return *now;
}

/* p5: the least a HIGH thread with run-time hint @key (0 = none) is taken
 * to cost: the hint plus p4's per-request overhead */
static inline uint64_t learn_floor(uint64_t key)
{
	return key + (uint64_t)POLICY_RESCUE_COST_US * cycles_per_us;
}

/* p5: identifies @th while it stays queued; a freed thread struct that is
 * reused gets a new ready time, and so a new mark */
static inline uint64_t learn_mark(const thread_t *th)
{
	return (uint64_t)(uintptr_t)th ^ th->ready_tsc;
}

/* p5: expected cost of HIGH thread @th: the run time learned for its hint
 * value, but never less than learn_floor() */
static inline uint64_t learn_cost(const uint64_t *ps, const thread_t *th)
{
	uint64_t key = sjf_service(th), fl = learn_floor(key), e;
	int i;

	if (!key)
		return fl;
	for (i = POLICY_LEARN_FIRST;
	     i < POLICY_LEARN_FIRST + POLICY_LEARN_SLOTS; i++) {
		if ((ps[i] >> 32) == key) {
			e = ps[i] & 0xffffffffULL;
			return e > fl ? e : fl;
		}
	}
	return fl;
}

/* p5: folds one observed run time @sample of a HIGH thread with hint @key
 * into that hint's slot, claiming a free slot the first time */
static void learn_update(uint64_t *ps, uint64_t key, uint64_t sample)
{
	uint64_t fl = learn_floor(key), e;
	int i, slot = -1;

	if (sample > 2 * fl + (uint64_t)POLICY_LEARN_CAP_US * cycles_per_us)
		return;
	for (i = POLICY_LEARN_FIRST;
	     i < POLICY_LEARN_FIRST + POLICY_LEARN_SLOTS; i++) {
		if ((ps[i] >> 32) == key) {
			slot = i;
			break;
		}
		if (!ps[i] && slot < 0)
			slot = i;
	}
	if (slot < 0)
		return;
	e = ps[slot] ? (ps[slot] & 0xffffffffULL) : fl;
	if (sample > e)
		e += (sample - e) >> POLICY_LEARN_UP_SHIFT;
	else
		e -= (e - sample) >> POLICY_LEARN_DOWN_SHIFT;
	ps[slot] = (key << 32) | e;
}

/* p5: true if HIGH thread @a (cost @ca, too late if @al) goes before HIGH
 * thread @b (cost @cb, too late if @bl): p4's rescue_before() with learned
 * costs in place of hints */
static inline bool learn_before(const thread_t *a, uint64_t ca, bool al,
				const thread_t *b, uint64_t cb, bool bl)
{
	if ((al || bl) && ca != cb)
		return ca < cb;
	return (int64_t)((edf_due(a) + POLICY_SJF_WEIGHT * ca) -
			 (edf_due(b) + POLICY_SJF_WEIGHT * cb)) < 0;
}

/*
 * p5 "sjf_learn": p4's order (helper threads, then HIGH, NORMAL, LOW; NORMAL
 * and LOW oldest first; among HIGH, a too-late thread waits for shorter
 * ones, the others go by deadline plus POLICY_SJF_WEIGHT times their cost,
 * then p4's rescue check), with each HIGH thread's cost from learn_cost()
 * instead of its hint plus POLICY_RESCUE_COST_US. Each core times the
 * hinted HIGH threads it runs: the policy sees every pick from a queue of
 * two or more, so if the next pick still finds a thread this pick left
 * queued, nothing else ran in between and the time between the two picks
 * is the chosen thread's run time. A hint value whose threads run within
 * their hint plus POLICY_RESCUE_COST_US keeps p4's decisions exactly. The
 * clock is read at most once per pick.
 */
static uint32_t choose_sjf_learn(struct kthread *k, uint32_t n)
{
	uint64_t *ps = k->policy_state;
	thread_t *th, *bth, *uth = NULL;
	uint8_t r, rank;
	uint32_t i, best = 0, ubest = 0;
	int64_t s, bs = 0, us = 0, late = 0;
	uint64_t now = 0, c, bc = 0;
	bool two_high = false;

	/* close the sample of this core's previous timed pick */
	if (ps[0]) {
		learn_clock(&now);
		for (i = 0; i < n; i++) {
			if (learn_mark(sched_rq_at(k, i)) == ps[2]) {
				learn_update(ps, ps[1], now - ps[0]);
				break;
			}
		}
		ps[0] = 0;
	}

	th = bth = sched_rq_at(k, 0);
	rank = prio_rank[th->prio_class];
	if (rank == prio_rank[THREAD_PRIO_SOFTIRQ])
		return 0;

	for (i = 1; i < n; i++) {
		th = sched_rq_at(k, i);
		r = prio_rank[th->prio_class];
		if (r > rank) {
			/* a more important class: helpers run at once */
			if (r == prio_rank[THREAD_PRIO_SOFTIRQ])
				return i;
			rank = r;
			best = i;
			bth = th;
		} else if (r == rank && r == prio_rank[THREAD_PRIO_HIGH]) {
			if (!two_high) {
				/* a second HIGH thread: as in p4 */
				two_high = true;
				learn_clock(&now);
				late = (int64_t)POLICY_RESCUE_LATE_US *
				       cycles_per_us;
				bc = learn_cost(ps, bth);
				bs = rescue_slack(bth, now);
				if (bs >= late) {
					uth = bth;
					ubest = best;
					us = bs;
				}
			}
			c = learn_cost(ps, th);
			s = rescue_slack(th, now);
			/* least slack among the threads not too late */
			if (s >= late && (!uth || s < us)) {
				uth = th;
				ubest = i;
				us = s;
			}
			if (learn_before(th, c, s < late, bth, bc, bs < late)) {
				best = i;
				bth = th;
				bc = c;
				bs = s;
			}
		}
	}

	/* p4's rescue check, with the learned cost of the chosen thread */
	if (uth && uth != bth && us < late + (int64_t)bc) {
		best = ubest;
		bth = uth;
	}

	/* time this pick: mark the newest thread it leaves queued */
	if (bth->prio_class == THREAD_PRIO_HIGH && bth->service_tsc &&
	    n - 1 >= POLICY_LEARN_MIN_LEFT) {
		ps[0] = learn_clock(&now);
		ps[1] = sjf_service(bth);
		ps[2] = learn_mark(sched_rq_at(k, best == n - 1 ? n - 2 : n - 1));
	}
	return best;
}

/*
 * p6: expected cost of HIGH thread @th: the run time this core has learned
 * for its run-time hint value in p5's table (k->policy_state[]), whether
 * that is below the hint or above it; before any run with that hint has
 * been timed, the hint plus POLICY_RESCUE_COST_US, where p5's estimate
 * starts
 */
static inline uint64_t timed_cost(const uint64_t *ps, const thread_t *th)
{
	uint64_t key = sjf_service(th);
	int i;

	if (key) {
		for (i = POLICY_LEARN_FIRST;
		     i < POLICY_LEARN_FIRST + POLICY_LEARN_SLOTS; i++) {
			if ((ps[i] >> 32) == key)
				return ps[i] & 0xffffffffULL;
		}
	}
	return learn_floor(key);
}

/*
 * p6: p3's sjf_urgent() with cost @c in place of the hint: true if @th can
 * still finish by its due time, but only if it starts within
 * POLICY_SJF_GUARD_US of @now; once its latest start has passed, the
 * unsigned difference wraps to a huge value and the test fails
 */
static inline bool timed_urgent(const thread_t *th, uint64_t c, uint64_t now)
{
	return edf_due(th) - c - now <
	       (uint64_t)POLICY_SJF_GUARD_US * cycles_per_us;
}

/*
 * p6: p3's sjf_before() with costs in place of hints: true if HIGH thread
 * @a (cost @ca, urgent if @ua) runs before HIGH thread @b (cost @cb, urgent
 * if @ub): urgent ones first, the one whose latest start comes first among
 * them, otherwise the earlier of due time plus POLICY_SJF_WEIGHT times cost
 */
static inline bool timed_before(const thread_t *a, uint64_t ca, bool ua,
				const thread_t *b, uint64_t cb, bool ub)
{
	if (ua != ub)
		return ua;
	if (ua)
		return (int64_t)((edf_due(a) - ca) - (edf_due(b) - cb)) < 0;
	return (int64_t)((edf_due(a) + POLICY_SJF_WEIGHT * ca) -
			 (edf_due(b) + POLICY_SJF_WEIGHT * cb)) < 0;
}

/*
 * p6 "sjf_timed": p3's order (helper threads, then HIGH, NORMAL, LOW; NORMAL
 * and LOW oldest first; among HIGH, a thread that must start within
 * POLICY_SJF_GUARD_US to finish by its due time runs first, least slack
 * first, and the others go by due time plus POLICY_SJF_WEIGHT times their
 * length). The one change is that each HIGH thread's length comes from
 * timed_cost() instead of its hint. Lengths are learned as in p5: each core
 * times the hinted HIGH threads it runs, from their pick to the next pick,
 * and folds each run into learn_update()'s per-hint estimate. Unlike p5,
 * the estimate is used without a floor, so a hint that is too long gets
 * corrected as well as one that is too short. p4's too-late rule and rescue
 * check are left out: a thread that can no longer finish in time keeps its
 * normal turn and does not yield to newer work. Ties keep the oldest. The
 * clock is read at most once per pick. Without HIGH threads this is p3's
 * path and the clock is never read.
 */
static uint32_t choose_sjf_timed(struct kthread *k, uint32_t n)
{
	uint64_t *ps = k->policy_state;
	thread_t *th, *bth;
	uint8_t r, rank;
	uint32_t i, best = 0;
	uint64_t now = 0, c, bc = 0;
	bool two_high = false, bu = false, u;

	/* close the sample of this core's previous timed pick (as in p5) */
	if (ps[0]) {
		learn_clock(&now);
		for (i = 0; i < n; i++) {
			if (learn_mark(sched_rq_at(k, i)) == ps[2]) {
				learn_update(ps, ps[1], now - ps[0]);
				break;
			}
		}
		ps[0] = 0;
	}

	th = bth = sched_rq_at(k, 0);
	rank = prio_rank[th->prio_class];
	if (rank == prio_rank[THREAD_PRIO_SOFTIRQ])
		return 0;

	for (i = 1; i < n; i++) {
		th = sched_rq_at(k, i);
		r = prio_rank[th->prio_class];
		if (r > rank) {
			/* a more important class: helpers run at once */
			if (r == prio_rank[THREAD_PRIO_SOFTIRQ])
				return i;
			rank = r;
			best = i;
			bth = th;
		} else if (r == rank && r == prio_rank[THREAD_PRIO_HIGH]) {
			if (!two_high) {
				/* a second HIGH thread: price the first one */
				two_high = true;
				learn_clock(&now);
				bc = timed_cost(ps, bth);
				bu = timed_urgent(bth, bc, now);
			}
			c = timed_cost(ps, th);
			u = timed_urgent(th, c, now);
			if (timed_before(th, c, u, bth, bc, bu)) {
				best = i;
				bth = th;
				bc = c;
				bu = u;
			}
		}
	}

	/* time this pick (as in p5): mark the newest thread it leaves queued */
	if (bth->prio_class == THREAD_PRIO_HIGH && bth->service_tsc &&
	    n - 1 >= POLICY_LEARN_MIN_LEFT) {
		ps[0] = learn_clock(&now);
		ps[1] = sjf_service(bth);
		ps[2] = learn_mark(sched_rq_at(k, best == n - 1 ? n - 2 : n - 1));
	}
	return best;
}

/* p7: run time assumed for a HIGH thread without a run-time hint: longer
 * than the short hinted kinds (1-2 us), shorter than the long ones (17 us) */
#define POLICY_NOHINT_US	8

/* p7: expected run time of HIGH thread @th in cycles: its hint as in p3
 * (sjf_service()), or POLICY_NOHINT_US if it carries none */
static inline uint64_t nohint_cost(const thread_t *th)
{
	uint64_t c = sjf_service(th);

	return c ? c : (uint64_t)POLICY_NOHINT_US * cycles_per_us;
}

/*
 * p7 "sjf_nohint": p3's order (helper threads, then HIGH, NORMAL, LOW;
 * NORMAL and LOW oldest first; among HIGH, a thread that must start within
 * POLICY_SJF_GUARD_US to finish by its due time runs first, least slack
 * first, and the others go by due time plus POLICY_SJF_WEIGHT times their
 * run time). The one change: a HIGH thread without a run-time hint counts
 * as POLICY_NOHINT_US long, both in its turn and in the urgency test (p3
 * counts it as zero-length, ahead of every short hinted thread). p6's
 * timed_urgent() and timed_before() are p3's tests with the run time passed
 * in, so a thread with a hint is ranked exactly as in p3. Ties keep the
 * oldest. The clock is read at most once, and only when two HIGH threads
 * are queued; k->policy_state[] is not used.
 */
static uint32_t choose_sjf_nohint(struct kthread *k, uint32_t n)
{
	thread_t *th = sched_rq_at(k, 0), *bth = th;
	uint8_t r, rank = prio_rank[th->prio_class];
	bool have_now = false, bu = false, u;
	uint32_t i, best = 0;
	uint64_t now = 0, c, bc = 0;

	if (rank == prio_rank[THREAD_PRIO_SOFTIRQ])
		return 0;

	for (i = 1; i < n; i++) {
		th = sched_rq_at(k, i);
		r = prio_rank[th->prio_class];
		if (r > rank) {
			/* a more important class: helpers run at once */
			if (r == prio_rank[THREAD_PRIO_SOFTIRQ])
				return i;
			rank = r;
			best = i;
			bth = th;
		} else if (r == rank && r == prio_rank[THREAD_PRIO_HIGH]) {
			if (!have_now) {
				/* a second HIGH thread: read the clock once */
				now = rdtsc();
				have_now = true;
				bc = nohint_cost(bth);
				bu = timed_urgent(bth, bc, now);
			}
			c = nohint_cost(th);
			u = timed_urgent(th, c, now);
			if (timed_before(th, c, u, bth, bc, bu)) {
				best = i;
				bth = th;
				bc = c;
				bu = u;
			}
		}
	}
	return best;
}

/* p8: a learned run time counts at most this many us above p4's length for
 * its hint (the hint plus POLICY_RESCUE_COST_US): w8's 1 us hint, shared by
 * quick puts and 30 us syncs, then counts as 13 us, behind gets (about
 * 6 us) and ahead of queries (about 21 us) */
#define POLICY_CAP_UP_US	8
/* p8: length of a HIGH thread without a run-time hint: behind the 13 us
 * that a 1 us hint can reach, ahead of queries (about 21 us) */
#define POLICY_CAP_BLANK_US	17

/* p8: expected length of HIGH thread @th in cycles: the run time this core
 * has learned for its run-time hint value (p6's timed_cost(), which can be
 * below the hint), but at most POLICY_CAP_UP_US above learn_floor(); a
 * thread without a run-time hint counts as POLICY_CAP_BLANK_US */
static inline uint64_t capped_cost(const uint64_t *ps, const thread_t *th)
{
	uint64_t key = sjf_service(th), c, cap;

	if (!key)
		return (uint64_t)POLICY_CAP_BLANK_US * cycles_per_us;
	c = timed_cost(ps, th);
	cap = learn_floor(key) + (uint64_t)POLICY_CAP_UP_US * cycles_per_us;
	return c < cap ? c : cap;
}

/* p8: slack of HIGH thread @th of length @c at @now: how long it can still
 * wait and finish by its due time; negative once that moment has passed */
static inline int64_t capped_slack(const thread_t *th, uint64_t c,
				   uint64_t now)
{
	return (int64_t)(edf_due(th) - c - now);
}

/*
 * p8 "sjf_capped": p5's order (helper threads, then HIGH, NORMAL, LOW;
 * NORMAL and LOW oldest first; among HIGH, a thread that is too late waits
 * for any shorter one, the others go by due time plus POLICY_SJF_WEIGHT
 * times their length, then p4's rescue check) and p5's per-core timing,
 * with three changes to a HIGH thread's length, which capped_cost() gives:
 * the learned run time is used without p5's floor, so it can also fall
 * below the hint (as in p6); it counts at most POLICY_CAP_UP_US above the
 * hint plus POLICY_RESCUE_COST_US; and a thread without a run-time hint
 * counts as POLICY_CAP_BLANK_US (p5: POLICY_RESCUE_COST_US). Slack is
 * measured with the same length, so a thread is too late below
 * POLICY_RESCUE_LATE_US - POLICY_RESCUE_COST_US of slack; for a hint whose
 * threads run in exactly the hint plus POLICY_RESCUE_COST_US this is p4's
 * test. The clock is read at most once per pick. Without HIGH threads this
 * is p4's path and the clock is never read.
 */
static uint32_t choose_sjf_capped(struct kthread *k, uint32_t n)
{
	uint64_t *ps = k->policy_state;
	thread_t *th, *bth, *uth = NULL;
	uint8_t r, rank;
	uint32_t i, best = 0, ubest = 0;
	int64_t s, bs = 0, us = 0, late = 0;
	uint64_t now = 0, c, bc = 0;
	bool two_high = false;

	/* close the sample of this core's previous timed pick (as in p5) */
	if (ps[0]) {
		learn_clock(&now);
		for (i = 0; i < n; i++) {
			if (learn_mark(sched_rq_at(k, i)) == ps[2]) {
				learn_update(ps, ps[1], now - ps[0]);
				break;
			}
		}
		ps[0] = 0;
	}

	th = bth = sched_rq_at(k, 0);
	rank = prio_rank[th->prio_class];
	if (rank == prio_rank[THREAD_PRIO_SOFTIRQ])
		return 0;

	for (i = 1; i < n; i++) {
		th = sched_rq_at(k, i);
		r = prio_rank[th->prio_class];
		if (r > rank) {
			/* a more important class: helpers run at once */
			if (r == prio_rank[THREAD_PRIO_SOFTIRQ])
				return i;
			rank = r;
			best = i;
			bth = th;
		} else if (r == rank && r == prio_rank[THREAD_PRIO_HIGH]) {
			if (!two_high) {
				/* a second HIGH thread: price the first one */
				two_high = true;
				learn_clock(&now);
				late = (int64_t)(POLICY_RESCUE_LATE_US -
						 POLICY_RESCUE_COST_US) *
				       cycles_per_us;
				bc = capped_cost(ps, bth);
				bs = capped_slack(bth, bc, now);
				if (bs >= late) {
					uth = bth;
					ubest = best;
					us = bs;
				}
			}
			c = capped_cost(ps, th);
			s = capped_slack(th, c, now);
			/* least slack among the threads not too late */
			if (s >= late && (!uth || s < us)) {
				uth = th;
				ubest = i;
				us = s;
			}
			if (learn_before(th, c, s < late, bth, bc, bs < late)) {
				best = i;
				bth = th;
				bc = c;
				bs = s;
			}
		}
	}

	/* p4's rescue check, with the capped length of the chosen thread */
	if (uth && uth != bth && us < late + (int64_t)bc) {
		best = ubest;
		bth = uth;
	}

	/* time this pick (as in p5): mark the newest thread it leaves queued */
	if (bth->prio_class == THREAD_PRIO_HIGH && bth->service_tsc &&
	    n - 1 >= POLICY_LEARN_MIN_LEFT) {
		ps[0] = learn_clock(&now);
		ps[1] = sjf_service(bth);
		ps[2] = learn_mark(sched_rq_at(k, best == n - 1 ? n - 2 : n - 1));
	}
	return best;
}

/* p9: a HIGH thread whose deadline lies more than this many us after it
 * became ready is learned apart from threads with the same run-time hint and
 * a nearer deadline: w9's multigets (300 us) apart from its gets (100 us);
 * no other workload has a deadline above 200 us, so there p9 decides as p8 */
#define POLICY_PAIR_SPLIT_US	250
/* p9: marks such a thread in its learning key; run-time hints are capped at
 * POLICY_SJF_SVC_MAX_US, far below 2^31 cycles, so the bit is otherwise 0 */
#define POLICY_PAIR_RELAXED	(1ULL << 31)

/* p9: learning key of HIGH thread @th with run-time hint @hint: the hint,
 * with POLICY_PAIR_RELAXED set if its deadline is more than
 * POLICY_PAIR_SPLIT_US after it became ready */
static inline uint64_t pair_key(const thread_t *th, uint64_t hint)
{
	if (th->deadline_tsc &&
	    (int64_t)(th->deadline_tsc - th->ready_tsc) >
	    (int64_t)POLICY_PAIR_SPLIT_US * cycles_per_us)
		return hint | POLICY_PAIR_RELAXED;
	return hint;
}

/* p9: expected length of HIGH thread @th: p8's capped_cost(), with the run
 * time looked up under pair_key() instead of the hint alone */
static inline uint64_t pair_cost(const uint64_t *ps, const thread_t *th)
{
	uint64_t hint = sjf_service(th), key, fl, c, cap;
	int i;

	if (!hint)
		return (uint64_t)POLICY_CAP_BLANK_US * cycles_per_us;
	key = pair_key(th, hint);
	fl = learn_floor(hint);
	c = fl;
	for (i = POLICY_LEARN_FIRST;
	     i < POLICY_LEARN_FIRST + POLICY_LEARN_SLOTS; i++) {
		if ((ps[i] >> 32) == key) {
			c = ps[i] & 0xffffffffULL;
			break;
		}
	}
	cap = fl + (uint64_t)POLICY_CAP_UP_US * cycles_per_us;
	return c < cap ? c : cap;
}

/* p9: p5's learn_update() for learning key @key: the floor and the drop
 * limit come from the run-time hint alone, without POLICY_PAIR_RELAXED */
static void pair_update(uint64_t *ps, uint64_t key, uint64_t sample)
{
	uint64_t fl = learn_floor(key & ~POLICY_PAIR_RELAXED), e;
	int i, slot = -1;

	if (sample > 2 * fl + (uint64_t)POLICY_LEARN_CAP_US * cycles_per_us)
		return;
	for (i = POLICY_LEARN_FIRST;
	     i < POLICY_LEARN_FIRST + POLICY_LEARN_SLOTS; i++) {
		if ((ps[i] >> 32) == key) {
			slot = i;
			break;
		}
		if (!ps[i] && slot < 0)
			slot = i;
	}
	if (slot < 0)
		return;
	e = ps[slot] ? (ps[slot] & 0xffffffffULL) : fl;
	if (sample > e)
		e += (sample - e) >> POLICY_LEARN_UP_SHIFT;
	else
		e -= (e - sample) >> POLICY_LEARN_DOWN_SHIFT;
	ps[slot] = (key << 32) | e;
}

/*
 * p9 "sjf_pair": p8's order, timing and capped lengths (see
 * choose_sjf_capped()), with one change: each core learns a run time per
 * pair of run-time hint and coarse deadline instead of per hint, so HIGH
 * threads whose deadline is more than POLICY_PAIR_SPLIT_US after they became
 * ready keep their own estimate (pair_key()). On w9, 30 us multigets carry
 * the gets' 2 us hint with a 300 us deadline; learned apart, gets keep their
 * own short length and multigets count as p8's cap (hint plus
 * POLICY_RESCUE_COST_US plus POLICY_CAP_UP_US). Where every hint value comes
 * with one deadline, or no deadline exceeds the split, the keys pair up one
 * to one with p8's and every decision is p8's. The clock is read at most
 * once per pick. Without HIGH threads this is p4's path and the clock is
 * never read.
 */
static uint32_t choose_sjf_pair(struct kthread *k, uint32_t n)
{
	uint64_t *ps = k->policy_state;
	thread_t *th, *bth, *uth = NULL;
	uint8_t r, rank;
	uint32_t i, best = 0, ubest = 0;
	int64_t s, bs = 0, us = 0, late = 0;
	uint64_t now = 0, c, bc = 0;
	bool two_high = false;

	/* close the sample of this core's previous timed pick (as in p5) */
	if (ps[0]) {
		learn_clock(&now);
		for (i = 0; i < n; i++) {
			if (learn_mark(sched_rq_at(k, i)) == ps[2]) {
				pair_update(ps, ps[1], now - ps[0]);
				break;
			}
		}
		ps[0] = 0;
	}

	th = bth = sched_rq_at(k, 0);
	rank = prio_rank[th->prio_class];
	if (rank == prio_rank[THREAD_PRIO_SOFTIRQ])
		return 0;

	for (i = 1; i < n; i++) {
		th = sched_rq_at(k, i);
		r = prio_rank[th->prio_class];
		if (r > rank) {
			/* a more important class: helpers run at once */
			if (r == prio_rank[THREAD_PRIO_SOFTIRQ])
				return i;
			rank = r;
			best = i;
			bth = th;
		} else if (r == rank && r == prio_rank[THREAD_PRIO_HIGH]) {
			if (!two_high) {
				/* a second HIGH thread: price the first one */
				two_high = true;
				learn_clock(&now);
				late = (int64_t)(POLICY_RESCUE_LATE_US -
						 POLICY_RESCUE_COST_US) *
				       cycles_per_us;
				bc = pair_cost(ps, bth);
				bs = capped_slack(bth, bc, now);
				if (bs >= late) {
					uth = bth;
					ubest = best;
					us = bs;
				}
			}
			c = pair_cost(ps, th);
			s = capped_slack(th, c, now);
			/* least slack among the threads not too late */
			if (s >= late && (!uth || s < us)) {
				uth = th;
				ubest = i;
				us = s;
			}
			if (learn_before(th, c, s < late, bth, bc, bs < late)) {
				best = i;
				bth = th;
				bc = c;
				bs = s;
			}
		}
	}

	/* p4's rescue check, with the capped length of the chosen thread */
	if (uth && uth != bth && us < late + (int64_t)bc) {
		best = ubest;
		bth = uth;
	}

	/* time this pick (as in p5), under the chosen thread's learning key */
	if (bth->prio_class == THREAD_PRIO_HIGH && bth->service_tsc &&
	    n - 1 >= POLICY_LEARN_MIN_LEFT) {
		ps[0] = learn_clock(&now);
		ps[1] = pair_key(bth, sjf_service(bth));
		ps[2] = learn_mark(sched_rq_at(k, best == n - 1 ? n - 2 : n - 1));
	}
	return best;
}

/* p10: two capped labels in the wrong order (see mixed_costs()) both count
 * this many us less than the smaller of their caps */
#define POLICY_MIXED_DROP_US	4

/*
 * p10: the length of each label in p5's table (k->policy_state[]), in slot
 * order, into @lc. Each starts as p9's capped length: the run time learned
 * for the label, at most POLICY_CAP_UP_US above its hint plus
 * POLICY_RESCUE_COST_US. Two capped labels are in the wrong order when the
 * one that measured longer has the smaller cap, so it counts shorter than a
 * label that measured shorter (w10: puts and syncs at 13 us, gets and
 * multigets at 14 us). Both are then mixes of quick and long requests that
 * the caps cannot rank, and both count the same length, POLICY_MIXED_DROP_US
 * below the smaller cap. Unless two labels are capped and in the wrong
 * order, every length is p9's.
 */
static void mixed_costs(const uint64_t *ps, uint64_t *lc)
{
	uint64_t raw[POLICY_LEARN_SLOTS], cap[POLICY_LEARN_SLOTS], shared;
	uint64_t up = (uint64_t)POLICY_CAP_UP_US * cycles_per_us;
	int a, b, capped = 0;

	for (a = 0; a < POLICY_LEARN_SLOTS; a++) {
		raw[a] = ps[POLICY_LEARN_FIRST + a] & 0xffffffffULL;
		cap[a] = learn_floor((ps[POLICY_LEARN_FIRST + a] >> 32) &
				     ~POLICY_PAIR_RELAXED) + up;
		if (raw[a] > cap[a]) {
			lc[a] = cap[a];
			capped++;
		} else {
			lc[a] = raw[a];
		}
	}
	if (capped < 2)
		return;
	for (a = 0; a < POLICY_LEARN_SLOTS; a++) {
		for (b = 0; b < POLICY_LEARN_SLOTS; b++) {
			/* both capped, b measured longer but counts shorter */
			if (raw[a] <= cap[a] || raw[b] <= cap[b] ||
			    raw[b] <= raw[a] || cap[b] >= cap[a])
				continue;
			shared = cap[b] - (uint64_t)POLICY_MIXED_DROP_US *
					  cycles_per_us;
			if (shared < lc[a])
				lc[a] = shared;
			if (shared < lc[b])
				lc[b] = shared;
		}
	}
}

/* p10: expected length of HIGH thread @th: p9's pair_cost(), with the
 * length of its label taken from @lc (filled by mixed_costs()) */
static inline uint64_t mixed_cost(const uint64_t *ps, const uint64_t *lc,
				  const thread_t *th)
{
	uint64_t hint = sjf_service(th), key;
	int i;

	if (!hint)
		return (uint64_t)POLICY_CAP_BLANK_US * cycles_per_us;
	key = pair_key(th, hint);
	for (i = 0; i < POLICY_LEARN_SLOTS; i++) {
		if ((ps[POLICY_LEARN_FIRST + i] >> 32) == key)
			return lc[i];
	}
	return learn_floor(hint);
}

/*
 * p10 "sjf_mixed": p9's order, timing, learning keys and capped lengths (see
 * choose_sjf_pair()), with one change, in mixed_costs(): two capped labels
 * whose caps rank them against what was measured count one shared length,
 * POLICY_MIXED_DROP_US below the smaller cap. On w10, gets share their label
 * with 30 us multigets, as puts share theirs with 30 us syncs; p9 caps the
 * first at 14 us and the second at 13 us, so gets wait behind puts and
 * syncs, and once too late they also step aside for them. With both labels
 * at 9 us, gets and puts take turns by deadline, and both move further
 * ahead of queries. Where no two capped labels are in the wrong order
 * (w1-w9), every length, and so every decision, is p9's. Lengths are worked
 * out once per pick, only when two HIGH threads are queued; the clock is
 * read at most once per pick. Without HIGH threads this is p4's path and the
 * clock is never read.
 */
static uint32_t choose_sjf_mixed(struct kthread *k, uint32_t n)
{
	uint64_t *ps = k->policy_state;
	uint64_t lc[POLICY_LEARN_SLOTS];
	thread_t *th, *bth, *uth = NULL;
	uint8_t r, rank;
	uint32_t i, best = 0, ubest = 0;
	int64_t s, bs = 0, us = 0, late = 0;
	uint64_t now = 0, c, bc = 0;
	bool two_high = false;

	/* close the sample of this core's previous timed pick (as in p9) */
	if (ps[0]) {
		learn_clock(&now);
		for (i = 0; i < n; i++) {
			if (learn_mark(sched_rq_at(k, i)) == ps[2]) {
				pair_update(ps, ps[1], now - ps[0]);
				break;
			}
		}
		ps[0] = 0;
	}

	th = bth = sched_rq_at(k, 0);
	rank = prio_rank[th->prio_class];
	if (rank == prio_rank[THREAD_PRIO_SOFTIRQ])
		return 0;

	for (i = 1; i < n; i++) {
		th = sched_rq_at(k, i);
		r = prio_rank[th->prio_class];
		if (r > rank) {
			/* a more important class: helpers run at once */
			if (r == prio_rank[THREAD_PRIO_SOFTIRQ])
				return i;
			rank = r;
			best = i;
			bth = th;
		} else if (r == rank && r == prio_rank[THREAD_PRIO_HIGH]) {
			if (!two_high) {
				/* a second HIGH thread: price the labels, then
				 * the first thread */
				two_high = true;
				learn_clock(&now);
				mixed_costs(ps, lc);
				late = (int64_t)(POLICY_RESCUE_LATE_US -
						 POLICY_RESCUE_COST_US) *
				       cycles_per_us;
				bc = mixed_cost(ps, lc, bth);
				bs = capped_slack(bth, bc, now);
				if (bs >= late) {
					uth = bth;
					ubest = best;
					us = bs;
				}
			}
			c = mixed_cost(ps, lc, th);
			s = capped_slack(th, c, now);
			/* least slack among the threads not too late */
			if (s >= late && (!uth || s < us)) {
				uth = th;
				ubest = i;
				us = s;
			}
			if (learn_before(th, c, s < late, bth, bc, bs < late)) {
				best = i;
				bth = th;
				bc = c;
				bs = s;
			}
		}
	}

	/* p4's rescue check, with the length of the chosen thread */
	if (uth && uth != bth && us < late + (int64_t)bc) {
		best = ubest;
		bth = uth;
	}

	/* time this pick (as in p9), under the chosen thread's learning key */
	if (bth->prio_class == THREAD_PRIO_HIGH && bth->service_tsc &&
	    n - 1 >= POLICY_LEARN_MIN_LEFT) {
		ps[0] = learn_clock(&now);
		ps[1] = pair_key(bth, sjf_service(bth));
		ps[2] = learn_mark(sched_rq_at(k, best == n - 1 ? n - 2 : n - 1));
	}
	return best;
}

/*
 * p11: k->policy_state[POLICY_UNIT_SLOT] holds this core's time unit: the
 * tightest relative deadline (deadline minus ready time) of the HIGH
 * threads it has run, in cycles, in the low 32 bits, and that many
 * POLICY_UNIT_US rounded to the nearest whole number, at least 1, in the
 * high 32 bits (0 = nothing seen yet, which counts as 1). p5's learning
 * table keeps the slots from POLICY_LEARN_FIRST up to POLICY_UNIT_SLOT - 1.
 */
#define POLICY_UNIT_SLOT	7
#define POLICY_UNIT_LEARN_SLOTS	(POLICY_UNIT_SLOT - POLICY_LEARN_FIRST)
/* p11: one time unit per this many us of the tightest relative deadline:
 * 1 on w1-w10 (60 and 100 us), 4 on w11 (400 us) */
#define POLICY_UNIT_US		100
/* p11: a looser deadline raises the remembered tightest one by 1/2^8 of
 * the gap (a tighter one lowers it at once), so one thread that was
 * readied late cannot hold the unit down for good */
#define POLICY_UNIT_RISE_SHIFT	8

/* p11: this core's time unit (see POLICY_UNIT_SLOT) */
static inline uint64_t unit_get(const uint64_t *ps)
{
	uint64_t u = ps[POLICY_UNIT_SLOT] >> 32;

	return u ? u : 1;
}

/*
 * p11: folds the relative deadline of HIGH thread @th, which this core is
 * about to run, into its tightest relative deadline. If that moves the time
 * unit, the learning table is cleared: its keys, limits and caps belong to
 * the old unit (in practice this happens once per core, at startup).
 */
static void unit_observe(uint64_t *ps, const thread_t *th)
{
	uint64_t w = ps[POLICY_UNIT_SLOT], m = w & 0xffffffffULL, r, u;
	uint64_t unit = (uint64_t)POLICY_UNIT_US * cycles_per_us;
	int64_t rel;
	int i;

	if (!th->deadline_tsc)
		return;
	rel = (int64_t)(th->deadline_tsc - th->ready_tsc);
	if (rel <= 0)
		return;
	r = rel < 0xffffffffLL ? (uint64_t)rel : 0xffffffffULL;
	if (!w || r < m)
		m = r;
	else
		m += (r - m) >> POLICY_UNIT_RISE_SHIFT;
	u = (m + unit / 2) / unit;
	if (!u)
		u = 1;
	if (u != unit_get(ps)) {
		for (i = POLICY_LEARN_FIRST; i < POLICY_UNIT_SLOT; i++)
			ps[i] = 0;
	}
	ps[POLICY_UNIT_SLOT] = (u << 32) | m;
}

/* p11: @us microseconds of run-time allowance in unit @u, in cycles: @us
 * at a unit of 1, and half of @us more for each further unit (w11: 2.5
 * times), so a capped label stays well below the queries' length */
static inline uint64_t unit_allow(uint64_t us, uint64_t u)
{
	return us * (u + 1) / 2 * cycles_per_us;
}

/* p11: p9's pair_key() with the split at @u times POLICY_PAIR_SPLIT_US */
static inline uint64_t unit_key(const thread_t *th, uint64_t hint, uint64_t u)
{
	if (th->deadline_tsc &&
	    (int64_t)(th->deadline_tsc - th->ready_tsc) >
	    (int64_t)(POLICY_PAIR_SPLIT_US * u) * cycles_per_us)
		return hint | POLICY_PAIR_RELAXED;
	return hint;
}

/* p11: p9's pair_update() with the drop limit's allowance at @u times
 * POLICY_LEARN_CAP_US, over the learning slots below POLICY_UNIT_SLOT */
static void unit_update(uint64_t *ps, uint64_t key, uint64_t sample,
			uint64_t u)
{
	uint64_t fl = learn_floor(key & ~POLICY_PAIR_RELAXED), e;
	int i, slot = -1;

	if (sample > 2 * fl + POLICY_LEARN_CAP_US * u * cycles_per_us)
		return;
	for (i = POLICY_LEARN_FIRST; i < POLICY_UNIT_SLOT; i++) {
		if ((ps[i] >> 32) == key) {
			slot = i;
			break;
		}
		if (!ps[i] && slot < 0)
			slot = i;
	}
	if (slot < 0)
		return;
	e = ps[slot] ? (ps[slot] & 0xffffffffULL) : fl;
	if (sample > e)
		e += (sample - e) >> POLICY_LEARN_UP_SHIFT;
	else
		e -= (e - sample) >> POLICY_LEARN_DOWN_SHIFT;
	ps[slot] = (key << 32) | e;
}

/* p11: p10's mixed_costs() with the cap allowance unit_allow() of
 * POLICY_CAP_UP_US and the shared length unit_allow() of
 * POLICY_MIXED_DROP_US below the smaller cap, over the learning slots below
 * POLICY_UNIT_SLOT */
static void unit_costs(const uint64_t *ps, uint64_t *lc, uint64_t u)
{
	uint64_t raw[POLICY_UNIT_LEARN_SLOTS], cap[POLICY_UNIT_LEARN_SLOTS];
	uint64_t up = unit_allow(POLICY_CAP_UP_US, u), shared;
	int a, b, capped = 0;

	for (a = 0; a < POLICY_UNIT_LEARN_SLOTS; a++) {
		raw[a] = ps[POLICY_LEARN_FIRST + a] & 0xffffffffULL;
		cap[a] = learn_floor((ps[POLICY_LEARN_FIRST + a] >> 32) &
				     ~POLICY_PAIR_RELAXED) + up;
		if (raw[a] > cap[a]) {
			lc[a] = cap[a];
			capped++;
		} else {
			lc[a] = raw[a];
		}
	}
	if (capped < 2)
		return;
	for (a = 0; a < POLICY_UNIT_LEARN_SLOTS; a++) {
		for (b = 0; b < POLICY_UNIT_LEARN_SLOTS; b++) {
			/* both capped, b measured longer but counts shorter */
			if (raw[a] <= cap[a] || raw[b] <= cap[b] ||
			    raw[b] <= raw[a] || cap[b] >= cap[a])
				continue;
			shared = cap[b] - unit_allow(POLICY_MIXED_DROP_US, u);
			if (shared < lc[a])
				lc[a] = shared;
			if (shared < lc[b])
				lc[b] = shared;
		}
	}
}

/* p11: p10's mixed_cost() under unit_key(), with a thread without a
 * run-time hint counting unit_allow() of POLICY_CAP_BLANK_US */
static inline uint64_t unit_cost(const uint64_t *ps, const uint64_t *lc,
				 const thread_t *th, uint64_t u)
{
	uint64_t hint = sjf_service(th), key;
	int i;

	if (!hint)
		return unit_allow(POLICY_CAP_BLANK_US, u);
	key = unit_key(th, hint, u);
	for (i = 0; i < POLICY_UNIT_LEARN_SLOTS; i++) {
		if ((ps[POLICY_LEARN_FIRST + i] >> 32) == key)
			return lc[i];
	}
	return learn_floor(hint);
}

/*
 * p11 "sjf_unit": p10's order, timing, learning and lengths (see
 * choose_sjf_mixed()), with every constant that compares run times measured
 * in a time unit that each core reads from the deadlines it sees: the
 * tightest relative deadline of the HIGH threads it runs, in multiples of
 * POLICY_UNIT_US (unit_observe()). Spans of time are multiplied by the
 * unit: the deadline split between learning keys (POLICY_PAIR_SPLIT_US)
 * and the drop limit's allowance for long samples (POLICY_LEARN_CAP_US).
 * Allowances on a length grow by half a step per unit (unit_allow()): the
 * cap above a hint (POLICY_CAP_UP_US), the length of a thread without a
 * run-time hint (POLICY_CAP_BLANK_US) and p10's shared-length drop
 * (POLICY_MIXED_DROP_US). The per-request cost and the too-late line stay
 * in us: they are network and runtime time, which does not scale with the
 * requests. On w1-w10 the unit is 1 and every decision is p10's; on w11
 * (400 us deadlines) it is 4, so 120 us syncs and flushes are no longer
 * dropped as glitches, the '4 us' label counts its 28 us cap behind gets
 * (about 10 us), and multigets (1200 us) are learned apart from gets
 * (400 us). The clock is read at most once per pick. Without HIGH threads
 * this is p4's path and the clock is never read.
 */
static uint32_t choose_sjf_unit(struct kthread *k, uint32_t n)
{
	uint64_t *ps = k->policy_state;
	uint64_t lc[POLICY_UNIT_LEARN_SLOTS], u = unit_get(ps);
	thread_t *th, *bth, *uth = NULL;
	uint8_t r, rank;
	uint32_t i, best = 0, ubest = 0;
	int64_t s, bs = 0, us = 0, late = 0;
	uint64_t now = 0, c, bc = 0;
	bool two_high = false;

	/* close the sample of this core's previous timed pick (as in p9) */
	if (ps[0]) {
		learn_clock(&now);
		for (i = 0; i < n; i++) {
			if (learn_mark(sched_rq_at(k, i)) == ps[2]) {
				unit_update(ps, ps[1], now - ps[0], u);
				break;
			}
		}
		ps[0] = 0;
	}

	th = bth = sched_rq_at(k, 0);
	rank = prio_rank[th->prio_class];
	if (rank == prio_rank[THREAD_PRIO_SOFTIRQ])
		return 0;

	for (i = 1; i < n; i++) {
		th = sched_rq_at(k, i);
		r = prio_rank[th->prio_class];
		if (r > rank) {
			/* a more important class: helpers run at once */
			if (r == prio_rank[THREAD_PRIO_SOFTIRQ])
				return i;
			rank = r;
			best = i;
			bth = th;
		} else if (r == rank && r == prio_rank[THREAD_PRIO_HIGH]) {
			if (!two_high) {
				/* a second HIGH thread: price the labels, then
				 * the first thread */
				two_high = true;
				learn_clock(&now);
				unit_costs(ps, lc, u);
				late = (int64_t)(POLICY_RESCUE_LATE_US -
						 POLICY_RESCUE_COST_US) *
				       cycles_per_us;
				bc = unit_cost(ps, lc, bth, u);
				bs = capped_slack(bth, bc, now);
				if (bs >= late) {
					uth = bth;
					ubest = best;
					us = bs;
				}
			}
			c = unit_cost(ps, lc, th, u);
			s = capped_slack(th, c, now);
			/* least slack among the threads not too late */
			if (s >= late && (!uth || s < us)) {
				uth = th;
				ubest = i;
				us = s;
			}
			if (learn_before(th, c, s < late, bth, bc, bs < late)) {
				best = i;
				bth = th;
				bc = c;
				bs = s;
			}
		}
	}

	/* p4's rescue check, with the length of the chosen thread */
	if (uth && uth != bth && us < late + (int64_t)bc) {
		best = ubest;
		bth = uth;
	}

	if (bth->prio_class != THREAD_PRIO_HIGH)
		return best;

	/* learn the unit from the chosen thread's deadline */
	unit_observe(ps, bth);

	/* time this pick (as in p9), under the chosen thread's learning key */
	if (bth->service_tsc && n - 1 >= POLICY_LEARN_MIN_LEFT) {
		ps[0] = learn_clock(&now);
		ps[1] = unit_key(bth, sjf_service(bth), unit_get(ps));
		ps[2] = learn_mark(sched_rq_at(k, best == n - 1 ? n - 2 : n - 1));
	}
	return best;
}

/*
 * p12: this core's time unit, kept in the high 32 bits of
 * k->policy_state[1] (the low 32 bits keep p9's learning key of the pending
 * timed pick): bits 24-31 hold the unit (0 = nothing seen yet, which counts
 * as 1), bits 0-23 a running median of the relative deadlines (deadline
 * minus ready time) of the HIGH threads this core runs, in units of
 * 2^POLICY_SCALE_SHIFT cycles. p5's learning table keeps all five slots.
 */
#define POLICY_SCALE_SHIFT	6
/* p12: the median moves this many us toward each relative deadline seen, so
 * it settles where half the HIGH work lies on each side; a thread readied
 * again after a time-slice yield shows a smaller relative deadline, but such
 * threads are a small minority and move the median by one step at most */
#define POLICY_SCALE_STEP_US	2
/* p12: a median below this many us gives a unit of 1 (w1-w10: 60-200 us);
 * from it the unit is the median in POLICY_UNIT_US, rounded (w11, w12: 4) */
#define POLICY_SCALE_MIN_US	350

/* p12: this core's time unit (see above) */
static inline uint64_t scale_get(const uint64_t *ps)
{
	uint64_t u = (ps[1] >> 56) & 0xffULL;

	return u ? u : 1;
}

/*
 * p12: folds the relative deadline of HIGH thread @th, which this core is
 * about to run, into the running median and recomputes the unit. If the
 * unit changes, the learning table is cleared: its keys, limits and caps
 * belong to the old unit (on w11 and w12 this happens once per core, at
 * startup; on w1-w10 never).
 */
static void scale_observe(uint64_t *ps, const thread_t *th)
{
	uint64_t w = ps[1] >> 32, m = (w & 0xffffffULL) << POLICY_SCALE_SHIFT;
	uint64_t step = (uint64_t)POLICY_SCALE_STEP_US * cycles_per_us;
	uint64_t unit = (uint64_t)POLICY_UNIT_US * cycles_per_us;
	uint64_t top = 0xffffffULL << POLICY_SCALE_SHIFT, r, u;
	int64_t rel;
	int i;

	if (!th->deadline_tsc)
		return;
	rel = (int64_t)(th->deadline_tsc - th->ready_tsc);
	if (rel <= 0)
		return;
	r = (uint64_t)rel < top ? (uint64_t)rel : top;
	if (!w)
		m = r;
	else if (r > m)
		m += MIN(step, r - m);
	else
		m -= MIN(step, m - r);
	u = 1;
	if (m >= (uint64_t)POLICY_SCALE_MIN_US * cycles_per_us)
		u = MIN((m + unit / 2) / unit, 0xffULL);
	if (u != scale_get(ps)) {
		for (i = POLICY_LEARN_FIRST;
		     i < POLICY_LEARN_FIRST + POLICY_LEARN_SLOTS; i++)
			ps[i] = 0;
	}
	ps[1] = (u << 56) | ((m >> POLICY_SCALE_SHIFT) << 32) |
		(ps[1] & 0xffffffffULL);
}

/* p12: p11's unit_update() over all five learning slots */
static void scale_update(uint64_t *ps, uint64_t key, uint64_t sample,
			 uint64_t u)
{
	uint64_t fl = learn_floor(key & ~POLICY_PAIR_RELAXED), e;
	int i, slot = -1;

	if (sample > 2 * fl + POLICY_LEARN_CAP_US * u * cycles_per_us)
		return;
	for (i = POLICY_LEARN_FIRST;
	     i < POLICY_LEARN_FIRST + POLICY_LEARN_SLOTS; i++) {
		if ((ps[i] >> 32) == key) {
			slot = i;
			break;
		}
		if (!ps[i] && slot < 0)
			slot = i;
	}
	if (slot < 0)
		return;
	e = ps[slot] ? (ps[slot] & 0xffffffffULL) : fl;
	if (sample > e)
		e += (sample - e) >> POLICY_LEARN_UP_SHIFT;
	else
		e -= (e - sample) >> POLICY_LEARN_DOWN_SHIFT;
	ps[slot] = (key << 32) | e;
}

/* p12: p11's unit_costs() over all five learning slots */
static void scale_costs(const uint64_t *ps, uint64_t *lc, uint64_t u)
{
	uint64_t raw[POLICY_LEARN_SLOTS], cap[POLICY_LEARN_SLOTS];
	uint64_t up = unit_allow(POLICY_CAP_UP_US, u), shared;
	int a, b, capped = 0;

	for (a = 0; a < POLICY_LEARN_SLOTS; a++) {
		raw[a] = ps[POLICY_LEARN_FIRST + a] & 0xffffffffULL;
		cap[a] = learn_floor((ps[POLICY_LEARN_FIRST + a] >> 32) &
				     ~POLICY_PAIR_RELAXED) + up;
		if (raw[a] > cap[a]) {
			lc[a] = cap[a];
			capped++;
		} else {
			lc[a] = raw[a];
		}
	}
	if (capped < 2)
		return;
	for (a = 0; a < POLICY_LEARN_SLOTS; a++) {
		for (b = 0; b < POLICY_LEARN_SLOTS; b++) {
			/* both capped, b measured longer but counts shorter */
			if (raw[a] <= cap[a] || raw[b] <= cap[b] ||
			    raw[b] <= raw[a] || cap[b] >= cap[a])
				continue;
			shared = cap[b] - unit_allow(POLICY_MIXED_DROP_US, u);
			if (shared < lc[a])
				lc[a] = shared;
			if (shared < lc[b])
				lc[b] = shared;
		}
	}
}

/* p12: p9's pair_key() with the split grown by half a step per unit, as
 * p11's allowances: 250 us at a unit of 1, 625 us at 4 (w12: gets and puts
 * at 400 us apart from multigets at 1200 us, even after a multiget yielded
 * its core at the 100 us time slice and was readied again late) */
static inline uint64_t scale_key(const thread_t *th, uint64_t hint, uint64_t u)
{
	if (th->deadline_tsc &&
	    (int64_t)(th->deadline_tsc - th->ready_tsc) >
	    (int64_t)unit_allow(POLICY_PAIR_SPLIT_US, u))
		return hint | POLICY_PAIR_RELAXED;
	return hint;
}

/* p12: p11's unit_cost() under scale_key(), over all five learning slots */
static inline uint64_t scale_cost(const uint64_t *ps, const uint64_t *lc,
				  const thread_t *th, uint64_t u)
{
	uint64_t hint = sjf_service(th), key;
	int i;

	if (!hint)
		return unit_allow(POLICY_CAP_BLANK_US, u);
	key = scale_key(th, hint, u);
	for (i = 0; i < POLICY_LEARN_SLOTS; i++) {
		if ((ps[POLICY_LEARN_FIRST + i] >> 32) == key)
			return lc[i];
	}
	return learn_floor(hint);
}

/*
 * p12 "sjf_scale": p11's scaled constants (see choose_sjf_unit()), except
 * that the deadline split grows by half a step per unit (scale_key()), with
 * the time unit read from the median relative deadline of the HIGH threads
 * each core runs instead of the tightest (scale_observe()), kept beside the
 * pending pick's key so all five learning slots stay p10's. On w12 the median
 * is 400 us even though leases carry 100 us, and on w11 too, where re-queued
 * threads pinned p11's tightest deadline low: a request running past the
 * IOKernel's 100 us time slice is yielded and readied again with a new ready
 * time, so its deadline minus ready time shrinks. Below a 350 us median the
 * unit is 1 and every decision is p10's (w1-w10). The clock is read at most
 * once per pick. Without HIGH threads this is p4's path and the clock is
 * never read.
 */
static uint32_t choose_sjf_scale(struct kthread *k, uint32_t n)
{
	uint64_t *ps = k->policy_state;
	uint64_t lc[POLICY_LEARN_SLOTS], u = scale_get(ps);
	thread_t *th, *bth, *uth = NULL;
	uint8_t r, rank;
	uint32_t i, best = 0, ubest = 0;
	int64_t s, bs = 0, us = 0, late = 0;
	uint64_t now = 0, c, bc = 0;
	bool two_high = false;

	/* close the sample of this core's previous timed pick (as in p9) */
	if (ps[0]) {
		learn_clock(&now);
		for (i = 0; i < n; i++) {
			if (learn_mark(sched_rq_at(k, i)) == ps[2]) {
				scale_update(ps, ps[1] & 0xffffffffULL,
					     now - ps[0], u);
				break;
			}
		}
		ps[0] = 0;
	}

	th = bth = sched_rq_at(k, 0);
	rank = prio_rank[th->prio_class];
	if (rank == prio_rank[THREAD_PRIO_SOFTIRQ])
		return 0;

	for (i = 1; i < n; i++) {
		th = sched_rq_at(k, i);
		r = prio_rank[th->prio_class];
		if (r > rank) {
			/* a more important class: helpers run at once */
			if (r == prio_rank[THREAD_PRIO_SOFTIRQ])
				return i;
			rank = r;
			best = i;
			bth = th;
		} else if (r == rank && r == prio_rank[THREAD_PRIO_HIGH]) {
			if (!two_high) {
				/* a second HIGH thread: price the labels, then
				 * the first thread */
				two_high = true;
				learn_clock(&now);
				scale_costs(ps, lc, u);
				late = (int64_t)(POLICY_RESCUE_LATE_US -
						 POLICY_RESCUE_COST_US) *
				       cycles_per_us;
				bc = scale_cost(ps, lc, bth, u);
				bs = capped_slack(bth, bc, now);
				if (bs >= late) {
					uth = bth;
					ubest = best;
					us = bs;
				}
			}
			c = scale_cost(ps, lc, th, u);
			s = capped_slack(th, c, now);
			/* least slack among the threads not too late */
			if (s >= late && (!uth || s < us)) {
				uth = th;
				ubest = i;
				us = s;
			}
			if (learn_before(th, c, s < late, bth, bc, bs < late)) {
				best = i;
				bth = th;
				bc = c;
				bs = s;
			}
		}
	}

	/* p4's rescue check, with the length of the chosen thread */
	if (uth && uth != bth && us < late + (int64_t)bc) {
		best = ubest;
		bth = uth;
	}

	if (bth->prio_class != THREAD_PRIO_HIGH)
		return best;

	/* fold the chosen thread's deadline into the median and the unit */
	scale_observe(ps, bth);

	/* time this pick (as in p9), under the chosen thread's learning key */
	if (bth->service_tsc && n - 1 >= POLICY_LEARN_MIN_LEFT) {
		ps[0] = learn_clock(&now);
		ps[1] = (ps[1] & ~0xffffffffULL) |
			scale_key(bth, sjf_service(bth), scale_get(ps));
		ps[2] = learn_mark(sched_rq_at(k, best == n - 1 ? n - 2 : n - 1));
	}
	return best;
}

/*
 * p13: p12's running estimate of the relative deadlines (deadline minus
 * ready time) of the HIGH threads a core runs, kept in the same bits of
 * k->policy_state[1], but stepping POLICY_UPPER_UP times further up than
 * down: it settles where a quarter of the HIGH picks lie above it (an upper
 * quartile) instead of half. w13: 61% of picks carry at most 300 us (leases,
 * 300 us queries, re-queued remnants), 39% at least 400 us, 10% about
 * 1000-1200 us (multigets and their remnants), so it settles at 400 us;
 * w11, w12: also 400 us; w1-w10: every deadline is at most 300 us, and the
 * estimate never passes the largest value seen, so the unit stays 1.
 */
#define POLICY_UPPER_UP		3

/*
 * p13: p12's scale_observe() with the upper-quartile step and hysteresis:
 * from a unit of 1 the unit rises when the estimate reaches
 * POLICY_SCALE_MIN_US (as p12); a unit above 1 is kept until the estimate
 * is a whole POLICY_UNIT_US away from it (w13: kept from 300 to 500 us), so
 * a run of short-deadline picks cannot flip it and clear the table.
 */
static void upper_observe(uint64_t *ps, const thread_t *th)
{
	uint64_t w = ps[1] >> 32, m = (w & 0xffffffULL) << POLICY_SCALE_SHIFT;
	uint64_t step = (uint64_t)POLICY_SCALE_STEP_US * cycles_per_us;
	uint64_t unit = (uint64_t)POLICY_UNIT_US * cycles_per_us;
	uint64_t min = (uint64_t)POLICY_SCALE_MIN_US * cycles_per_us;
	uint64_t top = 0xffffffULL << POLICY_SCALE_SHIFT, r, u, cur;
	int64_t rel;
	int i;

	if (!th->deadline_tsc)
		return;
	rel = (int64_t)(th->deadline_tsc - th->ready_tsc);
	if (rel <= 0)
		return;
	r = (uint64_t)rel < top ? (uint64_t)rel : top;
	if (!w)
		m = r;
	else if (r > m)
		m += MIN(POLICY_UPPER_UP * step, r - m);
	else
		m -= MIN(step, m - r);
	cur = scale_get(ps);
	u = cur;
	if (cur == 1 ? m >= min :
	    m + unit < cur * unit || m >= (cur + 1) * unit) {
		u = 1;
		if (m >= min)
			u = MIN((m + unit / 2) / unit, 0xffULL);
	}
	if (u != cur) {
		for (i = POLICY_LEARN_FIRST;
		     i < POLICY_LEARN_FIRST + POLICY_LEARN_SLOTS; i++)
			ps[i] = 0;
	}
	ps[1] = (u << 56) | ((m >> POLICY_SCALE_SHIFT) << 32) |
		(ps[1] & 0xffffffffULL);
}

/*
 * p13 "sjf_upper": p12's sjf_scale (see choose_sjf_scale()) with the time
 * unit read from an upper quartile of the relative deadlines of the HIGH
 * threads each core runs instead of their median, with hysteresis
 * (upper_observe()). On w13 half the HIGH picks are 300 us queries, so
 * p12's median sits at 300 us and its unit is 1, which makes p10's
 * decisions: syncs and flushes hide behind the puts' hint and run ahead of
 * gets, and gets share a label with multigets. The upper quartile sits at
 * the 400 us that gets, puts and syncs carry, so the unit is 4 as on w12
 * and leases still turn first. On w11 and w12 the unit is 4 and on w1-w10
 * it is 1, as under p12. The clock is read at most once per pick. Without
 * HIGH threads this is p4's path and the clock is never read.
 */
static uint32_t choose_sjf_upper(struct kthread *k, uint32_t n)
{
	uint64_t *ps = k->policy_state;
	uint64_t lc[POLICY_LEARN_SLOTS], u = scale_get(ps);
	thread_t *th, *bth, *uth = NULL;
	uint8_t r, rank;
	uint32_t i, best = 0, ubest = 0;
	int64_t s, bs = 0, us = 0, late = 0;
	uint64_t now = 0, c, bc = 0;
	bool two_high = false;

	/* close the sample of this core's previous timed pick (as in p9) */
	if (ps[0]) {
		learn_clock(&now);
		for (i = 0; i < n; i++) {
			if (learn_mark(sched_rq_at(k, i)) == ps[2]) {
				scale_update(ps, ps[1] & 0xffffffffULL,
					     now - ps[0], u);
				break;
			}
		}
		ps[0] = 0;
	}

	th = bth = sched_rq_at(k, 0);
	rank = prio_rank[th->prio_class];
	if (rank == prio_rank[THREAD_PRIO_SOFTIRQ])
		return 0;

	for (i = 1; i < n; i++) {
		th = sched_rq_at(k, i);
		r = prio_rank[th->prio_class];
		if (r > rank) {
			/* a more important class: helpers run at once */
			if (r == prio_rank[THREAD_PRIO_SOFTIRQ])
				return i;
			rank = r;
			best = i;
			bth = th;
		} else if (r == rank && r == prio_rank[THREAD_PRIO_HIGH]) {
			if (!two_high) {
				/* a second HIGH thread: price the labels, then
				 * the first thread */
				two_high = true;
				learn_clock(&now);
				scale_costs(ps, lc, u);
				late = (int64_t)(POLICY_RESCUE_LATE_US -
						 POLICY_RESCUE_COST_US) *
				       cycles_per_us;
				bc = scale_cost(ps, lc, bth, u);
				bs = capped_slack(bth, bc, now);
				if (bs >= late) {
					uth = bth;
					ubest = best;
					us = bs;
				}
			}
			c = scale_cost(ps, lc, th, u);
			s = capped_slack(th, c, now);
			/* least slack among the threads not too late */
			if (s >= late && (!uth || s < us)) {
				uth = th;
				ubest = i;
				us = s;
			}
			if (learn_before(th, c, s < late, bth, bc, bs < late)) {
				best = i;
				bth = th;
				bc = c;
				bs = s;
			}
		}
	}

	/* p4's rescue check, with the length of the chosen thread */
	if (uth && uth != bth && us < late + (int64_t)bc) {
		best = ubest;
		bth = uth;
	}

	if (bth->prio_class != THREAD_PRIO_HIGH)
		return best;

	/* fold the chosen thread's deadline into the quartile and the unit */
	upper_observe(ps, bth);

	/* time this pick (as in p9), under the chosen thread's learning key */
	if (bth->service_tsc && n - 1 >= POLICY_LEARN_MIN_LEFT) {
		ps[0] = learn_clock(&now);
		ps[1] = (ps[1] & ~0xffffffffULL) |
			scale_key(bth, sjf_service(bth), scale_get(ps));
		ps[2] = learn_mark(sched_rq_at(k, best == n - 1 ? n - 2 : n - 1));
	}
	return best;
}

/*
 * p14: at a time unit above 1, p4's rescue check lets an urgent HIGH thread
 * pass the chosen one only if it is at most this many times as long: w14's
 * urgent 68 us queries no longer pass 7 us gets (about 6-7 times shorter)
 * or 2 us leases, but still pass the puts' and syncs' capped label (about
 * 2.6 times shorter) and multigets
 */
#define POLICY_RATIO_MAX	3

/*
 * p14 "sjf_ratio": p13's sjf_upper (see choose_sjf_upper()) with one change
 * to p4's rescue check. When the core's time unit is above 1 (w11-w14), a
 * HIGH thread about to become too late runs ahead of the thread the order
 * chose only if its length is at most POLICY_RATIO_MAX times the chosen
 * one's. A rescued 68 us query delays a waiting 7 us get by about six times
 * what the get would cost the query, and on w13 and w14 such rescues are a
 * large part of the gets' wait. At a unit of 1 (w1-w10) the check is p13's,
 * so every decision is p13's. The clock is read at most once per pick.
 * Without HIGH threads this is p4's path and the clock is never read.
 */
static uint32_t choose_sjf_ratio(struct kthread *k, uint32_t n)
{
	uint64_t *ps = k->policy_state;
	uint64_t lc[POLICY_LEARN_SLOTS], u = scale_get(ps);
	thread_t *th, *bth, *uth = NULL;
	uint8_t r, rank;
	uint32_t i, best = 0, ubest = 0;
	int64_t s, bs = 0, us = 0, late = 0;
	uint64_t now = 0, c, bc = 0, uc = 0;
	bool two_high = false;

	/* close the sample of this core's previous timed pick (as in p9) */
	if (ps[0]) {
		learn_clock(&now);
		for (i = 0; i < n; i++) {
			if (learn_mark(sched_rq_at(k, i)) == ps[2]) {
				scale_update(ps, ps[1] & 0xffffffffULL,
					     now - ps[0], u);
				break;
			}
		}
		ps[0] = 0;
	}

	th = bth = sched_rq_at(k, 0);
	rank = prio_rank[th->prio_class];
	if (rank == prio_rank[THREAD_PRIO_SOFTIRQ])
		return 0;

	for (i = 1; i < n; i++) {
		th = sched_rq_at(k, i);
		r = prio_rank[th->prio_class];
		if (r > rank) {
			/* a more important class: helpers run at once */
			if (r == prio_rank[THREAD_PRIO_SOFTIRQ])
				return i;
			rank = r;
			best = i;
			bth = th;
		} else if (r == rank && r == prio_rank[THREAD_PRIO_HIGH]) {
			if (!two_high) {
				/* a second HIGH thread: price the labels, then
				 * the first thread */
				two_high = true;
				learn_clock(&now);
				scale_costs(ps, lc, u);
				late = (int64_t)(POLICY_RESCUE_LATE_US -
						 POLICY_RESCUE_COST_US) *
				       cycles_per_us;
				bc = scale_cost(ps, lc, bth, u);
				bs = capped_slack(bth, bc, now);
				if (bs >= late) {
					uth = bth;
					ubest = best;
					us = bs;
					uc = bc;
				}
			}
			c = scale_cost(ps, lc, th, u);
			s = capped_slack(th, c, now);
			/* least slack among the threads not too late */
			if (s >= late && (!uth || s < us)) {
				uth = th;
				ubest = i;
				us = s;
				uc = c;
			}
			if (learn_before(th, c, s < late, bth, bc, bs < late)) {
				best = i;
				bth = th;
				bc = c;
				bs = s;
			}
		}
	}

	/* p4's rescue check, with the length of the chosen thread; at a unit
	 * above 1 it never passes a thread under 1/POLICY_RATIO_MAX its length */
	if (uth && uth != bth && us < late + (int64_t)bc &&
	    (u == 1 || uc <= POLICY_RATIO_MAX * bc)) {
		best = ubest;
		bth = uth;
	}

	if (bth->prio_class != THREAD_PRIO_HIGH)
		return best;

	/* fold the chosen thread's deadline into the quartile and the unit */
	upper_observe(ps, bth);

	/* time this pick (as in p9), under the chosen thread's learning key */
	if (bth->service_tsc && n - 1 >= POLICY_LEARN_MIN_LEFT) {
		ps[0] = learn_clock(&now);
		ps[1] = (ps[1] & ~0xffffffffULL) |
			scale_key(bth, sjf_service(bth), scale_get(ps));
		ps[2] = learn_mark(sched_rq_at(k, best == n - 1 ? n - 2 : n - 1));
	}
	return best;
}

static const struct {
	const char		*name;
	sched_choose_fn_t	choose;
} sched_policies[] = {
	{ "fifo",	choose_fifo },
	{ "prio",	choose_prio },
	{ "edf_high",	choose_edf_high },
	{ "sjf_guard",	choose_sjf_guard },
	{ "sjf_rescue",	choose_sjf_rescue },
	{ "sjf_learn",	choose_sjf_learn },
	{ "sjf_timed",	choose_sjf_timed },
	{ "sjf_nohint",	choose_sjf_nohint },
	{ "sjf_capped",	choose_sjf_capped },
	{ "sjf_pair",	choose_sjf_pair },
	{ "sjf_mixed",	choose_sjf_mixed },
	{ "sjf_unit",	choose_sjf_unit },
	{ "sjf_scale",	choose_sjf_scale },
	{ "sjf_upper",	choose_sjf_upper },
	{ "sjf_ratio",	choose_sjf_ratio },
};

/* ===== END SCHEDULING POLICY REGION ======================================== */

/* the active policy (default: strict priority) */
static sched_choose_fn_t sched_choose = choose_prio;
static const char *sched_choose_name = "prio";

/**
 * sched_policy_select - selects the scheduling policy by name
 * @name: a policy name from sched_policies[]
 *
 * Returns 0 if successful, or -EINVAL if there is no such policy.
 */
int sched_policy_select(const char *name)
{
	int i;

	for (i = 0; i < ARRAY_SIZE(sched_policies); i++) {
		if (!strcmp(name, sched_policies[i].name)) {
			sched_choose = sched_policies[i].choose;
			sched_choose_name = sched_policies[i].name;
			return 0;
		}
	}
	return -EINVAL;
}

const char *sched_policy_name(void)
{
	return sched_choose_name;
}

/* per-class counters are indexed by prio_class */
BUILD_ASSERT(STAT_PICK_HIGH == STAT_PICK_NORMAL + THREAD_PRIO_HIGH);
BUILD_ASSERT(STAT_PICK_LOW == STAT_PICK_NORMAL + THREAD_PRIO_LOW);
BUILD_ASSERT(STAT_PICK_SOFTIRQ == STAT_PICK_NORMAL + THREAD_PRIO_SOFTIRQ);
BUILD_ASSERT(STAT_WAIT_CYCLES_SOFTIRQ ==
	     STAT_WAIT_CYCLES_NORMAL + THREAD_PRIO_SOFTIRQ);

/*
 * Records what a pick looked like, for hint-aware measurement: the class of
 * the chosen thread and how long it waited, the runqueue depth, whether a
 * thread of a higher class was left waiting, and deadline misses.
 */
static void sched_count_pick(struct kthread *k, uint32_t n, uint32_t best,
			     thread_t *th)
{
	uint64_t now = rdtsc();
	uint8_t rank = prio_rank[th->prio_class];
	uint32_t i;

	k->stats[STAT_PICK_NORMAL + th->prio_class]++;
	k->stats[STAT_WAIT_CYCLES_NORMAL + th->prio_class] +=
		now - MIN(th->ready_tsc, now);
	k->stats[STAT_PICK_SCANNED] += n;

	for (i = 0; i < n; i++) {
		if (i != best &&
		    prio_rank[sched_rq_at(k, i)->prio_class] > rank) {
			k->stats[STAT_PICK_INVERSIONS]++;
			break;
		}
	}

	if (th->deadline_tsc) {
		k->stats[STAT_PICK_DEADLINE]++;
		if (now > th->deadline_tsc)
			k->stats[STAT_DEADLINE_MISS_AT_PICK]++;
	}
}

/**
 * sched_pop_next - removes and returns the next thread to run
 * @k: the kthread (its lock must be held and its runqueue non-empty)
 *
 * Asks the active policy which ready thread to run, removes it from the ring,
 * and slides the threads queued before it back by one slot so the order of
 * the remaining threads is preserved. Threads in the overflow list are not
 * considered until they move into the ring.
 */
static thread_t *sched_pop_next(struct kthread *k)
{
	uint32_t tail = k->rq_tail, i, best;
	uint32_t n = load_acquire(&k->rq_head) - tail;
	thread_t *th;

	assert_spin_lock_held(&k->lock);
	assert(n > 0 && n <= RUNTIME_RQ_SIZE);

	best = n > 1 ? sched_choose(k, n) : 0;
	BUG_ON(best >= n);
	th = k->rq[(tail + best) % RUNTIME_RQ_SIZE];
	if (cfg_sched_stats)
		sched_count_pick(k, n, best, th);

	/* close the gap: slide the threads queued before @th back by one slot */
	for (i = best; i > 0; i--)
		k->rq[(tail + i) % RUNTIME_RQ_SIZE] =
			k->rq[(tail + i - 1) % RUNTIME_RQ_SIZE];

	k->rq_tail = tail + 1;
	return th;
}
#else
static inline thread_t *sched_pop_next(struct kthread *k)
{
	return k->rq[k->rq_tail++ % RUNTIME_RQ_SIZE];
}

/* without hint support only the stock FIFO order exists */
int sched_policy_select(const char *name)
{
	return strcmp(name, "fifo") ? -EINVAL : 0;
}

const char *sched_policy_name(void)
{
	return "fifo";
}
#endif

static bool work_available(struct kthread *k, uint64_t now_tsc)
{
	return ACCESS_ONCE(k->rq_tail) != ACCESS_ONCE(k->rq_head) ||
	       softirq_pending(k, now_tsc);
}

static void update_oldest_tsc(struct kthread *k)
{
	thread_t *th;

	assert_spin_lock_held(&k->lock);

	/* find the oldest thread in the runqueue */
	if (load_acquire(&k->rq_head) != k->rq_tail) {
		th = k->rq[k->rq_tail % RUNTIME_RQ_SIZE];
		ACCESS_ONCE(k->q_ptrs->oldest_tsc) = th->ready_tsc;
	}
}

/* drain up to nr threads from k's runqueue into list l */
static uint32_t drain_threads(struct kthread *k, struct list_head *l, uint32_t nr, bool update_tail)
{
	uint32_t i, rq_head, rq_tail;
	thread_t *th;

	rq_head = load_acquire(&k->rq_head);
	rq_tail = k->rq_tail;

	for (i = 0; i < nr; i++) {
		if (likely(wraps_lt(rq_tail, rq_head))) {
			th = k->rq[rq_tail++ % RUNTIME_RQ_SIZE];
		} else {
			th = list_pop(&k->rq_overflow, thread_t, link);
			if (!th)
				break;
		}
		if (update_tail && thread_is_hinted(th))
			STAT(HINTED_STOLEN)++;
		list_add_tail(l, &th->link);
	}

	if (update_tail) {
		k->rq_tail = rq_tail;
		ACCESS_ONCE(k->q_ptrs->rq_tail) += i;
	}

	return i;
}

static void merge_runqueues(struct kthread *l, uint32_t lsize, struct kthread *r, uint32_t rsize)
{
	struct list_head l_ths, r_ths;
	thread_t *th, *cur_l, *cur_r;
	uint32_t i;

	assert_preempt_disabled();
	assert_spin_lock_held(&l->lock);
	assert_spin_lock_held(&r->lock);
	assert(myk() == l);

	list_head_init(&r_ths);
	rsize = drain_threads(r, &r_ths, rsize, true /* update_tail */);
	update_oldest_tsc(r);
	spin_unlock(&r->lock);

	list_head_init(&l_ths);
	lsize = drain_threads(l, &l_ths, lsize, false /* update_tail */);

	/* reset rq_head/tail */
	l->rq_head = l->rq_tail = 0;

	cur_r = list_pop(&r_ths, thread_t, link);
	cur_l = list_pop(&l_ths, thread_t, link);

	/* merge together two queues of threads sorted by ready_tsc */
	for (i = 0; i < lsize + rsize; i++) {
		if (cur_r && (!cur_l || cur_r->ready_tsc < cur_l->ready_tsc)) {
			th = cur_r;
			cur_r = list_pop(&r_ths, thread_t, link);
		} else {
			th = cur_l;
			cur_l = list_pop(&l_ths, thread_t, link);
		}

		assert(th);
		if (unlikely(l->rq_head - l->rq_tail >= RUNTIME_RQ_SIZE))
			list_add_tail(&l->rq_overflow, &th->link);
		else
			l->rq[l->rq_head++ % RUNTIME_RQ_SIZE] = th;
	}

	ACCESS_ONCE(l->q_ptrs->rq_head) += rsize;
	update_oldest_tsc(l);
}

static bool steal_work(struct kthread *l, struct kthread *r)
{
	uint64_t now_tsc = rdtsc();
	uint32_t lsize, rsize, num_to_steal = 0;

	assert_spin_lock_held(&l->lock);
	assert(myk() == l);

	if (!work_available(r, now_tsc) || !spin_try_lock(&r->lock))
		return rx_poll_locked(r);

	/* first try to steal directly from the runqueue */
	lsize = l->q_ptrs->rq_head - l->q_ptrs->rq_tail;
	rsize = ACCESS_ONCE(r->q_ptrs->rq_head) - r->q_ptrs->rq_tail;
	if (lsize < rsize)
		num_to_steal = MIN(div_up(rsize - lsize, 2), RUNTIME_RQ_SIZE);
	if (num_to_steal) {
		merge_runqueues(l, lsize, r, num_to_steal);
		return true;
	}

	/* otherwise try to steal softirqs */
	if (softirq_run_locked(r)) {
		STAT(SOFTIRQS_STOLEN)++;
		spin_unlock(&r->lock);
		return true;
	}

	spin_unlock(&r->lock);
	return false;
}

static __noinline bool do_watchdog(struct kthread *l)
{
	bool work;

	assert_spin_lock_held(&l->lock);

	work = softirq_run_locked(l);
	if (work)
		STAT(SOFTIRQS_LOCAL)++;
	return work;
}

/* the main scheduler routine, decides what to run next */
static __noinline void schedule(void)
{
	struct kthread *r = NULL, *l = myk();
	uint64_t prog_cycles, start_tsc;
	thread_t *th;
	unsigned int start_idx;
	unsigned int iters = 0;
	int i, sibling;

	assert_spin_lock_held(&l->lock);
	assert(l->parked == false);

	/* detect misuse of preempt disable */
	BUG_ON((perthread_read(preempt_cnt) & ~PREEMPT_NOT_PENDING) != 1);

	/* update entry stat counters */
	STAT(RESCHEDULES)++;
	start_tsc = rdtsc();
	prog_cycles = start_tsc - perthread_read_stable(last_tsc);
	STAT(PROGRAM_CYCLES) += prog_cycles;

	th = perthread_read_stable(__self);

	/* unmark busy for the stack of the last uthread */
	if (likely(th != NULL)) {
		store_release(&th->thread_running, false);
		th->total_cycles += prog_cycles;
		store_release(&th->cur_kthread, NCPU);
		perthread_store(__self, NULL);
		th = NULL;
	}

	/* increment the RCU generation number (even is in scheduler) */
	store_release(&l->rcu_gen, l->rcu_gen + 1);
	ACCESS_ONCE(l->q_ptrs->rcu_gen) = l->rcu_gen;
	assert((l->rcu_gen & 0x1) == 0x0);

	/* check for pending preemption */
	if (unlikely(preempt_cede_needed(l))) {
		l->parked = true;
		spin_unlock(&l->lock);
		kthread_park_now();
		start_tsc = rdtsc();
		iters = 0;
		spin_lock(&l->lock);
		l->parked = false;
	}

	/* if it's been too long, run the softirq handler */
	if (!disable_watchdog &&
	    unlikely(start_tsc - l->last_softirq_tsc >=
	             cycles_per_us * RUNTIME_WATCHDOG_US)) {
		l->last_softirq_tsc = start_tsc;
		if (do_watchdog(l))
			goto done;
	}

	/* move overflow tasks into the runqueue */
	if (unlikely(!list_empty(&l->rq_overflow)))
		drain_overflow(l);

	/* first try the local runqueue */
	if (l->rq_head != l->rq_tail)
		goto done;

again:

	if (unlikely(!mbufq_empty(&l->txpktq_overflow)))
		net_tx_drain_overflow();

	/* then check for local softirqs */
	if (softirq_run_locked(l)) {
		STAT(SOFTIRQS_LOCAL)++;
		goto done;
	}

	/* then try to steal from a sibling kthread */
	sibling = cpu_map[l->curr_cpu].sibling_core;
	r = cpu_map[sibling].recent_kthread;
	if (r && r != l && steal_work(l, r))
		goto done;

	/* try to steal from every kthread */
	start_idx = hash_crc32c_one((uintptr_t)l, perthread_get_stable(last_tsc));
	for (i = 0; i < maxks; i++) {
		int idx = (start_idx + i) % maxks;
		if (&ks[idx] != l && steal_work(l, &ks[idx]))
			goto done;
	}

	/* recheck for local softirqs one last time */
	if (softirq_run_locked(l)) {
		STAT(SOFTIRQS_LOCAL)++;
		goto done;
	}

	/* keep trying to find work until the polling timeout expires */
	perthread_get_stable(last_tsc) = rdtsc();
	if (!preempt_cede_needed(l) &&
	    (++iters < RUNTIME_SCHED_POLL_ITERS ||
	     perthread_get_stable(last_tsc) - start_tsc < cycles_per_us * RUNTIME_SCHED_MIN_POLL_US ||
	     storage_pending_completions(l) ||
	     !mbufq_empty(&l->txpktq_overflow))) {
		goto again;
	}

	l->parked = true;

	/* did not find anything to run, park this kthread */
	STAT(SCHED_CYCLES) += perthread_get_stable(last_tsc) - start_tsc;
	/* we may have got a preempt signal before voluntarily yielding */
	kthread_park();
	start_tsc = rdtsc();
	iters = 0;

	l->parked = false;
	goto again;

done:
	/* pop off a thread and run it */
	assert(l->rq_head != l->rq_tail);
	th = sched_pop_next(l);
	ACCESS_ONCE(l->q_ptrs->rq_tail)++;

	/* move overflow tasks into the runqueue */
	if (unlikely(!list_empty(&l->rq_overflow)))
		drain_overflow(l);

	update_oldest_tsc(l);

	store_release(&th->cur_kthread, kthread_idx(l));

	spin_unlock(&l->lock);

	/* update exit stat counters */
	perthread_get_stable(last_tsc) = rdtsc();
	STAT(SCHED_CYCLES) += perthread_get_stable(last_tsc) - start_tsc;
	if (cores_have_affinity(th->last_cpu, l->curr_cpu))
		STAT(LOCAL_RUNS)++;
	else
		STAT(REMOTE_RUNS)++;

	/* update exported thread run start time */
	ACCESS_ONCE(l->q_ptrs->run_start_tsc) = perthread_get_stable(last_tsc);

	/* increment the RCU generation number (odd is in thread) */
	store_release(&l->rcu_gen, l->rcu_gen + 1);
	ACCESS_ONCE(l->q_ptrs->rcu_gen) = l->rcu_gen;
	assert((l->rcu_gen & 0x1) == 0x1);

	/* and jump into the next thread */
	jmp_thread(th);
}

static __always_inline void enter_schedule(thread_t *curth)
{
	struct kthread *k = myk();
	thread_t *th;
	uint64_t now_tsc, prog_cycles;

	assert_preempt_disabled();

	/* prepare current thread for sleeping */
	curth->last_cpu = k->curr_cpu;

	spin_lock(&k->lock);
	now_tsc = rdtsc();

	/* slow path: switch from the uthread stack to the runtime stack */
	if (k->rq_head == k->rq_tail ||
	    preempt_cede_needed(k) ||
	    (!disable_watchdog &&
	     unlikely(now_tsc - k->last_softirq_tsc >
		      cycles_per_us * RUNTIME_WATCHDOG_US))) {
		jmp_runtime(schedule);
		return;
	}

	/* fast path: switch directly to the next uthread */
	prog_cycles = now_tsc - perthread_get_stable(last_tsc);
	STAT(PROGRAM_CYCLES) += prog_cycles;
	curth->total_cycles += prog_cycles;
	perthread_get_stable(last_tsc) = now_tsc;

	/* pop the next runnable thread from the queue */
	th = sched_pop_next(k);
	ACCESS_ONCE(k->q_ptrs->rq_tail)++;

	/* move overflow tasks into the runqueue */
	if (unlikely(!list_empty(&k->rq_overflow)))
		drain_overflow(k);

	update_oldest_tsc(k);
	store_release(&curth->cur_kthread, NCPU);
	th->cur_kthread = kthread_idx(k);
	spin_unlock(&k->lock);

	/* update exported thread run start time */
	ACCESS_ONCE(k->q_ptrs->run_start_tsc) = perthread_get_stable(last_tsc);

	/* increment the RCU generation number (odd is in thread) */
	store_release(&k->rcu_gen, k->rcu_gen + 2);
	ACCESS_ONCE(k->q_ptrs->rcu_gen) = k->rcu_gen;
	assert((k->rcu_gen & 0x1) == 0x1);

	/* check for misuse of preemption disabling */
	BUG_ON((perthread_read(preempt_cnt) & ~PREEMPT_NOT_PENDING) != 1);

	/* check if we're switching into the same thread as before */
	if (unlikely(th == curth)) {
		th->thread_ready = false;
		preempt_enable();
		return;
	}

	/* switch stacks and enter the next thread */
	STAT(RESCHEDULES)++;
	if (cores_have_affinity(th->last_cpu, k->curr_cpu))
		STAT(LOCAL_RUNS)++;
	else
		STAT(REMOTE_RUNS)++;
	jmp_thread_direct(curth, th);
}

/**
 * thread_park_and_unlock_np - puts a thread to sleep, unlocks the lock @l,
 *                             and schedules the next thread
 * @l: the lock to be released
 */
void thread_park_and_unlock_np(spinlock_t *l)
{
	thread_t *curth = thread_self();

	assert_preempt_disabled();
	assert_spin_lock_held(l);
	spin_unlock(l);
	enter_schedule(curth);
}

/**
 * thread_park_and_preempt_enable - puts a thread to sleep, enables preemption,
 *                                  and schedules the next thread
 */
void thread_park_and_preempt_enable(void)
{
	thread_t *curth = thread_self();

	assert_preempt_disabled();
	enter_schedule(curth);
}

static void thread_ready_prepare(struct kthread *k, thread_t *th)
{
	/* check for misuse where a ready thread is marked ready again */
	BUG_ON(th->thread_ready);

	/* prepare thread to be runnable */
	th->thread_ready = true;
	th->ready_tsc = rdtsc();
	if (cores_have_affinity(th->last_cpu, k->curr_cpu))
		STAT(LOCAL_WAKES)++;
	else
		STAT(REMOTE_WAKES)++;
}

/**
 * thread_ready_locked - makes a uthread runnable (at tail, kthread lock held)
 * @th: the thread to mark runnable
 *
 * This function can only be called when @th is parked.
 * This function must be called with preemption disabled and the kthread lock
 * held.
 */
void thread_ready_locked(thread_t *th)
{
	struct kthread *k = myk();

	assert_preempt_disabled();
	assert_spin_lock_held(&k->lock);

	/* ensure new thread lands after older threads */
	if (unlikely(!list_empty(&k->rq_overflow)))
		drain_overflow(k);

	thread_ready_prepare(k, th);
	if (unlikely(k->rq_head - k->rq_tail >= RUNTIME_RQ_SIZE)) {
		assert(k->rq_head - k->rq_tail == RUNTIME_RQ_SIZE);
		list_add_tail(&k->rq_overflow, &th->link);
		ACCESS_ONCE(k->q_ptrs->rq_head)++;
		STAT(RQ_OVERFLOW)++;
		if (thread_is_hinted(th))
			STAT(HINTED_OVERFLOW)++;
		return;
	}

	k->rq[k->rq_head++ % RUNTIME_RQ_SIZE] = th;
	if (k->rq_head - k->rq_tail == 1)
		ACCESS_ONCE(k->q_ptrs->oldest_tsc) = th->ready_tsc;
	ACCESS_ONCE(k->q_ptrs->rq_head)++;
}

/**
 * thread_ready_head_locked - makes a uthread runnable (at head, kthread lock held)
 * @th: the thread to mark runnable
 *
 * This function can only be called when @th is parked.
 * This function must be called with preemption disabled and the kthread lock
 * held.
 */
void thread_ready_head_locked(thread_t *th)
{
	struct kthread *k = myk();
	thread_t *oldestth;

	assert_preempt_disabled();
	assert_spin_lock_held(&k->lock);

	thread_ready_prepare(k, th);

	if (k->rq_head != k->rq_tail)
		th->ready_tsc = k->rq[k->rq_tail % RUNTIME_RQ_SIZE]->ready_tsc;
	oldestth = k->rq[--k->rq_tail % RUNTIME_RQ_SIZE];
	k->rq[k->rq_tail % RUNTIME_RQ_SIZE] = th;
	if (unlikely(k->rq_head - k->rq_tail > RUNTIME_RQ_SIZE)) {
		list_add(&k->rq_overflow, &oldestth->link);
		k->rq_head--;
		STAT(RQ_OVERFLOW)++;
		if (thread_is_hinted(oldestth))
			STAT(HINTED_OVERFLOW)++;
	}
	ACCESS_ONCE(k->q_ptrs->oldest_tsc) = th->ready_tsc;
	ACCESS_ONCE(k->q_ptrs->rq_head)++;
}

/**
 * thread_ready - makes a uthread runnable (at the tail of the queue)
 * @th: the thread to mark runnable
 *
 * This function can only be called when @th is parked.
 */
void thread_ready(thread_t *th)
{
	struct kthread *k;
	uint32_t rq_tail;

	k = getk();
	thread_ready_prepare(k, th);
	rq_tail = load_acquire(&k->rq_tail);
	if (unlikely(k->rq_head - rq_tail >= RUNTIME_RQ_SIZE ||
	             !list_empty_volatile(&k->rq_overflow))) {
		assert(k->rq_head - rq_tail <= RUNTIME_RQ_SIZE);
		spin_lock(&k->lock);
		list_add_tail(&k->rq_overflow, &th->link);
		drain_overflow(k);
		spin_unlock(&k->lock);
		ACCESS_ONCE(k->q_ptrs->rq_head)++;
		STAT(RQ_OVERFLOW)++;
		if (thread_is_hinted(th))
			STAT(HINTED_OVERFLOW)++;
		putk();
		return;
	}

	k->rq[k->rq_head % RUNTIME_RQ_SIZE] = th;
	store_release(&k->rq_head, k->rq_head + 1);
	if (k->rq_head - load_acquire(&k->rq_tail) == 1)
		ACCESS_ONCE(k->q_ptrs->oldest_tsc) = th->ready_tsc;
	ACCESS_ONCE(k->q_ptrs->rq_head)++;
	putk();
}

/**
 * thread_ready_head - makes a uthread runnable (at the head of the queue)
 * @th: the thread to mark runnable
 *
 * This function can only be called when @th is parked.
 */
void thread_ready_head(thread_t *th)
{
	struct kthread *k;
	thread_t *oldestth;

	k = getk();
	thread_ready_prepare(k, th);
	spin_lock(&k->lock);
	if (k->rq_head != k->rq_tail)
		th->ready_tsc = k->rq[k->rq_tail % RUNTIME_RQ_SIZE]->ready_tsc;
	oldestth = k->rq[--k->rq_tail % RUNTIME_RQ_SIZE];
	k->rq[k->rq_tail % RUNTIME_RQ_SIZE] = th;
	if (unlikely(k->rq_head - k->rq_tail > RUNTIME_RQ_SIZE)) {
		list_add(&k->rq_overflow, &oldestth->link);
		k->rq_head--;
		STAT(RQ_OVERFLOW)++;
		if (thread_is_hinted(oldestth))
			STAT(HINTED_OVERFLOW)++;
	}
	spin_unlock(&k->lock);
	ACCESS_ONCE(k->q_ptrs->oldest_tsc) = th->ready_tsc;
	ACCESS_ONCE(k->q_ptrs->rq_head)++;
	putk();
}

// Hacky way to calculate total cycle time.
uint64_t thread_get_total_cycles(thread_t *th) {

	unsigned int k = load_acquire(&th->cur_kthread);
	uint64_t k_run_start, cycles = ACCESS_ONCE(th->total_cycles);
	// th is not running on any kthread or we just missed it starting to run.
	// Either way the last total_cycles should be accurate.
	if (k == NCPU)
		return cycles;

	bool correct_k = false;
	spin_lock_np(&ks[k].lock);
	correct_k = th->cur_kthread == k;
	cycles = ACCESS_ONCE(th->total_cycles);
	k_run_start = ks[k].q_ptrs->run_start_tsc;
	spin_unlock_np(&ks[k].lock);

	if (correct_k)
		return cycles + rdtsc() - k_run_start;
	return cycles;
}

void thread_finish_yield(void)
{
	thread_t *curth = thread_self();
	struct kthread *k = myk();

	assert_preempt_disabled();

	spin_lock(&k->lock);

	/* check for softirqs */
	softirq_run_locked(k);

	curth->thread_ready = false;
	curth->last_cpu = k->curr_cpu;
	thread_ready_locked(curth);

	schedule();
}

void thread_finish_cede(void)
{
	struct kthread *k = myk();
	thread_t *myth = thread_self();
	uint64_t prog_cycles, tsc = rdtsc();

	/* update stats and scheduler state */
	myth->thread_running = false;
	myth->last_cpu = k->curr_cpu;
	perthread_store(__self, NULL);
	prog_cycles = tsc - perthread_get_stable(last_tsc);
	STAT(PROGRAM_CYCLES) += prog_cycles;
	myth->total_cycles += prog_cycles;

	/* mark ceded thread ready at head of runqueue */
	thread_ready_head(myth);

	/* increment the RCU generation number (even - pretend in sched) */
	store_release(&k->rcu_gen, k->rcu_gen + 1);
	ACCESS_ONCE(k->q_ptrs->rcu_gen) = k->rcu_gen;
	assert((k->rcu_gen & 0x1) == 0x0);

	/* cede this kthread to the iokernel */
	ACCESS_ONCE(k->parked) = true; /* deliberately racy */
	kthread_park_now();
	perthread_get_stable(last_tsc) = rdtsc();

	/* increment the RCU generation number (odd - back in thread) */
	store_release(&k->rcu_gen, k->rcu_gen + 1);
	ACCESS_ONCE(k->q_ptrs->rcu_gen) = k->rcu_gen;
	assert((k->rcu_gen & 0x1) == 0x1);

	/* re-enter the scheduler */
	spin_lock(&k->lock);
	k->parked = false;
	schedule();
}

/**
 * thread_cede - yields the running thread and gives the core back to iokernel
 */
void thread_cede(void)
{
	/* this will switch from the thread stack to the runtime stack */
	assert_preempt_disabled();
	jmp_runtime(thread_finish_cede);
}

/**
 * thread_yield - yields the currently running thread
 *
 * Yielding will give other threads and softirqs a chance to run.
 */
void thread_yield(void)
{
	thread_t *curth = thread_self();

	/* check for softirqs */
	softirq_run();

	preempt_disable();
	curth->thread_ready = false;
	thread_ready(curth);
	enter_schedule(curth);
}

static __always_inline thread_t *__thread_create(void)
{
	struct thread *th;
	struct stack *s;

	preempt_disable();
	th = tcache_alloc(perthread_ptr(thread_pt));
	if (unlikely(!th)) {
		preempt_enable();
		return NULL;
	}

	s = stack_alloc();
	if (unlikely(!s)) {
		tcache_free(perthread_ptr(thread_pt), th);
		preempt_enable();
		return NULL;
	}
	th->last_cpu = myk()->curr_cpu;

	/*
	 * Priority class is inherited from the creating thread, but only if it
	 * is a class an application could have set (never SOFTIRQ). Deadlines
	 * and service times are not inherited.
	 */
	th->prio_class = THREAD_PRIO_NORMAL;
	if (thread_self() && thread_self()->prio_class < THREAD_PRIO_NR_USER)
		th->prio_class = thread_self()->prio_class;
	preempt_enable();

	th->stack = s;
	th->main_thread = false;
	th->has_fsbase = false;
	th->thread_ready = false;
	th->thread_running = false;
	th->waitq_micros = 0;
	th->tlsvar = 0;
	th->cur_kthread = NCPU;
	// Can be used to detect newly created thread.
	th->ready_tsc = 0;
	th->total_cycles = 0;
	th->deadline_tsc = 0;
	th->service_tsc = 0;
	th->hinted = (th->prio_class != THREAD_PRIO_NORMAL &&
		      th->prio_class < THREAD_PRIO_NR_USER);
	atomic8_write(&th->interrupt_state, 0);

	return th;
}

/**
 * thread_set_hints - attaches scheduling hints to a thread
 * @th: the thread to modify
 * @h: the hints; a zeroed struct clears all hints
 *
 * Must only be called on the running thread (thread_self()) or on a thread
 * that has been created but not yet readied. Hints take effect the next time
 * the thread is made runnable.
 *
 * Returns 0 if successful, otherwise -EINVAL if the class is invalid.
 */
int thread_set_hints(thread_t *th, const struct thread_hints *h)
{
	if (h->prio_class >= THREAD_PRIO_NR_USER)
		return -EINVAL;

	/* the thread must not be sitting in a runqueue right now */
	assert(!th->thread_ready);
	assert(th == thread_self() || th->ready_tsc == 0);

	th->prio_class = h->prio_class;
	th->deadline_tsc = h->deadline_us ?
		start_tsc + h->deadline_us * cycles_per_us : 0;
	th->service_tsc = h->service_us * cycles_per_us;
	th->hinted = (th->prio_class != THREAD_PRIO_NORMAL ||
		      th->deadline_tsc != 0);
	return 0;
}

/**
 * thread_get_hints - reads back a thread's scheduling hints
 * @th: the thread to inspect
 * @out: filled with the hints (deadline converted back to microtime() units)
 */
void thread_get_hints(const thread_t *th, struct thread_hints *out)
{
	out->prio_class = th->prio_class < THREAD_PRIO_NR_USER ?
			  th->prio_class : THREAD_PRIO_NORMAL;
	out->deadline_us = th->deadline_tsc ?
		(th->deadline_tsc - start_tsc) / cycles_per_us : 0;
	out->service_us = th->service_tsc / cycles_per_us;
}

/**
 * thread_mark_softirq - marks a runtime helper thread (internal use only)
 * @th: the thread to mark
 *
 * Softirq threads always run ahead of application threads. They are kept in
 * the plain ring (head slot), so they are never counted as "hinted".
 */
void thread_mark_softirq(thread_t *th)
{
	th->prio_class = THREAD_PRIO_SOFTIRQ;
	th->deadline_tsc = 0;
	th->service_tsc = 0;
	th->hinted = false;
}

/**
 * thread_create - creates a new thread
 * @fn: a function pointer to the starting method of the thread
 * @arg: an argument passed to @fn
 *
 * Returns 0 if successful, otherwise -ENOMEM if out of memory.
 */
thread_t *thread_create(thread_fn_t fn, void *arg)
{
	thread_t *th = __thread_create();
	if (unlikely(!th))
		return NULL;

	th->tf.rsp = stack_init_to_rsp(th->stack, thread_exit);
	th->tf.rdi = (uint64_t)arg;
	th->tf.rbp = (uint64_t)0; /* just in case base pointers are enabled */
	th->tf.rip = (uint64_t)fn;
	return th;
}

/**
 * thread_create_with_buf - creates a new thread with space for a buffer on the
 * stack
 * @fn: a function pointer to the starting method of the thread
 * @buf: a pointer to the stack allocated buffer (passed as arg too)
 * @buf_len: the size of the stack allocated buffer
 *
 * Returns 0 if successful, otherwise -ENOMEM if out of memory.
 */
thread_t *thread_create_with_buf(thread_fn_t fn, void **buf, size_t buf_len)
{
	void *ptr;
	thread_t *th = __thread_create();
	if (unlikely(!th))
		return NULL;

	th->tf.rsp = stack_init_to_rsp_with_buf(th->stack, &ptr, buf_len,
						thread_exit);
	th->tf.rdi = (uint64_t)ptr;
	th->tf.rbp = (uint64_t)0; /* just in case base pointers are enabled */
	th->tf.rip = (uint64_t)fn;
	*buf = ptr;
	return th;
}

/**
 * thread_spawn - creates and launches a new thread
 * @fn: a function pointer to the starting method of the thread
 * @arg: an argument passed to @fn
 *
 * Returns 0 if successful, otherwise -ENOMEM if out of memory.
 */
int thread_spawn(thread_fn_t fn, void *arg)
{
	thread_t *th = thread_create(fn, arg);
	if (unlikely(!th))
		return -ENOMEM;
	thread_ready(th);
	return 0;
}

/**
 * thread_spawn_with_hints - creates and launches a new thread with hints
 * @fn: a function pointer to the starting method of the thread
 * @arg: an argument passed to @fn
 * @h: scheduling hints to attach before the thread first runs
 *
 * Returns 0 if successful, otherwise -ENOMEM if out of memory or -EINVAL if
 * the hints are invalid.
 */
int thread_spawn_with_hints(thread_fn_t fn, void *arg,
			    const struct thread_hints *h)
{
	thread_t *th = thread_create(fn, arg);
	int ret;

	if (unlikely(!th))
		return -ENOMEM;
	ret = thread_set_hints(th, h);
	if (unlikely(ret)) {
		thread_free(th);
		return ret;
	}
	thread_ready(th);
	return 0;
}

/**
 * thread_spawn_main - creates and launches the main thread
 * @fn: a function pointer to the starting method of the thread
 * @arg: an argument passed to @fn
 *
 * WARNING: Only can be called once.
 *
 * Returns 0 if successful, otherwise -ENOMEM if out of memory.
 */
int thread_spawn_main(thread_fn_t fn, void *arg)
{
	static bool called = false;
	thread_t *th;

	BUG_ON(called);
	called = true;

	th = thread_create(fn, arg);
	if (!th)
		return -ENOMEM;
	th->main_thread = true;
	thread_ready(th);
	return 0;
}

void thread_free(thread_t *th)
{
	stack_free(th->stack);
	tcache_free(perthread_ptr(thread_pt), th);
}

static void thread_finish_exit(void)
{
	struct thread *th = thread_self();

	perthread_store(__self, NULL);

	/* if the main thread dies, kill the whole program */
	if (unlikely(th->main_thread))
		init_shutdown(EXIT_SUCCESS);

	thread_free(th);

	spin_lock(&myk()->lock);
	schedule();
}

/**
 * thread_exit - terminates a thread
 */
void thread_exit(void)
{
	/* can't free the stack we're currently using, so switch */
	preempt_disable();
	jmp_runtime_nosave(thread_finish_exit);
}

/**
 * immediately park each kthread when it first starts up, only schedule it once
 * the iokernel has granted it a core
 */
static void schedule_start(void)
{
	struct kthread *k = myk();

	/*
	 * force kthread parking (iokernel assumes all kthreads are parked
	 * initially). Update RCU generation so it stays even after entering
	 * schedule().
	 */
	if (k->q_ptrs->oldest_tsc == 0)
		ACCESS_ONCE(k->q_ptrs->oldest_tsc) = UINT64_MAX;
	ACCESS_ONCE(k->parked) = true;
	kthread_wait_to_attach();
	perthread_store(last_tsc, rdtsc());
	store_release(&k->rcu_gen, 1);
	ACCESS_ONCE(k->q_ptrs->rcu_gen) = 1;

	spin_lock(&k->lock);
	k->parked = false;
	schedule();
}

/**
 * sched_start - used only to enter the runtime the first time
 */
void sched_start(void)
{
	preempt_disable();
	jmp_runtime_nosave(schedule_start);
}

static void runtime_top_of_stack(void)
{
	panic("a thread returned to the top of the stack");
}

/**
 * sched_init_thread - initializes per-thread state for the scheduler
 *
 * Returns 0 if successful, or -ENOMEM if out of memory.
 */
int sched_init_thread(void)
{
	struct stack *s;

	tcache_init_perthread(thread_tcache, perthread_ptr(thread_pt));

	s = stack_alloc();
	if (!s)
		return -ENOMEM;

	perthread_store(runtime_stack, (void *)runtime_stack_init_to_rsp(s, runtime_top_of_stack));
	perthread_store(runtime_fsbase, _readfsbase_u64());

	return 0;
}

/**
 * sched_init - initializes the scheduler subsystem
 *
 * Returns 0 if successful, or -ENOMEM if out of memory.
 */
int sched_init(void)
{
	int ret, i, j, siblings;

	/*
	 * set up allocation routines for threads
	 */
	ret = slab_create(&thread_slab, "runtime_threads",
			  sizeof(struct thread), 0);
	if (ret)
		return ret;

	thread_tcache = slab_create_tcache(&thread_slab,
					   TCACHE_DEFAULT_MAG_SIZE);
	if (!thread_tcache) {
		slab_destroy(&thread_slab);
		return -ENOMEM;
	}

	for (i = 0; i < cpu_count; i++) {
		siblings = 0;
		bitmap_for_each_set(cpu_info_tbl[i].thread_siblings_mask,
				    cpu_count, j) {
			if (i == j)
				continue;
			BUG_ON(siblings++);
			cpu_map[i].sibling_core = j;
		}
	}

	return 0;
}
