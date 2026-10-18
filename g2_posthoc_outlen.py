#!/usr/bin/env python3
"""g2_posthoc_outlen.py -- POST HOC diagnostic (not pre-registered): is the source gap under G2 an output-length effect?
Accuracy by number of expected output tokens for real (conditions 1,5), G1 (2,6) and G2 (2,6), original prompt, A original; and the source effect
restricted to samples whose real and G2 outputs are both a single token. Scores in points."""
import json, os
import numpy as np
import cafa_revision as cr

TAGS = {"ds": "DeepSeek-Coder-6.7B", "sc2": "StarCoder2", "cl": "CodeLlama", "q7": "Qwen2.5-Coder-7B", "q14": "Qwen2.5-Coder-14B"}
BUCK = [("1 token", 1, 1), ("2-3", 2, 3), ("4-6", 4, 6), ("7+", 7, 10**9)]


def load(path):
    out = {}
    for r in cr.load_jsonl(path):
        if r.get("status") == "ok": out[(r["sample_index"], r["condition_id"])] = (len(str(r["expected"]).split()), 1.0 if r["correct"] else 0.0)
    return out


def acc_table(cells):
    row = []
    for name, lo, hi in BUCK:
        v = [c for t, c in cells if lo <= t <= hi]
        row.append(f"{100*np.mean(v):5.1f} (n={len(v)})" if v else "   -   ")
    return row


md = ["# Post hoc: accuracy by expected output length (original prompt; A original)\n", "| model | source | " + " | ".join(b[0] for b in BUCK) + " | all |", "|---|---|" + "---|" * (len(BUCK) + 1)]
paired = ["\n# Post hoc: source effect (G2 minus real, mean of conditions (2,6) minus (1,5)) on samples whose real AND G2 outputs are both a single token\n", "| model | n | real | G2 | G2 - real [95%] | all-sample G2 - real (for reference) |", "|---|---|---|---|---|---|"]
for tag, label in TAGS.items():
    rr = load(f"rerun_{tag}_q4.jsonl"); g2 = load(f"g2_out/e1_{tag}.jsonl")
    if not rr or not g2: continue
    srcs = {"real": [v for (s, c), v in rr.items() if c in (1, 5)], "G1": [v for (s, c), v in rr.items() if c in (2, 6)], "G2": [v for (s, c), v in g2.items() if c in (2, 6)]}
    for name, cells in srcs.items():
        md.append(f"| {label} | {name} | " + " | ".join(acc_table(cells)) + f" | {100*np.mean([c for _, c in cells]):.1f} |")
    sids = sorted({s for s, _ in g2})
    rows, allrows = [], []
    for s in sids:
        if all((s, c) in rr for c in (1, 5)) and all((s, c) in g2 for c in (2, 6)):
            r, g = [rr[(s, 1)], rr[(s, 5)]], [g2[(s, 2)], g2[(s, 6)]]
            d = 100 * (np.mean([x[1] for x in g]) - np.mean([x[1] for x in r])); allrows.append(d)
            if r[0][0] == 1 and g[0][0] == 1: rows.append((d, 100 * np.mean([x[1] for x in r]), 100 * np.mean([x[1] for x in g])))
    if len(rows) >= 30:
        E = np.array(rows); Bt = cr.boot(E[:, :1], B=10000, seed=20261012)
        lo, hi = np.percentile(Bt[:, 0], [2.5, 97.5])
        paired.append(f"| {label} | {len(rows)} | {E[:,1].mean():.1f} | {E[:,2].mean():.1f} | {E[:,0].mean():+.2f} [{lo:+.2f}, {hi:+.2f}] | {np.mean(allrows):+.2f} |")
    else:
        paired.append(f"| {label} | {len(rows)} | too few | | | |")
txt = "\n".join(md + paired); open("g2_posthoc_outlen.md", "w").write(txt); print(txt)
