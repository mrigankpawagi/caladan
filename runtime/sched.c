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

/*
 * p2 "rescue": prio's strict class order, plus one rationed pass inside the
 * chosen class. The oldest thread keeps its turn unless a younger thread of
 * the same class
 *   (a) carries a deadline and is due earlier than every thread of the class
 *       ahead of it (so a request never passes one of its own kind),
 *   (b) would miss that deadline if it waited for them: the hinted run times
 *       of the threads ahead, its own run time, and the latency the hints do
 *       not see add up to more than the time it has left, and
 *   (c) the oldest thread has waited less than the run time it would be asked
 *       to absorb: the queue formed within the last request's run and the
 *       pass at most doubles that wait, leaving the passed request in the
 *       body of its latency, not its tail.
 * A passed thread is older than one run time afterwards, so it is passed at
 * most once. Without deadlines, or with one deadline window per class, the
 * pass can never trigger and the pick is prio's.
 */

/*
 * Latency the hint clock does not see, in microseconds: the packet's wait
 * before its handler thread exists plus the reply. The gen 1 report measured
 * 12 us at light load and 45 us at the tail of a loaded server (176 - 37 - 94
 * on w2 at 202k req/s); 30 sits between, so a sub-request that the hints say
 * will finish with less than 30 us to spare counts as about to miss.
 */
#define POLICY_UNSEEN_US 30

static uint32_t choose_rescue(struct kthread *k, uint32_t n)
{
	uint32_t i, best = 0;
	uint8_t rank = prio_rank[sched_rq_at(k, 0)->prio_class];
	bool any_due = sched_rq_at(k, 0)->deadline_tsc != 0;
	uint64_t now, head_age, ahead, unseen, due_ahead;
	thread_t *th;

	/* prio's choice: the oldest thread of the highest class present */
	for (i = 1; i < n && rank < prio_rank[THREAD_PRIO_SOFTIRQ]; i++) {
		th = sched_rq_at(k, i);
		if (prio_rank[th->prio_class] > rank) {
			rank = prio_rank[th->prio_class];
			best = i;
		}
		any_due |= th->deadline_tsc != 0;
	}

	/* nothing to rescue: no deadlines, a helper thread, or nobody behind */
	if (!any_due || rank == prio_rank[THREAD_PRIO_SOFTIRQ] || best + 1 >= n)
		return best;

	now = rdtsc();
	th = sched_rq_at(k, best);
	head_age = now > th->ready_tsc ? now - th->ready_tsc : 0;
	unseen = (uint64_t)POLICY_UNSEEN_US * cycles_per_us;
	ahead = 0;			/* hinted run time of the class ahead */
	due_ahead = ~(uint64_t)0;	/* earliest deadline of the class ahead */

	for (i = best; i < n; i++) {
		th = sched_rq_at(k, i);
		if (prio_rank[th->prio_class] != rank)
			continue;	/* a lower class: prio runs it later anyway */
		if (i != best && th->deadline_tsc &&
		    th->deadline_tsc < due_ahead &&		/* (a) */
		    head_age < th->service_tsc &&			/* (c) */
		    now + ahead + th->service_tsc + unseen > th->deadline_tsc) /* (b) */
			return i;
		ahead += th->service_tsc;
		if (th->deadline_tsc && th->deadline_tsc < due_ahead)
			due_ahead = th->deadline_tsc;
	}
	return best;
}

/*
 * p3 "passonce": prio's strict class order, plus one pass inside the chosen
 * class, paid at most once by each passed thread.
 *
 * Principle: a thread that carries a deadline and whose hinted run time is
 * shorter than that of every thread of its class ahead of it may run before
 * them, and a thread is passed at most once. The price of a pass to each
 * passed thread is the passer's own run time, so a thread never passes one
 * of its own kind (no cascades) and never passes a shorter one.
 *
 * Bookkeeping without a clock: the ring is kept in ready-time order (the
 * steal path merges by ready_tsc and thread_ready_head copies the head's
 * stamp), so the core remembers in policy_state[0] the ready time of the
 * youngest thread it let something pass. Every thread with a ready time at
 * or before that mark forms a prefix of the ring and has been passed
 * already; a pass is therefore allowed only while the oldest thread of the
 * chosen class is younger than the mark, and when it happens the mark moves
 * to the youngest thread passed. The mark is per core: a thread stolen to
 * another core may in rare cases be passed once more there, or, if it is
 * older than the thief's mark, be treated as already passed.
 *
 * The pick is prio's whenever no thread of the chosen class carries a
 * deadline together with a hinted run time strictly shorter than every
 * class-mate ahead of it: without deadlines (w0), with one hinted run time
 * per class (w1), or when the shorter kind has no deadline (w2's health
 * checks). The mark is then never written. There are no constants.
 */
