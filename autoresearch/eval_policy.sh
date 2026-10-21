#!/bin/bash
# eval_policy.sh <gen> <policy>: judge a new policy on every scored workload.
#
# Full sweeps for the newest workload and for workloads with a LOW kind
# (rule 4 checks every level up to the headline); headline level only for
# the other workloads; w0 at the level below its headline and its top level
# (the overhead rule). Superseded workloads are skipped. Ends with judge.py.
set -e
G=$1; P=$2
cd "$(dirname "$0")"
IFS='|' read -r FULL HEAD W0 <<<"$(python3 - <<'PY'
import glob, json, sys
sys.path.insert(0, '.')
import summarize as S
idx = S.index(S.latest(S.load_rows('summary.csv')))
ws = [json.load(open(f)) | {'_f': f} for f in sorted(glob.glob('workloads/w*.json'))]
ws = [w for w in ws if w.get('status') != 'superseded']
num = lambda w: (int(w['id'][1:].rstrip('abcdefghij')), w['id'])
newest = max(ws, key=num)['id']
full, head, w0 = [], [], ''
for w in ws:
    h = S.headline_load(idx, w['id'], w['load_rps'])
    if w['id'] == 'w0':
        below = max([l for l in w['load_rps'] if l < h])
        w0 = '%s:%d,%d' % (w['_f'], below, w['load_rps'][-1])
    elif w['id'] == newest or any(k.get('hint', {}).get('class') == 'low' for k in w['kinds']):
        full.append(w['_f'])
    else:
        head.append('%s:%d' % (w['_f'], h))
print('|'.join([','.join(full), ','.join(head), w0]))
PY
)"
echo "full sweeps: $FULL"; echo "headline only: $HEAD"; echo "overhead: $W0"
ARGS=""; for f in ${FULL//,/ }; do ARGS="$ARGS --workload $f"; done
./run.py --gen $G $ARGS --policy $P
for wl in ${HEAD//,/ }; do ./run.py --gen $G --workload ${wl%%:*} --policy $P --levels ${wl##*:}; done
./run.py --gen $G --workload ${W0%%:*} --policy $P --levels ${W0##*:}
./summarize.py --gen $G
set +e
./judge.py accept --policy $P; echo "ACCEPT_EXIT=$?"
