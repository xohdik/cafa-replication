#!/usr/bin/env python3
"""g2_posthoc_strata.py -- POST HOC (not pre-registered). Re-estimates S, IS, SP, ISP for G1 and G2 inside strata where the floor does not apply.
Stratum A: expected output of the real program AND of its G2 counterpart is a single token. Stratum B: G2 counterpart's expected output is a single token.
Same estimators, 10,000 resamples, seed 20261012, unadjusted 95% percentile intervals; scores in points. Strata are defined from expected outputs only (not from model scores)."""
import numpy as np
import cafa_revision as cr
sys_models = {"ds": ("DeepSeek-Coder-6.7B", "responses_deepseek_confirm.json", "rerun_dsnone_q4.jsonl"),
              "sc2": ("StarCoder2", "responses_starcoder2_confirm.json", "rerun_sc2none_q4.jsonl"),
              "cl": ("CodeLlama", "responses_codellama_confirm.json", "rerun_clnone_q4.jsonl"),
              "q7": ("Qwen2.5-Coder-7B", "responses_qwen_confirm.json", "rerun_q7none_q4.jsonl"),
              "q14": ("Qwen2.5-Coder-14B", "responses_qwen14b_confirm.json", "rerun_q14none_q4.jsonl")}
B, SEED = 10000, 20261012

def ntok(path, cid):
    d = {}
    for r in cr.load_jsonl(path):
        if r.get("status") == "ok" and r["condition_id"] == cid: d[r["sample_index"]] = len(str(r["expected"]).split())
    return d
tr = ntok("rerun_cl_q4.jsonl", 1); tg = ntok("g2_out/e1_cl.jsonl", 2)
S = lambda a2, a6, r1, r5: (a2 + a6) / 2 - (r1 + r5) / 2
IS = lambda a2, a6, r1, r5: (a6 - a2) - (r5 - r1)
def est(x):
    Bt = cr.boot(x[:, None], B=B, seed=SEED)[:, 0]; return f"{x.mean():+.2f} [{np.percentile(Bt,2.5):+.2f}, {np.percentile(Bt,97.5):+.2f}]"
md = ["# Post hoc: S, IS, SP, ISP inside output-length strata (points; unadjusted 95% intervals)\n"]
for sname, ok in (("A: real and G2 outputs both a single token", lambda s: tr.get(s) == 1 and tg.get(s) == 1),
                  ("B: G2 output a single token", lambda s: tg.get(s) == 1)):
    md += [f"\n## Stratum {sname}\n", "| model | n | G2 cell means (c2,c4,c6,c8) | gen | S (orig prompt) | IS (orig) | SP | ISP |", "|---|---|---|---|---|---|---|---|"]
    for tag, (label, resp, nonef) in sys_models.items():
        orig = cr.load_orig(resp); g2o = cr.rerun_scores(f"g2_out/e1_{tag}.jsonl"); g2n = cr.rerun_scores(f"g2_out/e2_{tag}.jsonl"); non = cr.rerun_scores(nonef)
        need = [(orig, 1), (orig, 5), (orig, 2), (orig, 6), (g2o, 2), (g2o, 6), (non, 1), (non, 5), (non, 2), (non, 6), (g2n, 2), (g2n, 6)]
        ids = [s for s in sorted({s for s, _ in orig}) if ok(s) and all((s, c) in d for d, c in need) and (s, 4) in g2o and (s, 8) in g2o]
        if len(ids) < 30: md.append(f"| {label} | {len(ids)} | too few | | | | | |"); continue
        X = np.array([[d[(s, c)] * 100 for d, c in need] for s in ids]); r1o, r5o, a2, a6, b2, b6, r1n, r5n, a2n, a6n, b2n, b6n = X.T
        cells = [np.mean([g2o[(s, c)] * 100 for s in ids]) for c in (2, 4, 6, 8)]
        for g, (x2, x6, x2n, x6n) in (("G1", (a2, a6, a2n, a6n)), ("G2", (b2, b6, b2n, b6n))):
            so, sn = S(x2, x6, r1o, r5o), S(x2n, x6n, r1n, r5n); io, inn = IS(x2, x6, r1o, r5o), IS(x2n, x6n, r1n, r5n)
            md.append(f"| {label} | {len(ids)} | " + (" / ".join(f"{c:.1f}" for c in cells) if g == "G2" else "") + f" | {g} | {est(so)} | {est(io)} | {est(sn - so)} | {est(inn - io)} |")
txt = "\n".join(md); open("g2_posthoc_strata.md", "w").write(txt); print(txt)
