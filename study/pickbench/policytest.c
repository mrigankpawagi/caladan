/*
 * policytest - checks the key-based policies in runtime/sched_policy.h
 * against straightforward reference comparators, on random runqueues.
 *
 * The references compare hint fields directly (class, then deadline, then
 * service time, then ring position), so this checks that packing the hints
 * into one 64-bit key, and each policy's choice of key bits, picks exactly
 * the thread the policy's one-line rule describes. It also checks:
 *   - with no hints, every policy picks the earliest ring slot (stock fifo)
 *   - a queued helper thread is picked by every policy except fifo
 *   - packing preserves order at the field limits (deadline and size near
 *     their maximum, "none" after every real value)
 *
 *   cc -O2 -Wall -o policytest policytest.c && ./policytest
 */

#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define RUNTIME_RQ_SIZE 32

enum {
	THREAD_PRIO_NORMAL = 0,
	THREAD_PRIO_HIGH,
	THREAD_PRIO_LOW,
	THREAD_PRIO_NR_USER,
	THREAD_PRIO_SOFTIRQ = THREAD_PRIO_NR_USER,
	THREAD_PRIO_NR,
};

typedef struct thread {
	uint64_t	sched_key;
	/* the hints, kept unpacked for the reference comparators */
	uint8_t		prio_class;
	uint64_t	deadline_us;	/* 0 = none */
	uint64_t	service_us;	/* 0 = none */
} thread_t;

struct kthread {
	uint32_t	rq_head;
	uint32_t	rq_tail;
	thread_t	*rq[RUNTIME_RQ_SIZE];
};

#include "../../runtime/sched_policy.h"

static sched_choose_fn_t policy(const char *name)
{
	size_t i;

	for (i = 0; i < sizeof(sched_policies) / sizeof(sched_policies[0]); i++)
		if (!strcmp(sched_policies[i].name, name))
			return sched_policies[i].choose;
	abort();
}

/* reference: rank of a class (smaller runs sooner) */
static int ref_class(const thread_t *t)
{
	switch (t->prio_class) {
	case THREAD_PRIO_SOFTIRQ: return 0;
	case THREAD_PRIO_HIGH: return 1;
	case THREAD_PRIO_NORMAL: return 2;
	default: return 3;
	}
}

static uint64_t ref_dl(const thread_t *t)
{
	return t->deadline_us ? t->deadline_us : UINT64_MAX;
}

static uint64_t ref_svc(const thread_t *t)
{
	return t->service_us ? t->service_us : UINT64_MAX;
}

/* reference comparators: <0 if a runs before b (ties: earlier slot wins) */
static int cmp_u(uint64_t a, uint64_t b) { return a < b ? -1 : a > b; }

static int ref_cmp(const char *pol, const thread_t *a, const thread_t *b)
{
	int c;

	/* every policy but fifo takes a helper thread first */
	if ((ref_class(a) == 0) != (ref_class(b) == 0))
		return ref_class(a) == 0 ? -1 : 1;
	if (!strcmp(pol, "edf"))
		return cmp_u(ref_dl(a), ref_dl(b));
	if ((c = ref_class(a) - ref_class(b)))
		return c;
	if (!strcmp(pol, "prio"))
		return 0;
	if ((c = cmp_u(ref_dl(a), ref_dl(b))))
		return c;
	if (!strcmp(pol, "prio_edf"))
		return 0;
	return cmp_u(ref_svc(a), ref_svc(b));	/* hinted */
}

static uint32_t ref_choose(const char *pol, const struct kthread *k, uint32_t n)
{
	uint32_t i, best = 0;

	if (!strcmp(pol, "fifo"))
		return 0;
	for (i = 1; i < n; i++)
		if (ref_cmp(pol, sched_rq_at(k, i), sched_rq_at(k, best)) < 0)
			best = i;
	/* a helper thread is taken at its first occurrence */
	for (i = 0; i < n; i++)
		if (ref_class(sched_rq_at(k, i)) == 0)
			return i;
	return best;
}

