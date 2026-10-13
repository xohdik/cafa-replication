import json, glob
def fl(t):
    p = t.strip().splitlines()
    return p[0].strip() if p else ''
for tag in ['rerun_ds_q4', 'rerun_sc2_q4', 'rerun_ds_q8']:
    R = []
    for f in sorted(glob.glob(tag + '*.jsonl')):
        R += [json.loads(l) for l in open(f) if l.strip()]
    for c in (1, 2, 5, 6):
        A = [r for r in R if r['condition_id'] == c and r.get('status') == 'ok']
        if not A: continue
        miss = [r for r in A if not r['correct'] and fl(r['prediction']) != fl(r['expected'])]
        p10 = sum(1 for r in A if fl(r['prediction']) == '10')
        m10 = sum(1 for r in miss if fl(r['prediction']) == '10')
        e10 = sum(1 for r in A if fl(r['expected']) == '10')
        print('%-13s C%d n=%d acc=%.3f | first line predicted "10": %.1f%% of all, %d of %d first-line misses (%.1f%%) | expected first line "10": %.1f%% of all' % (tag, c, len(A), sum(r['correct'] for r in A) / len(A), 100.0 * p10 / len(A), m10, len(miss), 100.0 * m10 / max(1, len(miss)), 100.0 * e10 / len(A)))
