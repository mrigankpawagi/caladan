/*
 * time.c - timekeeping utilities
 */

#include <time.h>

#include <base/assert.h>
#include <base/time.h>
#include <base/log.h>
#include <base/init.h>

#include "init_internal.h"

/* calibration windows: without CPUID, and to check CPUID's rate to 100 ppm */
#define CALIBRATE_NS	500000000
#define CPUID_CHECK_NS	20000000

struct timebase timebase;
BUILD_ASSERT(sizeof(timebase) == CACHE_LINE_SIZE);

/**
 * __timer_delay_us - spins the CPU for the specified delay
 * @us: the delay in microseconds
 */
void __time_delay_us(uint64_t us)
{
	uint64_t cycles = us_to_cycles(us);
	unsigned long start = rdtsc();

	while (rdtsc() - start < cycles)
		cpu_relax();
}

static void time_set_mult(uint64_t mult)
{
	timebase.tsc_mult = mult;
	timebase.tsc_rmult = (((__uint128_t)1 << 96) - 1) / mult + 1;
	timebase.tsc_rmult_us = ((1000 * ((__uint128_t)1 << 96)) - 1) / mult + 1;
	timebase.cycles_per_us = (1000 * ((__uint128_t)1 << 64) + mult / 2) / mult;
}

/* derived from DPDK */
static int time_measure_mult(long window_ns, uint64_t *mult)
{
	struct timespec sleeptime = {.tv_nsec = window_ns};
	struct timespec t_start, t_end;
	uint64_t ns, end, start;

	cpu_serialize();
	if (clock_gettime(CLOCK_MONOTONIC_RAW, &t_start))
		return -1;

	start = rdtsc();
	nanosleep(&sleeptime, NULL);
	clock_gettime(CLOCK_MONOTONIC_RAW, &t_end);
	end = rdtscp(NULL);
	ns = ((t_end.tv_sec - t_start.tv_sec) * 1E9);
	ns += (t_end.tv_nsec - t_start.tv_nsec);

	/* tsc_mult must be below 2^64 */
	if (ns >= end - start) {
		log_err("time: TSC below 1 GHz is not supported");
		return -1;
	}

	*mult = ((__uint128_t)ns << 64) / (end - start);
	return 0;
}

/* the TSC rate from CPUID leaf 0x15, as in Linux's native_calibrate_tsc() */
static uint64_t time_cpuid_mult(void)
{
	struct cpuid_info regs;
	uint64_t hz;

	cpuid(0, 0, &regs);
	if (regs.eax < 0x15)
		return 0;

	cpuid(0x15, 0, &regs);
	if (!regs.eax || !regs.ebx || !regs.ecx)
		return 0;

	/* TSC Hz = ECX * EBX / EAX */
	hz = (uint64_t)regs.ecx * regs.ebx;
	if (hz <= 1000000000UL * regs.eax)
		return 0;

	return ((__uint128_t)1000000000 * regs.eax << 64) / hz;
}

static int time_calibrate_tsc(void)
{
	uint64_t mult, cpuid_mult;
	const char *src = "calibration";

	/* tsc_mult may be provided in advance */
	if (timebase.tsc_mult) {
		time_set_mult(timebase.tsc_mult);
		timebase.start_tsc = rdtsc();
		return 0;
	}

	/* distrust a leaf that disagrees with the clock */
	cpuid_mult = time_cpuid_mult();
	if (cpuid_mult) {
		if (time_measure_mult(CPUID_CHECK_NS, &mult))
			return -1;
		if (mult > cpuid_mult + cpuid_mult / 10000 ||
		    mult < cpuid_mult - cpuid_mult / 10000) {
			log_warn("time: CPUID leaf 0x15 says %.3f ticks / us, "
				 "measured %.3f, calibrating",
				 1000 * 0x1p64 / cpuid_mult,
				 1000 * 0x1p64 / mult);
			cpuid_mult = 0;
		}
	}

	if (cpuid_mult) {
		mult = cpuid_mult;
		src = "CPUID leaf 0x15";
	} else if (time_measure_mult(CALIBRATE_NS, &mult)) {
		return -1;
	}

	time_set_mult(mult);
	log_info("time: %.3f ticks / us from %s", 1000 * 0x1p64 / mult, src);

	/* record the start time of the binary */
	timebase.start_tsc = rdtsc();
	return 0;
}

/**
 * time_init - global time initialization
 *
 * Returns 0 if successful, otherwise fail.
 */
int time_init(void)
{
	return time_calibrate_tsc();
}
