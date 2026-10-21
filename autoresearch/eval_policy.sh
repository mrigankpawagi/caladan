#!/bin/bash
# eval_policy.sh <gen> <policy>: judge a new policy on every scored workload.
#
# Full sweep for the newest workload; the headline level and the two below it
# for older workloads with a LOW kind (rule 4 checks the levels up to the
# headline that were measured; LOW has answered 100% at every level so far);
# headline level only for the other workloads; w0 at the level below its
# headline and its top level (the overhead rule). Superseded workloads are
# skipped. Ends with judge.py.
#
# Paired confirmation: the champion's numbers on older workloads come from an
# earlier session, and deadline-met drifts by about 1.5 points between
# sessions (README). If the judge rejects the policy although its score on
# the newest workload improved enough (rule 1), the policy and the champion
# are re-measured back to back on every failing workload at the same levels
# (run.py --paired; the full sweep for the newest workload) and the judge
# decides those workloads from the paired runs.
set -e
G=$1; P=$2
cd "$(dirname "$0")"
# one line per workload: <kind> <id> <spec file> <levels or "all">
PLAN="$(python3 - <<'PY'
import glob, json, sys
sys.path.insert(0, '.')
import summarize as S
idx = S.index(S.latest(S.load_rows('summary.csv')))
ws = [json.load(open(f)) | {'_f': f} for f in sorted(glob.glob('workloads/w*.json'))]
ws = [w for w in ws if w.get('status') != 'superseded']
num = lambda w: (int(w['id'][1:].rstrip('abcdefghij')), w['id'])
newest = max(ws, key=num)['id']
low = lambda w: any(k.get('hint', {}).get('class') == 'low' for k in w['kinds'])
for w in ws:
    h = S.headline_load(idx, w['id'], w['load_rps'])
    if w['id'] == 'w0':
        below = max([l for l in w['load_rps'] if l < h])
        kind, lv = 'w0', '%d,%d' % (below, w['load_rps'][-1])
    elif w['id'] == newest:
        kind, lv = 'full', 'all'
    elif low(w):
        kind, lv = 'head', ','.join(str(l) for l in [l for l in w['load_rps'] if l <= h][-3:])
    else:
        kind, lv = 'head', '%d' % h
    print(kind, w['id'], w['_f'], lv)
PY
)"
echo "$PLAN"
ARGS=""
while read -r kind wid f lv; do
    [ "$kind" = full ] && ARGS="$ARGS --workload $f"
done <<<"$PLAN"
./run.py --gen $G $ARGS --policy $P
while read -r kind wid f lv; do
    [ "$kind" = full ] && continue
    ./run.py --gen $G --workload $f --policy $P --levels $lv
done <<<"$PLAN"
./summarize.py --gen $G
set +e
OUT="$(./judge.py accept --policy $P)"; EXIT=$?
echo "$OUT"; echo "ACCEPT_EXIT=$EXIT"
LINE="$(grep '^FAILED_ON:' <<<"$OUT")"
[ $EXIT -eq 0 ] || [ -z "$LINE" ] && exit 0
FAILED="$(sed 's/^FAILED_ON: \(.*\) NEWEST: .*/\1/' <<<"$LINE")"
NEWEST="$(sed 's/.* NEWEST: \([^ ]*\) .*/\1/' <<<"$LINE")"
CHAMP="$(sed 's/.* CHAMPION: \([^ ]*\) .*/\1/' <<<"$LINE")"
SCORE="$(sed 's/.* SCORE: //' <<<"$LINE")"
if [ "$SCORE" != ok ]; then
    echo "the score on $NEWEST did not improve enough: no paired confirmation"
    exit 0
fi
set -e
echo "paired confirmation of $P against $CHAMP on: $FAILED"
for wid in $FAILED; do
    read -r kind _ f lv <<<"$(awk -v w="$wid" '$2 == w' <<<"$PLAN")"
    [ "$lv" = all ] && LV="" || LV="--levels $lv"
    ./run.py --gen $G --workload $f --policy $CHAMP,$P $LV --paired
done
./summarize.py --gen $G
set +e
./judge.py accept --policy $P; echo "ACCEPT_EXIT=$?"
