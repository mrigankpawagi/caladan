/*
 * time.h - timekeeping utilities
 */

#pragma once

#include <base/compiler.h>
#include <base/types.h>
#include <asm/ops.h>

#define ONE_SECOND	1000000
#define ONE_MS		1000
#define ONE_US		1

/* read on every time call, so it gets a cache line of its own */
struct timebase {
	uint64_t	start_tsc;
	/* nanoseconds per cycle, 0.64 fixed point */
	uint64_t	tsc_mult;
	/* cycles per nanosecond, 32.32 fixed point, rounded up */
	uint64_t	tsc_rmult;
	/* cycles per microsecond, 32.32 fixed point, rounded up */
	uint64_t	tsc_rmult_us;
	/* rounded to nearest, for display */
	uint64_t	cycles_per_us;
} __aligned(CACHE_LINE_SIZE);

extern struct timebase timebase;

/**
 * cycles_to_ns - converts TSC cycles to nanoseconds, rounding down
 */
static inline uint64_t cycles_to_ns(uint64_t cycles)
{
	return ((__uint128_t)cycles * timebase.tsc_mult) >> 64;
}

/**
 * cycles_to_us - converts TSC cycles to microseconds, rounding down
 */
static inline uint64_t cycles_to_us(uint64_t cycles)
{
	return cycles_to_ns(cycles) / 1000;
}

/**
 * ns_to_cycles - converts nanoseconds to TSC cycles
 *
 * Rounds up, so cycles_to_ns(ns_to_cycles(ns)) >= ns.
 */
static inline uint64_t ns_to_cycles(uint64_t ns)
{
	return ((__uint128_t)ns * timebase.tsc_rmult + 0xffffffff) >> 32;
}

/**
 * us_to_cycles - converts microseconds to TSC cycles
 *
 * Rounds up, so cycles_to_us(us_to_cycles(us)) >= us, and is late by at most
 * 1 + us / 2^32 cycles.
 */
static inline uint64_t us_to_cycles(uint64_t us)
{
	return ((__uint128_t)us * timebase.tsc_rmult_us + 0xffffffff) >> 32;
}

/**
 * nanotime - gets the number of nanoseconds since the process started
 */
static inline uint64_t nanotime(void)
{
	return cycles_to_ns(rdtsc() - timebase.start_tsc);
}

/**
 * microtime - gets the number of microseconds since the process started
 * This routine is very inexpensive, even compared to clock_gettime().
 */
static inline uint64_t microtime(void)
{
	return nanotime() / 1000;
}

extern void __time_delay_us(uint64_t us);

/**
 * delay_us - pauses the CPU for microseconds
 * @us: the number of microseconds
 */
static inline void delay_us(uint64_t us)
{
	__time_delay_us(us);
}

/**
 * delay_ms - pauses the CPU for milliseconds
 * @ms: the number of milliseconds
 */
static inline void delay_ms(uint64_t ms)
{
	/* TODO: yield instead of spin */
	__time_delay_us(ms * ONE_MS);
}
