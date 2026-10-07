/*
 * thread.h - support for user-level threads
 */

#pragma once

#include <base/compiler.h>
#include <base/list.h>
#include <base/thread.h>
#include <base/trapframe.h>
#include <base/types.h>
#include <runtime/preempt.h>
#include <iokernel/control.h>

struct thread;
typedef void (*thread_fn_t)(void *arg);
typedef struct thread thread_t;

/*
 * Scheduling hints (optional, per thread)
 *
 * A thread may carry any subset of these. A zero-initialized struct means
 * "no hints", which schedules exactly like a thread that never set any.
 */

/* priority classes; NORMAL is 0 so that a zeroed hint struct is the default */
enum {
	THREAD_PRIO_NORMAL = 0,	/* default: FIFO by wake time, as before */
	THREAD_PRIO_HIGH,	/* runs before NORMAL and LOW */
	THREAD_PRIO_LOW,	/* runs only when nothing else is runnable */
	THREAD_PRIO_NR_USER,	/* number of classes an application may set */
	THREAD_PRIO_SOFTIRQ = THREAD_PRIO_NR_USER, /* internal: runtime helper threads */
	THREAD_PRIO_NR,
};

struct thread_hints {
	uint8_t		prio_class;	/* THREAD_PRIO_NORMAL/HIGH/LOW */
	uint64_t	deadline_us;	/* absolute, microtime() clock; 0 = none */
	uint64_t	service_us;	/* expected run time; 0 = unknown */
};

/*
 * Internal thread structure, only intended for building low level primitives.
 */
struct thread {
	bool	main_thread:1;
	bool	has_fsbase:1;
	bool	thread_ready:1;
	bool	hinted:1;	/* true if prio_class != NORMAL or a deadline is set */
	bool	thread_running;
	atomic8_t	interrupt_state;
	uint8_t		prio_class;	/* THREAD_PRIO_* (incl. SOFTIRQ) */
	struct stack	*stack;
	uint16_t	last_cpu;
	uint16_t	cur_kthread;
	uint64_t	ready_tsc;
	uint64_t	total_cycles;
	uint64_t	deadline_tsc;	/* absolute rdtsc() value; 0 = none */
	uint64_t	service_tsc;	/* expected run time in cycles; 0 = unknown */
	struct thread_tf	tf;
	struct list_node	link;
	struct list_node	interruptible_link;
	size_t			waitq_micros;
	uint64_t	tlsvar;
	uint64_t	fsbase;
};

extern uint64_t thread_get_total_cycles(thread_t *th);

/*
 * Low-level routines, these are helpful for bindings and synchronization
 * primitives.
 */

extern void thread_park_and_unlock_np(spinlock_t *l);
extern void thread_park_and_preempt_enable(void);
extern void thread_ready(thread_t *thread);
extern void thread_ready_head(thread_t *thread);
extern thread_t *thread_create(thread_fn_t fn, void *arg);
extern thread_t *thread_create_with_buf(thread_fn_t fn, void **buf, size_t len);
extern void thread_set_fsbase(thread_t *th, uint64_t fsbase);
extern void thread_free(thread_t *th);
extern int thread_set_hints(thread_t *th, const struct thread_hints *h);
extern void thread_get_hints(const thread_t *th, struct thread_hints *out);

DECLARE_PERTHREAD(thread_t *, __self);
DECLARE_PERTHREAD_ALIAS(thread_t * const, __self, __const_self);
DECLARE_PERTHREAD(uint64_t, runtime_fsbase);

static inline unsigned int get_current_affinity(void)
{
	return this_thread_id();
}

/**
 * thread_self - gets the currently running thread
 */
static inline thread_t *thread_self(void)
{
	return perthread_read_const_p(__const_self);
}

static inline uint64_t get_uthread_specific(void)
{
    return thread_self()->tlsvar;
}

static inline void set_uthread_specific(uint64_t val)
{
    thread_self()->tlsvar = val;
}


/*
 * High-level routines, use this API most of the time.
 */

extern void thread_yield(void);
extern int thread_spawn(thread_fn_t fn, void *arg);
extern int thread_spawn_with_hints(thread_fn_t fn, void *arg,
				   const struct thread_hints *h);
extern void thread_exit(void) __noreturn;

/**
 * thread_set_self_hints - sets scheduling hints for the running thread
 * @h: the hints to apply (takes effect the next time this thread is readied)
 */
static inline int thread_set_self_hints(const struct thread_hints *h)
{
	return thread_set_hints(thread_self(), h);
}
