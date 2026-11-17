/*
 * pickbench - cycles per scheduling decision, for each policy, by runqueue
 * depth.
 *
 * Compiles the policies in runtime/sched_policy.h unchanged, against mock
 * thread and kthread types laid out like the real ones for the fields
 * policies read. A "pick" here is what sched_pop_next() does beyond stock
 * Caladan: call the policy, then slide the threads queued before the chosen
 * one back by a slot.
 *
 * Two cases per depth:
 *   hot  - ring and threads already in L1 (the common case: a core keeps
 *          touching its own runqueue)
 *   cold - every thread struct is flushed from the cache before the pick
 *          (an upper bound: threads stolen from or woken on another core)
 *
 * Thread hints are random (class, deadline, service time), so branches
 * cannot be learned. Output: CSV of policy, depth, case, median and p99
 * cycles per pick, with the cost of reading the clock subtracted.
 *
 *   cc -O3 -march=native -o pickbench pickbench.c && ./pickbench
 */

#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <x86intrin.h>

#define RUNTIME_RQ_SIZE 32

enum {
	THREAD_PRIO_NORMAL = 0,
	THREAD_PRIO_HIGH,
	THREAD_PRIO_LOW,
	THREAD_PRIO_NR_USER,
	THREAD_PRIO_SOFTIRQ = THREAD_PRIO_NR_USER,
	THREAD_PRIO_NR,
};

/* same first cache line as runtime's struct thread for the fields read */
typedef struct thread {
	uint8_t		flags;
	uint8_t		thread_running;
	uint8_t		interrupt_state;
	uint8_t		prio_class;
	void		*stack;
	uint16_t	last_cpu;
	uint16_t	cur_kthread;
	uint64_t	ready_tsc;
	uint64_t	total_cycles;
	uint64_t	deadline_tsc;
	uint64_t	service_tsc;
	char		rest[512];	/* trap frame etc.: threads are far apart */
} __attribute__((aligned(64))) thread_t;

struct kthread {
	uint32_t	rq_head;
	uint32_t	rq_tail;
	thread_t	*rq[RUNTIME_RQ_SIZE];
};

#include "../../runtime/sched_policy.h"

#define NSETS	512	/* distinct random runqueues, cycled through */
#define REPS	200000	/* timed picks per policy, depth and case */

static thread_t threads[NSETS][RUNTIME_RQ_SIZE];
static struct kthread ks[NSETS];
static thread_t *orig[NSETS][RUNTIME_RQ_SIZE];	/* rings before a pick */
static uint64_t samples[REPS];

static inline uint64_t tsc_begin(void)
{
	_mm_lfence();
	return __rdtsc();
}

static inline uint64_t tsc_end(void)
{
	unsigned int aux;
	uint64_t t = __rdtscp(&aux);

	_mm_lfence();
	return t;
}

static int cmp_u64(const void *a, const void *b)
{
	uint64_t x = *(const uint64_t *)a, y = *(const uint64_t *)b;

	return x < y ? -1 : x > y;
}

static void fill(uint32_t n)
{
	static const uint8_t classes[] = {
		THREAD_PRIO_NORMAL, THREAD_PRIO_HIGH, THREAD_PRIO_LOW };
	int s;
	uint32_t i;

	for (s = 0; s < NSETS; s++) {
		ks[s].rq_tail = (uint32_t)rand() % RUNTIME_RQ_SIZE;
		ks[s].rq_head = ks[s].rq_tail + n;
		for (i = 0; i < n; i++) {
			thread_t *th = &threads[s][i];

			th->prio_class = classes[rand() % 3];
			th->ready_tsc = 1000000 + i * 100;
			th->deadline_tsc = (rand() % 4) ? 2000000 + rand() % 100000 : 0;
			th->service_tsc = (rand() % 4) ? 1000 + rand() % 100000 : 0;
			ks[s].rq[(ks[s].rq_tail + i) % RUNTIME_RQ_SIZE] = th;
		}
		memcpy(orig[s], ks[s].rq, sizeof(orig[s]));
	}
}

/* one pick: the policy call plus closing the gap, as in sched_pop_next() */
static inline uint32_t pick(sched_choose_fn_t choose, struct kthread *k,
			    uint32_t n)
{
	uint32_t tail = k->rq_tail, best = choose(k, n), i;
	thread_t *th = k->rq[(tail + best) % RUNTIME_RQ_SIZE];

	for (i = best; i > 0; i--)
		k->rq[(tail + i) % RUNTIME_RQ_SIZE] =
			k->rq[(tail + i - 1) % RUNTIME_RQ_SIZE];
	return best + (th == NULL);
}

static void flush(struct kthread *k, uint32_t n)
{
	uint32_t i;

	for (i = 0; i < n; i++)
		_mm_clflush(sched_rq_at(k, i));
	_mm_mfence();
}

static uint64_t clock_cost(void)
{
	int r;

	for (r = 0; r < REPS; r++) {
		uint64_t t0 = tsc_begin();

		samples[r] = tsc_end() - t0;
	}
	qsort(samples, REPS, sizeof(samples[0]), cmp_u64);
	return samples[REPS / 2];
}

int main(void)
{
	static const uint32_t depths[] = { 2, 4, 8, 16, 32 };
	volatile uint32_t sink = 0;
	uint64_t clk;
	size_t p, d;
	int cold, r;

	srand(42);
	clk = clock_cost();
	printf("policy,depth,case,median_cycles,p99_cycles\n");
	for (d = 0; d < sizeof(depths) / sizeof(depths[0]); d++) {
		uint32_t n = depths[d];

		fill(n);
		for (p = 0; p < sizeof(sched_policies) / sizeof(sched_policies[0]); p++) {
			for (cold = 0; cold <= 1; cold++) {
				for (r = 0; r < REPS; r++) {
					struct kthread *k = &ks[r % NSETS];
					uint64_t t0;

					if (cold)
						flush(k, n);
					t0 = tsc_begin();
					sink += pick(sched_policies[p].choose, k, n);
					samples[r] = tsc_end() - t0;
					samples[r] -= samples[r] > clk ? clk : samples[r];
					/* untimed: restore the ring for its next use */
					memcpy(k->rq, orig[r % NSETS], sizeof(k->rq));
				}
				qsort(samples, REPS, sizeof(samples[0]), cmp_u64);
				printf("%s,%u,%s,%lu,%lu\n", sched_policies[p].name, n,
				       cold ? "cold" : "hot",
				       (unsigned long)samples[REPS / 2],
				       (unsigned long)samples[REPS * 99 / 100]);
			}
		}
	}
	fprintf(stderr, "clock cost subtracted: %lu cycles (sink %u)\n",
		(unsigned long)clk, sink);
	return 0;
}
