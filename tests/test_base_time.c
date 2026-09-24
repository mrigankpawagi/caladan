/*
 * test_base_time.c - tests the TSC time base
 */

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>

#include <base/init.h>
#include <base/stddef.h>
#include <base/log.h>
#include <base/time.h>

#define READS		10000000
#define CONVERSIONS	1000000
#define DRIFT_SECS	2
/* allowed drift against CLOCK_MONOTONIC_RAW, in parts per million */
#define MAX_DRIFT_PPM	10.0

static int failures;

#define CHECK(cond, fmt, ...)						\
do {									\
	if (!(cond)) {							\
		log_err("FAIL %s: " fmt, #cond, ##__VA_ARGS__);		\
		failures++;						\
	}								\
} while (0)

static uint64_t raw_ns(void)
{
	struct timespec ts;

	clock_gettime(CLOCK_MONOTONIC_RAW, &ts);
	return ts.tv_sec * 1000000000UL + ts.tv_nsec;
}

static uint64_t rand64(void)
{
	return ((uint64_t)random() << 42) ^ ((uint64_t)random() << 21) ^
	       random();
}

static void test_monotonic(void)
{
	uint64_t ns, us, last_ns = 0, last_us = 0;
	unsigned long sub_us = 0;
	int i;

	for (i = 0; i < READS; i++) {
		ns = nanotime();
		us = microtime();
		CHECK(ns >= last_ns, "%lu < %lu", ns, last_ns);
		CHECK(us >= last_us, "%lu < %lu", us, last_us);
		/* nanotime() truncated to us must agree with microtime() */
		CHECK(ns / 1000 <= us, "%lu / 1000 > %lu", ns, us);
		last_ns = nanotime();
		CHECK(us <= last_ns / 1000, "%lu > %lu / 1000", us, last_ns);
		last_us = us;
		sub_us += ns % 1000 != 0;
		if (failures)
			return;
	}
	CHECK(sub_us > 0, "nanotime() only returned whole microseconds");
}

/*
 * ns_to_cycles(ns) is the first cycle that reads back as ns, or at most
 * (ns >> 32) + 1 cycles after it.
 */
static void check_ns_to_cycles(uint64_t ns)
{
	uint64_t c = ns_to_cycles(ns), slack = (ns >> 32) + 2;

	CHECK(cycles_to_ns(c) >= ns, "ns %lu cycles %lu", ns, c);
	CHECK(c < slack || cycles_to_ns(c - slack) < ns,
	      "ns %lu cycles %lu", ns, c);
}

/* us deadlines converted to cycles are never early */
static void test_conversions(void)
{
	uint64_t ns, us, c;
	int i;

	for (i = 0; i < CONVERSIONS; i++) {
		/* ns_to_cycles() overflows past 2^64 cycles */
		ns = i < 1000 ? i : rand64() >> (2 + i % 62);
		check_ns_to_cycles(ns);

		us = i < 1000 ? i : rand64() % (1000UL * ONE_SECOND);
		c = us_to_cycles(us);
		CHECK(cycles_to_us(c) >= us, "us %lu cycles %lu", us, c);
		/* at most 1 + us / 2^32 cycles late */
		CHECK(c < (us >> 32) + 2 ||
		      cycles_to_ns(c - (us >> 32) - 2) < us * 1000,
		      "us %lu cycles %lu", us, c);
		check_ns_to_cycles(us * 1000);
		if (failures)
			return;
	}
}

/* the rate comes from CPUID leaf 0x15 when the CPU reports one */
static void test_rate_source(void)
{
	struct cpuid_info regs;
	uint64_t mult;

	cpuid(0, 0, &regs);
	if (regs.eax < 0x15)
		regs.eax = 0;
	else
		cpuid(0x15, 0, &regs);
	if (!regs.eax || !regs.ebx || !regs.ecx) {
		log_info("no CPUID leaf 0x15, rate calibrated");
		return;
	}

	log_info("CPUID leaf 0x15: eax %u ebx %u ecx %u", regs.eax, regs.ebx,
		 regs.ecx);
	mult = ((__uint128_t)1000000000 * regs.eax << 64) /
	       ((uint64_t)regs.ecx * regs.ebx);
	CHECK(timebase.tsc_mult == mult, "tsc_mult %lu, CPUID %lu",
	      timebase.tsc_mult, mult);
}

/*
 * cycles_to_ns() is within 1 ns of the exact rate for any 64-bit cycle
 * count, checked against 128-bit arithmetic for a range of TSC rates.
 */
static void test_mult_error(void)
{
	uint64_t saved_mult = timebase.tsc_mult;
	/* cycles per 10^9 ns, i.e. TSC rates in Hz */
	static const uint64_t rates[] = {
		1000000001UL, 1999999999UL, 2100000000UL, 2399987654UL,
		2992968000UL, 3500000000UL, 4999999999UL,
	};
	__uint128_t exact;
	uint64_t cyc, ns;
	unsigned int i, j;

	for (i = 0; i < ARRAY_SIZE(rates); i++) {
		timebase.tsc_mult = ((__uint128_t)1000000000UL << 64) / rates[i];
		for (j = 0; j < CONVERSIONS; j++) {
			cyc = j == 0 ? UINT64_MAX : rand64() >> (j % 64);
			exact = (__uint128_t)cyc * 1000000000UL / rates[i];
			ns = cycles_to_ns(cyc);
			CHECK(ns <= exact && exact - ns <= 1,
			      "rate %lu cycles %lu ns %lu exact %lu",
			      rates[i], cyc, ns, (uint64_t)exact);
			if (failures)
				goto out;
		}
	}
out:
	timebase.tsc_mult = saved_mult;
}

static void test_drift(void)
{
	uint64_t raw0, raw1, ns0, ns1, us0, us1;
	double drift_ppm, us_drift_ppm, delay_ppm;

	raw0 = raw_ns();
	ns0 = nanotime();
	us0 = microtime();
	delay_us(DRIFT_SECS * ONE_SECOND);
	raw1 = raw_ns();
	ns1 = nanotime();
	us1 = microtime();

	drift_ppm = ((double)(ns1 - ns0) - (raw1 - raw0)) * 1e6 /
		    (raw1 - raw0);
	us_drift_ppm = ((double)(us1 - us0) * 1000 - (raw1 - raw0)) * 1e6 /
		       (raw1 - raw0);
	delay_ppm = ((double)(raw1 - raw0) - DRIFT_SECS * 1e9) * 1e6 /
		    (DRIFT_SECS * 1e9);
	log_info("drift over %d s: nanotime %.3f ppm, microtime %.3f ppm, "
		 "delay_us %.3f ppm", DRIFT_SECS, drift_ppm, us_drift_ppm,
		 delay_ppm);

	CHECK(drift_ppm < MAX_DRIFT_PPM && drift_ppm > -MAX_DRIFT_PPM,
	      "%.3f ppm", drift_ppm);
	/* delay_us() must not be shorter than asked */
	CHECK(delay_ppm > -MAX_DRIFT_PPM, "%.3f ppm", delay_ppm);
}

int main(int argc, char *argv[])
{
	int ret;

	ret = base_init();
	if (ret) {
		log_err("base_init() failed, ret = %d", ret);
		return 1;
	}

	test_rate_source();
	test_monotonic();
	test_conversions();
	test_mult_error();
	test_drift();

	if (failures) {
		log_err("%d checks failed", failures);
		return 1;
	}

	log_info("time tests passed");
	return 0;
}
