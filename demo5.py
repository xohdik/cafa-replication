import sys, os, numpy as np
sys.path.insert(0, '.')
import cafa_revision as c
G = {'DS orig': ['rerun_ds_q4.jsonl', 'rerun_ds_q4_c56.jsonl'], 'DS reverse': ['rerun_dsrev_q4.jsonl'], 'DS none': ['rerun_dsnone_q4.jsonl'],
     'SC2 orig': ['rerun_sc2_q4.jsonl', 'rerun_sc2_q4_c56.jsonl'], 'SC2 reverse': ['rerun_sc2rev_q4.jsonl'], 'SC2 none': ['rerun_sc2none_q4.jsonl']}
cids = [1, 2, 5, 6]
names = ['S|orig-names', 'S|obf-names', 'I|real', 'I|synth', 'IxS']
def load(files):
    d = {}
    for f in files:
        if os.path.exists(f): d.update(c.rerun_scores(f))
    return d
def con(Y):
    y1, y2, y5, y6 = Y.T
    return np.stack([y2 - y1, y6 - y5, y5 - y1, y6 - y2, (y6 - y2) - (y5 - y1)], 1)
for model in ('DS', 'SC2'):
    S = {k: load(v) for k, v in G.items() if k.startswith(model)}
    S = {k: v for k, v in S.items() if v}
    if not S: continue
    keep = None
    for v in S.values():
        ks = {p for (p, cc) in v if all((p, x) in v for x in cids)}
        keep = ks if keep is None else keep & ks
    keep = sorted(keep)
    Y = {k: np.array([[v[(p, x)] for x in cids] for p in keep]) for k, v in S.items()}
    n = len(keep); rng = np.random.default_rng(0)
    B = np.zeros((len(S), 10000, 5)); idxs = []
    for s in range(0, 10000, 250):
        ix = rng.integers(0, n, (250, n))
        for j, k in enumerate(S): B[j, s:s + 250] = con(Y[k])[ix].mean(1)
    print('\n== %s: %d programs scored in every prompt variant' % (model, n))
    labs = list(S)
    for j, k in enumerate(labs):
        a = Y[k].mean(0); e = con(Y[k]).mean(0)
        print('%-12s acc C1 %.3f C2 %.3f C5 %.3f C6 %.3f' % (k, *a))
        for i, nm in enumerate(names):
            lo, hi = np.percentile(B[j, :, i], [2.5, 97.5]); print('     %-13s %+.3f [%+.3f, %+.3f]' % (nm, e[i], lo, hi))
    o = labs.index(model + ' orig') if model + ' orig' in labs else None
    if o is not None:
        for j, k in enumerate(labs):
            if j == o: continue
            for i in (0, 4):
                d = B[j, :, i] - B[o, :, i]; lo, hi = np.percentile(d, [2.5, 97.5])
                print('  %s minus orig, %-12s %+.3f [%+.3f, %+.3f]' % (k, names[i], con(Y[k]).mean(0)[i] - con(Y[model + ' orig']).mean(0)[i], lo, hi))
