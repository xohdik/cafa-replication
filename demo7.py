import json, numpy as np
M = {"DeepSeek-Coder": (["rerun_ds_q4.jsonl", "rerun_ds_q4_c56.jsonl"], ["rerun_dsorig8_q4.jsonl"]),
     "StarCoder2": (["rerun_sc2_q4.jsonl", "rerun_sc2_q4_c56.jsonl"], ["rerun_sc2orig8_q4.jsonl"])}
def load(fs):
    d = {}
    for f in fs:
        for l in open(f):
            r = json.loads(l)
            if r.get("status") == "ok":
                p = (r.get("prediction") or "").strip().split("\n")[0].strip()
                d[(r["sample_index"], r["condition_id"])] = (1.0 if r["correct"] else 0.0, p)
    return d
def ci(v, rng, B=10000):
    n = len(v); m = np.empty(B)
    for i in range(0, B, 1000):
        m[i:i+1000] = v[rng.integers(0, n, (1000, n))].mean(1)
    return v.mean() * 100, *np.percentile(m, [2.5, 97.5]) * 100
for name, (fo, f8) in M.items():
    D = [load(fo), load(f8)]
    ks = sorted(set.intersection(*[set(s for s, c in d) for d in D]))
    ks = [s for s in ks if all((s, c) in d for d in D for c in (1, 2, 5, 6))]
    print("==", name, len(ks), "programs scored under both demonstrations")
    E = []
    for lab, d in zip(("orig (answer 10)", "orig8 (answer 8)"), D):
        A = {c: np.array([d[(s, c)][0] for s in ks]) for c in (1, 2, 5, 6)}
        sh = lambda c, x: np.mean([d[(s, c)][1] == x for s in ks]) * 100
        e = {"S|orig": A[2] - A[1], "S|obf": A[6] - A[5], "I|real": A[5] - A[1], "I|synth": A[6] - A[2], "IxS": (A[6] - A[2]) - (A[5] - A[1])}
        E.append(e)
        print(f"{lab}: acc C1 {A[1].mean():.3f} C2 {A[2].mean():.3f} C5 {A[5].mean():.3f} C6 {A[6].mean():.3f}")
        print("   first line = 10: " + " ".join(f"C{c} {sh(c,'10'):.1f}%" for c in (1, 2, 5, 6)) + " | first line = 8: " + " ".join(f"C{c} {sh(c,'8'):.1f}%" for c in (1, 2, 5, 6)))
        for k, v in e.items():
            x = ci(v, np.random.default_rng(1)); print(f"     {k:8s} {x[0]:+.1f} [{x[1]:+.1f}, {x[2]:+.1f}]")
    for k in ("S|orig", "IxS"):
        x = ci(E[1][k] - E[0][k], np.random.default_rng(2)); print(f"  orig8 minus orig, {k}: {x[0]:+.1f} [{x[1]:+.1f}, {x[2]:+.1f}]")
