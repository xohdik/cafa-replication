import json, glob
def fl(t):
    p = t.strip().splitlines()
    return p[0].strip() if p else ''
print('file | condition | n | accuracy | demo | first line == demo output | first line == "10" | correct first line == demo output')
for f in sorted(glob.glob('rerun_*.jsonl')):
    R = [json.loads(l) for l in open(f) if l.strip()]
    R = [r for r in R if r.get('status') == 'ok']
    for c in sorted({r['condition_id'] for r in R}):
        A = [r for r in R if r['condition_id'] == c]
        d = A[0].get('demo', 'orig'); o = A[0].get('demo_out', '10') if 'demo_out' in A[0] else '10'
        pd = ('%.1f%%' % (100.0 * sum(fl(r['prediction']) == o for r in A) / len(A))) if o else '-'
        ed = ('%.1f%%' % (100.0 * sum(fl(r['expected']) == o for r in A) / len(A))) if o else '-'
        p10 = 100.0 * sum(fl(r['prediction']) == '10' for r in A) / len(A)
        print('%-26s C%d n=%d acc=%.3f demo=%-7s copy %-6s | "10": %.1f%% | right answer is that string: %s' % (f, c, len(A), sum(r['correct'] for r in A) / len(A), d, pd, p10, ed))
