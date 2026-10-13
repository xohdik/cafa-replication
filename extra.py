import json, glob, re, sys, numpy as np
sys.path.insert(0, '.'); sys.path.insert(0, 'perturbations')
import cafa_revision as c
from scoring_harness import ground_truth
def ids(f):
    if f.endswith('.jsonl'):
        return {r.get('problem_id') for r in c.load_jsonl(f)} - {None}
    d = json.load(open(f)); rows = d['samples'] if isinstance(d, dict) and 'samples' in d else d
    return {r.get('problem_id') for r in rows if isinstance(r, dict)} - {None}
S = {f: ids(f) for f in sorted(glob.glob('rq4_samples*.jsonl') + glob.glob('manifest*.json')) if 'confirm' not in f}
S = {f: s for f, s in S.items() if s}
print('== distinct problem ids per pilot file')
for f, s in S.items(): print(f'  {f:34s} {len(s)}')
u = set().union(*S.values()); print('  UNION of all pilot files:', len(u))
base = S.get('rq4_samples_verified.jsonl', set())
for f, s in S.items():
    if s - base: print(f'  {f}: {len(s - base)} ids not in rq4_samples_verified.jsonl, e.g. {sorted(s - base)[:3]}')
print('== lines of make_confirmation_pairs.py that mention json/exclude/pilot')
for i, l in enumerate(open('make_confirmation_pairs.py'), 1):
    if re.search(r'json|exclu|pilot', l): print(f'  {i}: {l.rstrip()[:140]}')
sc = c.load_orig('responses_deepseek_confirm.json'); keep, Y = c.matrix(sc)
man = json.load(open('manifest_confirm.json')); by = {s['sample_index']: s for s in man['samples']}
R = {1: [], 2: []}
for si in keep:
    s = by[si]
    for cid in (1, 2):
        b = [x for x in s['conditions'] if x['condition_id'] == cid][0]
        e, err = ground_truth(b['source_code'], c.stdin_of(s, b)); R[cid].append(e or '')
nl = {k: np.array([len([l for l in v.strip().splitlines() if l.strip()]) for v in R[k]]) for k in R}
zero = np.array([v.strip() == '0' for v in R[1]])
st = {'both single-line, real output not 0': (nl[1] == 1) & (nl[2] == 1) & ~zero, 'both multi-line': (nl[1] >= 2) & (nl[2] >= 2), 'real output is 0': zero}
sw = c.simple_weights(); E7 = Y @ c.W7
print('== strata (DeepSeek, 10000 program-level resamples)')
for name, m in st.items():
    print(f'  {name}: n={m.sum()}  C1..C8 acc ' + ' '.join(f'{v:.3f}' for v in Y[m].mean(0)))
    if m.sum() < 30: continue
    cols = [E7[m][:, [2]], E7[m][:, [4]]] + [(Y[m] @ w)[:, None] for w in sw.values()]
    labs = ['S effect', 'IxS'] + list(sw)
    for lab, e in zip(labs, cols):
        b = c.boot(e); lo, hi = c.ci(b[:, 0]); print(f'      {lab:14s} {c.fmt(e.mean())} [{c.fmt(lo)},{c.fmt(hi)}]')