static void fill(struct kthread *k, thread_t *ths, uint32_t n, bool hints,
		 bool helper)
{
	static const uint8_t classes[] = {
		THREAD_PRIO_NORMAL, THREAD_PRIO_HIGH, THREAD_PRIO_LOW };
	uint32_t i;

	k->rq_tail = (uint32_t)rand() % RUNTIME_RQ_SIZE;
	k->rq_head = k->rq_tail + n;
	for (i = 0; i < n; i++) {
		thread_t *th = &ths[i];

		memset(th, 0, sizeof(*th));
		th->prio_class = THREAD_PRIO_NORMAL;
		if (hints) {
			/* small ranges so ties are common at every level */
			th->prio_class = classes[rand() % 3];
			th->deadline_us = rand() % 3 ? 1000 + rand() % 4 : 0;
			th->service_us = rand() % 3 ? 5 + rand() % 3 : 0;
		}
		th->sched_key = sched_key_make(th->prio_class, th->deadline_us,
					       th->service_us);
		k->rq[(k->rq_tail + i) % RUNTIME_RQ_SIZE] = th;
	}
	if (helper) {
		thread_t *th = &ths[rand() % n];

		th->prio_class = THREAD_PRIO_SOFTIRQ;
		th->deadline_us = th->service_us = 0;
		th->sched_key = 0;
	}
}

static int check_limits(void)
{
	const uint64_t dmax = SCHED_KEY_DL_NONE - 1, smax = SCHED_KEY_SVC_NONE - 1;
	struct { uint64_t d1, s1, d2, s2; } c[] = {
		{ dmax - 1, 1, dmax, 1 },	/* deadlines near the limit */
		{ dmax, 1, 0, 1 },		/* any deadline before none */
		{ 5, smax - 1, 5, smax },	/* sizes near the limit */
		{ 5, smax, 5, 0 },		/* any size before none */
		{ 5, 1, 5, 1u << 30 },		/* oversized sizes saturate */
	};
	int fails = 0;
	size_t i;

	for (i = 0; i < sizeof(c) / sizeof(c[0]); i++) {
		uint64_t a = sched_key_make(THREAD_PRIO_HIGH, c[i].d1, c[i].s1);
		uint64_t b = sched_key_make(THREAD_PRIO_HIGH, c[i].d2, c[i].s2);

		if (!(a < b) && !(i == 4 && a <= b))
			fails += printf("key limits case %zu: %#lx !< %#lx\n", i,
					(unsigned long)a, (unsigned long)b) > 0;
	}
	if (!(sched_key_make(THREAD_PRIO_HIGH, 0, 0) <
	      sched_key_make(THREAD_PRIO_NORMAL, 1, 1)))
		fails += printf("class does not dominate deadline\n") > 0;
	return fails;
}

int main(void)
{
	static const char *const pols[] = { "fifo", "prio", "prio_edf", "hinted", "edf" };
	thread_t ths[RUNTIME_RQ_SIZE];
	struct kthread k;
	int t, fails = check_limits();
	size_t p;

	srand(1);
	for (t = 0; t < 300000 && fails < 10; t++) {
		uint32_t n = 2 + rand() % (RUNTIME_RQ_SIZE - 1);

		fill(&k, ths, n, false, false);
		for (p = 0; p < 5; p++)
			if (policy(pols[p])(&k, n) != 0)
				fails += printf("%s: no hints, not slot 0\n", pols[p]) > 0;

		fill(&k, ths, n, true, rand() % 4 == 0);
		for (p = 0; p < 5; p++) {
			uint32_t got = policy(pols[p])(&k, n);
			uint32_t want = ref_choose(pols[p], &k, n);

			if (got != want)
				fails += printf("%s: picked slot %u, reference %u\n",
						pols[p], got, want) > 0;
		}
	}
	printf("%s (%d failures)\n", fails ? "FAIL" : "PASS", fails);
	return fails != 0;
}
