/*
 * policytest - checks the policies in runtime/sched_policy.h on random
 * runqueues:
 *   - with no hints, every policy picks the oldest thread (stock FIFO)
 *   - a queued helper thread is always picked by every policy except fifo
 *   - with only classes hinted, "hinted" picks what prio picks
 *   - with only deadlines hinted, "hinted" picks what edf picks
 *   - with only service times hinted, "hinted" picks what sjf picks
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
	uint8_t		prio_class;
	uint64_t	ready_tsc;
	uint64_t	deadline_tsc;
	uint64_t	service_tsc;
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

enum { NONE, CLASS, DEADLINE, SERVICE };

static void fill(struct kthread *k, thread_t *ths, uint32_t n, int hint, bool helper)
{
	static const uint8_t classes[] = {
		THREAD_PRIO_NORMAL, THREAD_PRIO_HIGH, THREAD_PRIO_LOW };
	uint32_t i;

	k->rq_tail = (uint32_t)rand() % RUNTIME_RQ_SIZE;
	k->rq_head = k->rq_tail + n;
	for (i = 0; i < n; i++) {
		thread_t *th = &ths[i];

		memset(th, 0, sizeof(*th));
		th->ready_tsc = 1000 + i;
		/* small key ranges so ties are common */
		if (hint == CLASS)
			th->prio_class = classes[rand() % 3];
		if (hint == DEADLINE)
			th->deadline_tsc = rand() % 3 ? 5000 + rand() % 4 : 0;
		if (hint == SERVICE)
			th->service_tsc = rand() % 3 ? 10 + rand() % 4 : 0;
		k->rq[(k->rq_tail + i) % RUNTIME_RQ_SIZE] = th;
	}
	if (helper)
		ths[rand() % n].prio_class = THREAD_PRIO_SOFTIRQ;
}

int main(void)
{
	static const char *const all[] = { "fifo", "prio", "sjf", "edf", "hinted" };
	static const char *const same[] = { [CLASS] = "prio", [DEADLINE] = "edf",
					     [SERVICE] = "sjf" };
	thread_t ths[RUNTIME_RQ_SIZE];
	struct kthread k;
	int t, hint, fails = 0;
	size_t p;

	srand(1);
	for (t = 0; t < 200000; t++) {
		uint32_t n = 2 + rand() % (RUNTIME_RQ_SIZE - 1);

		fill(&k, ths, n, NONE, false);
		for (p = 0; p < 5; p++)
			if (policy(all[p])(&k, n) != 0)
				fails += printf("%s: no hints, not oldest\n", all[p]) > 0;

		fill(&k, ths, n, rand() % 4, true);
		for (p = 1; p < 5; p++) {
			uint32_t i = policy(all[p])(&k, n);

			if (sched_rq_at(&k, i)->prio_class != THREAD_PRIO_SOFTIRQ)
				fails += printf("%s: helper not first\n", all[p]) > 0;
		}

		for (hint = CLASS; hint <= SERVICE; hint++) {
			fill(&k, ths, n, hint, false);
			if (policy("hinted")(&k, n) != policy(same[hint])(&k, n))
				fails += printf("hinted != %s\n", same[hint]) > 0;
		}
		if (fails > 10)
			break;
	}
	printf("%s (%d failures)\n", fails ? "FAIL" : "PASS", fails);
	return fails != 0;
}
