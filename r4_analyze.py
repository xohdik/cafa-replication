#!/usr/bin/env python3
"""r4_analyze.py -- the analysis fixed in PREREG_R4.md. Official-input scores of conditions 1 and 5 from the confirmation files, extra-input scores from r4_out."""
import json, os
import numpy as np
import cafa_revision as cr

B, SEED = 10000, 20261012
MODELS = {"ds": ("DeepSeek-Coder-6.7B", "responses_deepseek_confirm.json"), "sc2": ("StarCoder2", "responses_starcoder2_confirm.json"),
          "cl": ("CodeLlama", "responses_codellama_confirm.json"), "q7": ("Qwen2.5-Coder-7B", "responses_qwen_confirm.json"),
          "q14": ("Qwen2.5-Coder-14B", "responses_qwen14b_confirm.json")}
COLS = ["I_single", "I_mean", "I_strict", "diff", "single1", "mean1", "strict1", "single5", "mean5", "strict5", "lucky1"]
r4 = {r["sample_index"]: len(r["extra"]) for r in json.load(open("r4_inputs.json"))["records"]}


def ci(v): return float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))


def main():
    out, md, rows = {}, ["# R4 results (PREREG_R4.md; points; unadjusted 95% program-level percentile intervals; Holm over five models for I|real(mean))\n"], []
    for tag, (label, resp) in MODELS.items():
        orig = cr.load_orig(resp); xs = [cr.rerun_scores(f"r4_out/x1_{tag}.jsonl"), cr.rerun_scores(f"r4_out/x2_{tag}.jsonl")]
        prog, dropped = [], 0
        for s, ne in sorted(r4.items()):
            if ne == 0: continue
            if (s, 1) not in orig or (s, 5) not in orig or any((s, c) not in xs[k] for k in range(ne) for c in (1, 5)): dropped += 1; continue
            v = {c: [orig[(s, c)] * 100] + [xs[k][(s, c)] * 100 for k in range(ne)] for c in (1, 5)}
            m1, m5 = np.mean(v[1]), np.mean(v[5]); s1, s5 = v[1][0], v[5][0]
            t1, t5 = 100.0 * (min(v[1]) == 100), 100.0 * (min(v[5]) == 100)
            prog.append([s5 - s1, m5 - m1, t5 - t1, (m5 - m1) - (s5 - s1), s1, m1, t1, s5, m5, t5, 100.0 * (s1 == 100 and t1 == 0)])
        if len(prog) < 50: md.append(f"- {label}: only {len(prog)} complete programs, skipped"); continue
        X = np.array(prog); Bt = cr.boot(X, B=B, seed=SEED); est = X.mean(0)
        res = {c: {"est": float(est[j]), "lo": ci(Bt[:, j])[0], "hi": ci(Bt[:, j])[1], "p": float(cr.pval(Bt[:, j]))} for j, c in enumerate(COLS)}
        rows.append((tag, label, len(prog), dropped, res)); out[tag] = {"n": len(prog), "dropped": dropped, **res}
    if rows:
        hp = cr.holm(np.array([r[4]["I_mean"]["p"] for r in rows]))
        f = lambda r: f"{r['est']:+.2f} [{r['lo']:+.2f}, {r['hi']:+.2f}]"
        md += ["| model | programs (dropped) | acc. cond. 1: single / mean / strict | I given real: single | I given real: mean (primary) | I given real: strict | mean - single | Holm p (mean) | single correct but not all (share) |", "|---|---|---|---|---|---|---|---|---|"]
        neg, size_ok = 0, 0
        for (tag, label, n, d, r), a in zip(rows, hp):
            md.append(f"| {label} | {n} ({d}) | {r['single1']['est']:.1f} / {r['mean1']['est']:.1f} / {r['strict1']['est']:.1f} | {f(r['I_single'])} | {f(r['I_mean'])} | {f(r['I_strict'])} | {f(r['diff'])} | {a:.3f} | {r['lucky1']['est']:.1f}% |")
            neg += r["I_mean"]["est"] < 0; size_ok += abs(r["diff"]["est"]) <= 1.5; out[tag]["I_mean_holm"] = float(a)
        direction, size = neg == len(rows) and len(rows) == 5, size_ok == len(rows) and len(rows) == 5
        md.append(f"\n**Direction (I|real(mean) negative in all five models): {'holds' if direction else 'does not hold'} ({neg} of {len(rows)}). Size (|mean - single| <= 1.5 points in every model): {'holds' if size else 'does not hold'} ({size_ok} of {len(rows)}).**")
        md.append("Reading fixed in PREREG_R4.md: " + ("the identifier effect on real code does not depend on the single-input oracle." if direction and size else "the sign holds; the multi-input estimate is reported as the estimate." if direction else "for each model with a non-negative estimate the identifier effect on real code is reported as input-dependent."))
    open("r4_results.md", "w").write("\n".join(md)); json.dump(out, open("r4_results.json", "w"), indent=1); print("\n".join(md))


if __name__ == "__main__":
    main()
