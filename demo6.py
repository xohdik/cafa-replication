import json, numpy as np
M = {"CodeLlama": ("rerun_cl_q4.jsonl", "rerun_clnone_q4.jsonl"),
     "Qwen-7B": ("rerun_q7_q4.jsonl", "rerun_q7none_q4.jsonl"),
     "Qwen-14B": ("rerun_q14_q4.jsonl", "rerun_q14none_q4.jsonl")}
def load(f):
    d = {}
    for l in open(f):
        r = json.loads(l)
        if r.get("status") == "ok":
            p = (r.get("prediction") or "").strip().split("\n")[0].strip()
            d[(r["sample_index"], r["condition_id"])] = (1.0 if r["correct"] else 0.0, p == "10")
    return d
def eff(d, ks):
    return {"S|orig": d[2] - d[1], "S|obf": d[6] - d[5], "I|real": d[5] - d[1], "I|synth": d[6] - d[2],
            "IxS": (d[6] - d[2]) - (d[5] - d[1])}
def ci(v, rng, B=10000):
    n = len(v); m = np.empty(B)
    for i in range(0, B, 1000):
        m[i:i+1000] = v[rng.integers(0, n, (1000, n))].mean(1)
    return v.mean() * 100, *np.percentile(m, [2.5, 97.5]) * 100
for name, files in M.items():
    D = [load(f) for f in files]
    ks = sorted(set.intersection(*[set(s for s, c in d) for d in D]))
    ks = [s for s in ks if all((s, c) in d for d in D for c in (1, 2, 5, 6))]
    print("==", name, len(ks), "programs scored in both prompts")
    E = []
    for lab, d in zip(("orig", "none"), D):
        A = {c: np.array([d[(s, c)][0] for s in ks]) for c in (1, 2, 5, 6)}
        T = {c: np.mean([d[(s, c)][1] for s in ks]) * 100 for c in (1, 2, 5, 6)}
        e = eff(A, ks); E.append(e)
        print(f"{lab:5s} acc C1 {A[1].mean():.3f} C2 {A[2].mean():.3f} C5 {A[5].mean():.3f} C6 {A[6].mean():.3f} | first line 10: " + " ".join(f"C{c} {T[c]:.1f}%" for c in T))
        for k, v in e.items():
            x = ci(v, np.random.default_rng(1))
            print(f"     {k:8s} {x[0]:+.1f} [{x[1]:+.1f}, {x[2]:+.1f}]")
    for k in ("S|orig", "IxS"):
        x = ci(E[1][k] - E[0][k], np.random.default_rng(2))
        print(f"  none minus orig, {k}: {x[0]:+.1f} [{x[1]:+.1f}, {x[2]:+.1f}]")