static uint32_t choose_passonce(struct kthread *k, uint32_t n)
{
	uint32_t i, best = 0, cand = 0, passed = 0, last = 0;
	thread_t *th = sched_rq_at(k, 0);
	uint8_t rank = prio_rank[th->prio_class];
	/* the shortest hinted run time seen in the chosen class; unknown = longest */
	uint64_t shortest = th->service_tsc ? th->service_tsc : ~(uint64_t)0;

	for (i = 1; i < n && rank < prio_rank[THREAD_PRIO_SOFTIRQ]; i++) {
		uint8_t r;
		uint64_t s;

		th = sched_rq_at(k, i);
		r = prio_rank[th->prio_class];
		if (r < rank)
			continue;	/* a lower class: prio runs it later anyway */
		if (r > rank) {
			/* a higher class: prio's choice moves here, nothing passes it yet */
			rank = r;
			best = i;
			cand = 0;
			last = i;
			shortest = th->service_tsc ? th->service_tsc : ~(uint64_t)0;
			continue;
		}
		s = th->service_tsc ? th->service_tsc : ~(uint64_t)0;
		if (th->deadline_tsc && s < shortest) {
			/* shorter than every class-mate ahead: the pass candidate */
			cand = i;
			passed = last;	/* the youngest thread it would pass */
		}
		if (s < shortest)
			shortest = s;
		last = i;
	}

	/* no candidate, or the oldest of the class has been passed already */
	if (!cand || sched_rq_at(k, best)->ready_tsc <= k->policy_state[0])
		return best;

	k->policy_state[0] = sched_rq_at(k, passed)->ready_tsc;
	return cand;
}

/*
 * p4 "afford": passonce's pass, allowed only when every thread it would pass
 * can afford it by its own hints.
 *
 * Principle: a thread that carries a deadline and whose hinted run time is
 * shorter than that of every thread of its class ahead of it may run before
 * them, provided none of them has been passed before and every one of them
 * that carries a deadline would still, by the hints, finish with the unseen
 * time to spare: its deadline, minus the hinted run time of its class ahead
 * of it and its own, minus the passer's run time, minus the latency the hint
 * clock does not see, must not have run out at the moment of the pick.
 * Where no pass is affordable the pick is prio's; where every pass is
 * affordable the pick is passonce's.
 *
 * The price of a pass is the passer's run time, paid at most once by each
 * passed thread (passonce's mark in policy_state[0] is kept as it is). What
 * changes is who may be asked to pay. passonce charged any thread the once
 * bound allowed, which on w4 charged reads already past their budget 10 us
 * each to save appends that had 170 us to spare. Here the charge is priced
 * against the passed thread's remaining slack: on w4 a read with another
 * read ahead of it is passed only within 16 us of arriving, a read at the
 * head of its class within 53 us, and a tail read (75 us waited) never; on
 * w3 a search behind one search keeps 90 us minus its wait and is passed
 * as before, so the suggestions' gain holds except in queues four searches
 * deep.
 *
 * The one constant is p2's POLICY_UNSEEN_US, 30 us, reused: the latency the
 * hint clock does not see, because the clock starts when the handler thread
 * gets its hints, after the packet has waited for the request the core was
 * running, and stops before the reply. The gen 3 report measures the part
 * outside the queue at ~31 us at the tail on w4 (156 = 37 own + 12 light-
 * load + 75.5 queue + ~31), ~31 on w3 and ~33 on w2, with the 12 us light-
 * load floor (network, softirq, reply) on top of it. 30 is the report's
 * figure and sits between the floor (12) and the loaded tail (42-45); a
 * thread within that difference of the line can be mispriced by at most
 * that much, in either direction.
 *
 * Cost: passonce's single scan plus, per thread of the chosen class, one
 * add (the class's hinted work so far) and one subtract-and-min (the
 * thread's room: its deadline minus the work through it), and one clock
 * read only when a candidate exists and the once bound allows the pass. On
 * w0, w1 and w2 no candidate ever forms (no deadlines; one hinted run time
 * per class; the shorter kind without a deadline), so no clock is read,
 * the mark is never written and the pick is prio's, exactly as passonce.
 */

