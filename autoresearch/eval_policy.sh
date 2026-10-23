#!/bin/bash
# eval_policy.sh <gen> <candidate>: measure the candidate against the champion
# and judge it (DESIGN.md section 4).
#
# Every workload runs at its headline load (the newest at every level), with
# the champion and the candidate alternating repeat by repeat in one run.py
# invocation per workload, so each comparison comes from one session; w0 runs
# with fifo (the overhead rule). Then judge.py accept prints the verdict.
set -e
G=$1; P=$2
cd "$(dirname "$0")"
CH=$(./judge.py champion)
./judge.py plan | while read -r wid f lv with; do
    [ "$with" = fifo ] && WITH=fifo || WITH=$CH
    # no stdin for run.py: its ssh sessions would swallow the rest of the plan
    ./run.py --gen "$G" --workload "$f" --policy "$WITH,$P" --levels "$lv" </dev/null
done
./summarize.py
set +e
./judge.py accept --policy "$P"; echo "ACCEPT_EXIT=$?"
