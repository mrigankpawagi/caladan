#!/usr/bin/env python3
"""Reviews a policy agent's C code and inserts it into the policy region.

  ./apply_policy.py proposal.c        check, then edit runtime/sched.c
  ./apply_policy.py --check proposal.c   check only

The file holds the agent's code block: one or more functions (the policy's
choose_<name> plus optional static helpers or constants) and exactly one table
row like `{ "edf_high", choose_edf_high },`. The functions are inserted just
before the sched_policies[] table and the row at its end, so nothing outside
the policy region changes. The static review enforces the contract in
policies/README.md; it is a first filter, not a proof, and the orchestrator
still reads the code.
"""

import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCHED = os.path.join(HERE, "..", "runtime", "sched.c")
BEGIN = "/* ===== BEGIN SCHEDULING POLICY REGION"
END = "/* ===== END SCHEDULING POLICY REGION"
TABLE = "static const struct {\n\tconst char\t\t*name;\n\tsched_choose_fn_t\tchoose;\n} sched_policies[] = {\n"
FORBIDDEN = {
    r"\bmalloc\b|\bcalloc\b|\brealloc\b|\bsmalloc\b|\bfree\s*\(": "allocates memory",
    r"\bspin_lock\w*|\bmutex_\w+|\bcondvar_\w+|\bwaitgroup_\w+": "takes a lock or waits",
    r"\bthread_park\w*|\bthread_yield\b|\bthread_ready\w*|\bkthread_park\w*": "blocks or reschedules",
    r"\brq_overflow\b|\blist_\w+": "touches the overflow list or a linked list",
    r"\bk->rq\s*\[[^\]]*\]\s*=[^=]|\brq_tail\b|\brq_head\b": "modifies the runqueue",
    r"\bfloat\b|\bdouble\b": "uses floating point",
    r"\bprintf\b|\blog_\w+\s*\(": "prints in the scheduling hot path",
    r"\bwhile\s*\(\s*1\s*\)|\bfor\s*\(\s*;\s*;\s*\)|\bgoto\b": "may not be bounded",
    r"#\s*include|#\s*define\s+(?!POLICY_)\w+": "adds includes or macros (only POLICY_* macros allowed)",
}


def review(code, sched):
    errors = []
    rows = re.findall(r'^\s*\{\s*"([a-z][a-z0-9_]*)"\s*,\s*(choose_[a-z0-9_]+)\s*\}\s*,\s*$',
                      code, re.M)
    if len(rows) != 1:
        errors.append("need exactly one table row like { \"name\", choose_name },")
        return errors, None, None
    name, fn = rows[0]
    region = sched[sched.index(BEGIN):sched.index(END)]
    if re.search(r'\{\s*"%s"\s*,' % re.escape(name), region):
        errors.append("policy name %r already exists" % name)
    if not re.search(r"static\s+uint32_t\s+%s\s*\(\s*struct\s+kthread\s+\*\s*k\s*,\s*"
                     r"uint32_t\s+n\s*\)" % re.escape(fn), code):
        errors.append("%s must be 'static uint32_t %s(struct kthread *k, uint32_t n)'"
                      % (fn, fn))
    body = re.sub(r'^\s*\{\s*"[a-z0-9_]+"\s*,\s*choose_\w+\s*\}\s*,\s*$', "", code, flags=re.M)
    nocomment = re.sub(r"/\*.*?\*/|//[^\n]*", "", body, flags=re.S)
    for pat, why in FORBIDDEN.items():
        m = re.search(pat, nocomment)
        if m:
            errors.append("%s: %r" % (why, m.group(0)))
    for f in re.findall(r"^static[^;{]*\b(\w+)\s*\(", nocomment, re.M):
        if f in region and f not in (fn,):
            errors.append("helper %s already exists in the region" % f)
    if nocomment.count("rdtsc()") > 1:
        errors.append("calls rdtsc() more than once (contract: at most once per pick)")
    return errors, name, (fn, body.strip("\n"))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("proposal")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    code = open(args.proposal).read()
    sched = open(SCHED).read()
    errors, name, parts = review(code, sched)
    if errors:
        print("REVIEW FAILED:")
        for e in errors:
            print("  -", e)
        return 1
    print("review passed: policy %r (%s)" % (name, parts[0]))
    if args.check:
        return 0
    assert sched.count(TABLE) == 1, "policy table not found"
    sched = sched.replace(TABLE, parts[1] + "\n\n" + TABLE)
    tbl = sched.index(TABLE) + len(TABLE)
    close = sched.index("};", tbl)
    sched = sched[:close] + '\t{ "%s",\t%s },\n' % (name, parts[0]) + sched[close:]
    open(SCHED, "w").write(sched)
    print("inserted into runtime/sched.c")
    return 0


if __name__ == "__main__":
    sys.exit(main())