/*
 * The latest instant at which @th's class may start running and still, by
 * the hints, deliver @th before its deadline: its deadline minus @work, the
 * hinted run time of its class-mates ahead of it plus its own. A thread
 * without a deadline has no slack to keep and never refuses a pass.
 */
static inline uint64_t afford_room(const thread_t *th, uint64_t work)
{
	if (!th->deadline_tsc)
		return ~(uint64_t)0;
	return th->deadline_tsc > work ? th->deadline_tsc - work : 0;
}

static uint32_t choose_afford(struct kthread *k, uint32_t n)
{
	uint32_t i, best = 0, cand = 0, passed = 0, last = 0;
	thread_t *th = sched_rq_at(k, 0);
	uint8_t rank = prio_rank[th->prio_class];
	/* the shortest hinted run time seen in the chosen class; unknown = longest */
	uint64_t shortest = th->service_tsc ? th->service_tsc : ~(uint64_t)0;
	/* hinted work of the chosen class scanned so far, and the tightest room in it */
	uint64_t work = th->service_tsc;
	uint64_t room = afford_room(th, work);
	/* the tightest room among the threads the candidate would pass */
	uint64_t margin = 0, now;

	for (i = 1; i < n && rank < prio_rank[THREAD_PRIO_SOFTIRQ]; i++) {
		uint8_t r;
		uint64_t s;

		th = sched_rq_at(k, i);
		r = prio_rank[th->prio_class];
		if (r < rank)
			continue;	/* a lower class: prio runs it later anyway */
		if (r > rank) {
			/* a higher class: prio's choice moves here, nothing passes it yet */
			rank = r;
			best = i;
			cand = 0;
			last = i;
			shortest = th->service_tsc ? th->service_tsc : ~(uint64_t)0;
			work = th->service_tsc;
			room = afford_room(th, work);
			continue;
		}
		s = th->service_tsc ? th->service_tsc : ~(uint64_t)0;
		if (th->deadline_tsc && s < shortest) {
			/* shorter than every class-mate ahead: the pass candidate */
			cand = i;
			passed = last;	/* the youngest thread it would pass */
			margin = room;	/* the tightest room among them */
		}
		if (s < shortest)
			shortest = s;
		work += th->service_tsc;
		room = MIN(room, afford_room(th, work));
		last = i;
	}

	/* no candidate, or the oldest of the class has been passed already */
	if (!cand || sched_rq_at(k, best)->ready_tsc <= k->policy_state[0])
		return best;

	/* the pass must leave every passed thread its hinted slack */
	now = rdtsc();
	th = sched_rq_at(k, cand);
	if (margin < now + th->service_tsc +
		     (uint64_t)POLICY_UNSEEN_US * cycles_per_us)
		return best;

	k->policy_state[0] = sched_rq_at(k, passed)->ready_tsc;
	return cand;
}

/*
 * p5 "absorb": passonce's pass, with the once bound relaxed for passers
 * that are cheap relative to the threads they pass.
 *
 * Principle: a thread that carries a deadline and whose hinted run time is
 * shorter than that of every thread of its class ahead of it may run before
 * them, and each passed thread pays the passer's run time (passonce). A
 * thread absorbs one such pass unconditionally; it absorbs further passes
 * only while everything it has absorbed during its stay at the head of its
 * class, the new pass included, stays within a share of its own hinted run
 * time. A thread without a hinted run time has no share and is passed once.
 * The pick is prio's wherever no candidate forms (no deadlines, one hinted
 * run time per class, the shorter kind without a deadline), and passonce's
 * wherever the share admits nothing beyond the first pass.
 *
 * Bookkeeping, without a clock: passonce's mark in policy_state[0] (the
 * ready time of the youngest thread passed; the ring is kept in ready-time
 * order) says whether the oldest thread of the chosen class has been passed
 * before. policy_state[1] adds what the passed prefix has absorbed since a
 * pass last opened on a never-passed head, an episode. Every thread of the
 * prefix is charged the whole of it, which overstates what the younger ones
 * paid and therefore refuses passes, never admits them, beyond the rule.
 * The share is measured against the shortest hinted run time among the
 * threads the candidate would pass, the tightest of them. Both words are
 * per core, with passonce's caveat for stolen threads.
 *
 * Cost: passonce's single scan plus one min per thread of the chosen class
 * (same cache line as prio_class). The share is consulted only where
 * passonce refuses (a candidate behind a passed head); one extra store on a
 * pass. No clock read, no second scan.
 */

/*
 * Share of a passed thread's hinted run time, in percent, that the passes it
 * absorbs in one episode may add up to before further passes are refused.
 * The cap is a share of the passed thread's own cost so that it scales with
 * that thread and not with the passers' share of the traffic, which is what
 * an unconditional shorter-first order would charge. 25 is the middle of
 * the band in which the cap changes nothing on the workloads where the once
 * bound was measured as right and admits a second pass where its refusal
 * was measured as the whole residue: two suggestions cost a search 12 of 37
 * (32%, w3) and two appends cost a read 20 of 37 (54%, w4), both refused;
 * two lookups cost a range read 4 of 21 (19%, w5), admitted. 25 sits a
 * factor 1.3 from either edge of 19-32. A passer at an eighth of the
 * thread it passes or less therefore gets a second pass, one at a sixth or
 * more does not.
 */
#define POLICY_ABSORB_PCT 25

static uint32_t choose_absorb(struct kthread *k, uint32_t n)
{
	uint32_t i, best = 0, cand = 0, passed = 0, last = 0;
	thread_t *th = sched_rq_at(k, 0);
	uint8_t rank = prio_rank[th->prio_class];
	/* the shortest hinted run time seen in the chosen class; unknown = longest */
	uint64_t shortest = th->service_tsc ? th->service_tsc : ~(uint64_t)0;
	/* the same, with unknown = 0: a thread without a hint has no share */
	uint64_t least = th->service_tsc;
	/* the candidate's run time and the least run time it would pass */
	uint64_t price = 0, cap = 0, paid;

	for (i = 1; i < n && rank < prio_rank[THREAD_PRIO_SOFTIRQ]; i++) {
		uint8_t r;
		uint64_t s;

		th = sched_rq_at(k, i);
		r = prio_rank[th->prio_class];
		if (r < rank)
			continue;	/* a lower class: prio runs it later anyway */
		if (r > rank) {
			/* a higher class: prio's choice moves here, nothing passes it yet */
			rank = r;
			best = i;
			cand = 0;
			last = i;
			shortest = th->service_tsc ? th->service_tsc : ~(uint64_t)0;
			least = th->service_tsc;
			continue;
		}
		s = th->service_tsc ? th->service_tsc : ~(uint64_t)0;
		if (th->deadline_tsc && s < shortest) {
			/* shorter than every class-mate ahead: the pass candidate */
			cand = i;
			passed = last;	/* the youngest thread it would pass */
			price = th->service_tsc;
			cap = least;	/* the tightest share among them */
		}
		if (s < shortest)
			shortest = s;
		least = MIN(least, th->service_tsc);
		last = i;
	}

	if (!cand)
		return best;

	if (sched_rq_at(k, best)->ready_tsc > k->policy_state[0]) {
		/* a never-passed head: passonce's one pass opens an episode */
		paid = price;
	} else {
		/* a passed head: only while the prefix stays within its share */
		paid = k->policy_state[1] + price;
		if (paid * 100 > cap * POLICY_ABSORB_PCT)
			return best;
	}
	k->policy_state[1] = paid;
	k->policy_state[0] = MAX(k->policy_state[0],
				 sched_rq_at(k, passed)->ready_tsc);
	return cand;
}

static const struct {
	const char		*name;
	sched_choose_fn_t	choose;
} sched_policies[] = {
	{ "fifo",	choose_fifo },
	{ "prio",	choose_prio },
	{ "rescue",	choose_rescue },
	{ "passonce",	choose_passonce },
	{ "afford",	choose_afford },
	{ "absorb",	choose_absorb },
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
