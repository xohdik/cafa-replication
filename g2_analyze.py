#!/usr/bin/env python3
"""g2_analyze.py -- the analysis fixed in PREREG_G2.md (E1, E2, H1 to H3; H4 is a separate script).
Uses the paper's own estimators (cafa_revision.term_weights, simple_weights, boot, pval, holm, ci), 10,000 program-level resamples, seed 20261012.
Real-program cells (conditions 1, 3, 5, 7) and G1 cells (2, 4, 6, 8) come from the confirmation run; G2 cells from g2_out. Scores in points (x100).
Pairing: only samples that have every cell needed by a comparison are used, and the sample count is printed."""
import json, os, sys
import numpy as np
import cafa_revision as cr

B, SEED = 10000, 20261012
MODELS = {  # tag: (label, confirmation responses, no-demonstration rerun of conditions 1,2,5,6, orig-prompt rerun for the identity check)
    "ds": ("DeepSeek-Coder-6.7B", "responses_deepseek_confirm.json", "rerun_dsnone_q4.jsonl", "rerun_ds_q4.jsonl"),
    "sc2": ("StarCoder2", "responses_starcoder2_confirm.json", "rerun_sc2none_q4.jsonl", "rerun_sc2_q4.jsonl"),
    "cl": ("CodeLlama", "responses_codellama_confirm.json", "rerun_clnone_q4.jsonl", "rerun_cl_q4.jsonl"),
    "q7": ("Qwen2.5-Coder-7B", "responses_qwen_confirm.json", "rerun_q7none_q4.jsonl", "rerun_q7_q4.jsonl"),
    "q14": ("Qwen2.5-Coder-14B", "responses_qwen14b_confirm.json", "rerun_q14none_q4.jsonl", "rerun_q14_q4.jsonl"),
}
TERMS = cr.TERMS; W7 = cr.W7; SW = cr.simple_weights(); SIMPLE = list(SW)
iS, iIS = TERMS.index("S"), TERMS.index("IS"); sOrig = SIMPLE.index("S|orig-names")


def stats(Bt, est):
    return {"est": float(est), "lo": float(np.percentile(Bt, 2.5)), "hi": float(np.percentile(Bt, 97.5)), "p": float(cr.pval(Bt))}


def rows_for(sample_ids, srcs):
    """srcs: list of (dict, cid) in column order -> (kept sample list, n x k array of scores x100)."""
    keep = [s for s in sample_ids if all((s, c) in d for d, c in srcs)]
    return keep, np.array([[d[(s, c)] * 100 for d, c in srcs] for s in keep], float)


def main():
    out = {"models": {}}; md = []
    # --- data
    data = {}
    for tag, (label, resp, nonef, origf) in MODELS.items():
        if not os.path.exists(resp):
            print("missing", resp); continue
        orig = cr.load_orig(resp)
        g2o = cr.rerun_scores(f"g2_out/e1_{tag}.jsonl"); g2n = cr.rerun_scores(f"g2_out/e2_{tag}.jsonl")
        non = cr.rerun_scores(nonef)
        ident = None
        if os.path.exists(origf):
            rr = cr.rerun_scores(origf); both = [k for k in rr if k in orig and k[1] in (1, 2, 5, 6)]
            ident = (sum(abs(rr[k] - orig[k]) < 1e-9 for k in both) / max(1, len(both)), len(both))
        data[tag] = dict(label=label, orig=orig, g2o=g2o, g2n=g2n, non=non, ident=ident)
    # --- E1: eight-condition analysis with real cells + G2 cells; G1 from the same real cells for pairing
    h1, h2rows, h3rows = {}, [], []
    md.append("# G2 results (PREREG_G2.md; scores in points, 95% percentile intervals unadjusted, Holm within model over the seven terms)\n")
    for tag, d in data.items():
        orig, g2o = d["orig"], d["g2o"]
        sids = sorted({s for s, _ in orig})
        comb = {}
        for (s, c), v in orig.items():
            if c in (1, 3, 5, 7): comb[(s, c)] = v
        for (s, c), v in g2o.items():
            if c in (2, 4, 6, 8): comb[(s, c)] = v
        srcs2 = [(comb, c) for c in range(1, 9)]; srcs1 = [(orig, c) for c in range(1, 9)]
        keep = [s for s in sids if all((s, c) in comb for c in range(1, 9)) and all((s, c) in orig for c in range(1, 9))]
        if not keep:
            md.append(f"## {d['label']}: no complete samples yet\n"); continue
        X2 = np.array([[comb[(s, c)] * 100 for c in range(1, 9)] for s in keep]); X1 = np.array([[orig[(s, c)] * 100 for c in range(1, 9)] for s in keep])
        E2, S2, E1, S1 = X2 @ W7, X2 @ np.stack([SW[k] for k in SIMPLE], 1), X1 @ W7, X1 @ np.stack([SW[k] for k in SIMPLE], 1)
        D = np.stack([S2[:, sOrig] - S1[:, sOrig], E2[:, iIS] - E1[:, iIS], E2[:, iS] - E1[:, iS]], 1)
        Big = np.hstack([E2, S2, E1, S1, D]); Bt = cr.boot(Big, B=B, seed=SEED); est = Big.mean(0)
        j = 0
        g2 = {t: stats(Bt[:, j + i], est[j + i]) for i, t in enumerate(TERMS)}; j += 7
        g2s = {t: stats(Bt[:, j + i], est[j + i]) for i, t in enumerate(SIMPLE)}; j += 4
        g1 = {t: stats(Bt[:, j + i], est[j + i]) for i, t in enumerate(TERMS)}; j += 7
        g1s = {t: stats(Bt[:, j + i], est[j + i]) for i, t in enumerate(SIMPLE)}; j += 4
        dif = {k: stats(Bt[:, j + i], est[j + i]) for i, k in enumerate(["S|orig-names", "IS", "S"])}
        hp = cr.holm(np.array([g2[t]["p"] for t in TERMS]))
        for t, a in zip(TERMS, hp): g2[t]["holm"] = float(a)
        hp1 = cr.holm(np.array([g1[t]["p"] for t in TERMS]))
        for t, a in zip(TERMS, hp1): g1[t]["holm"] = float(a)
        cells = {"real": [float(x) for x in X2[:, [0, 2, 4, 6]].mean(0)], "G1": [float(x) for x in X1[:, [1, 3, 5, 7]].mean(0)], "G2": [float(x) for x in X2[:, [1, 3, 5, 7]].mean(0)]}
        out["models"][tag] = {"label": d["label"], "n": len(keep), "G2_terms": g2, "G2_simple": g2s, "G1_terms": g1, "G1_simple": g1s, "diff_G2_minus_G1": dif, "cell_means": cells, "identity_check": d["ident"]}
        md.append(f"## {d['label']}  (n = {len(keep)} programs with all eight cells)\n")
        if d["ident"]: md.append(f"Identity check: {d['ident'][0]:.3f} of {d['ident'][1]} shared cells identical between the confirmation file and the rerun.\n")
        md.append("Cell means (points), conditions in order 1,3,5,7 for real and 2,4,6,8 for generators: real " + ", ".join(f"{x:.1f}" for x in cells["real"]) + " | G1 " + ", ".join(f"{x:.1f}" for x in cells["G1"]) + " | G2 " + ", ".join(f"{x:.1f}" for x in cells["G2"]) + "\n")
        md.append("| term | G1 est | G1 Holm p | G2 est | G2 95% interval | G2 p | G2 Holm p |\n|---|---|---|---|---|---|---|")
        for t in TERMS:
            md.append(f"| {t} | {g1[t]['est']:+.2f} | {g1[t]['holm']:.3f} | {g2[t]['est']:+.2f} | [{g2[t]['lo']:+.2f}, {g2[t]['hi']:+.2f}] | {g2[t]['p']:.4f} | {g2[t]['holm']:.3f} |")
        md.append("\n| simple effect | G1 | G2 |\n|---|---|---|")
        for t in SIMPLE: md.append(f"| {t.replace('|', ' / ')} | {g1s[t]['est']:+.2f} [{g1s[t]['lo']:+.2f}, {g1s[t]['hi']:+.2f}] | {g2s[t]['est']:+.2f} [{g2s[t]['lo']:+.2f}, {g2s[t]['hi']:+.2f}] |")
        md.append("")
        h1[tag] = g2["IS"]
        for k in ("S|orig-names", "IS"): h2rows.append((tag, k, dif[k]))
    # --- H1
    md.append("# H1 (direction replicates: DeepSeek-Coder and StarCoder2, identifiers x source under G2 positive with Holm p < 0.05)")
    ok1 = []
    for tag in ("ds", "sc2"):
        if tag in h1:
            r = h1[tag]; sat = r["est"] > 0 and out["models"][tag]["G2_terms"]["IS"]["holm"] < 0.05; ok1.append(sat)
            md.append(f"- {MODELS[tag][0]}: IS = {r['est']:+.2f} [{r['lo']:+.2f}, {r['hi']:+.2f}], Holm p = {out['models'][tag]['G2_terms']['IS']['holm']:.3f} -> {'satisfied' if sat else 'not satisfied'}")
    if ok1: md.append(f"**H1: {'replicated' if all(ok1) and len(ok1)==2 else 'partly replicated' if any(ok1) else 'not replicated'}**\n")
    # --- H2
    md.append("# H2 (generator dependence: G2 minus G1, paired by program; Holm over 5 models x 2 quantities; dependent if |difference| >= 3 points and Holm p < 0.05)")
    if h2rows:
        hp = cr.holm(np.array([r[2]["p"] for r in h2rows]))
        md.append("| model | quantity | G2 - G1 | 95% interval | p | Holm p | generator-dependent |\n|---|---|---|---|---|---|---|")
        for (tag, k, r), a in zip(h2rows, hp):
            dep = abs(r["est"]) >= 3 and a < 0.05
            out["models"][tag].setdefault("H2", {})[k] = {**r, "holm": float(a), "dependent": bool(dep)}
            md.append(f"| {MODELS[tag][0]} | {k.replace('|', ' / ')} | {r['est']:+.2f} | [{r['lo']:+.2f}, {r['hi']:+.2f}] | {r['p']:.4f} | {a:.3f} | {'YES' if dep else 'no'} |")
    md.append("")
    # --- H3 / E2
    md.append("# H3 (prompt dependence). Per model, with statement order original: S(prompt) = mean(c2,c6) - mean(c1,c5); SP = S(no demonstration) - S(original prompt); IS(prompt) = (c6-c2) - (c5-c1); ISP = IS(none) - IS(orig).")
    rows = []
    for tag, d in data.items():
        orig, non, g2o, g2n = d["orig"], d["non"], d["g2o"], d["g2n"]
        sids = sorted({s for s, _ in orig})
        srcs = [(orig, 1), (orig, 5), (orig, 2), (orig, 6), (g2o, 2), (g2o, 6), (non, 1), (non, 5), (non, 2), (non, 6), (g2n, 2), (g2n, 6)]
        keep, X = rows_for(sids, srcs)
        if len(keep) < 50: md.append(f"- {d['label']}: only {len(keep)} complete programs, skipped"); continue
        r1o, r5o, g1_2o, g1_6o, g2_2o, g2_6o, r1n, r5n, g1_2n, g1_6n, g2_2n, g2_6n = X.T
        def S(a2, a6, r1, r5): return (a2 + a6) / 2 - (r1 + r5) / 2
        def IS(a2, a6, r1, r5): return (a6 - a2) - (r5 - r1)
        cols = {}
        for g, (a2o, a6o, a2n, a6n) in {"G1": (g1_2o, g1_6o, g1_2n, g1_6n), "G2": (g2_2o, g2_6o, g2_2n, g2_6n)}.items():
            cols[g + ".S_orig"] = S(a2o, a6o, r1o, r5o); cols[g + ".S_none"] = S(a2n, a6n, r1n, r5n)
            cols[g + ".SP"] = cols[g + ".S_none"] - cols[g + ".S_orig"]
            cols[g + ".IS_orig"] = IS(a2o, a6o, r1o, r5o); cols[g + ".IS_none"] = IS(a2n, a6n, r1n, r5n); cols[g + ".ISP"] = cols[g + ".IS_none"] - cols[g + ".IS_orig"]
        names = list(cols); Big = np.stack([cols[k] for k in names], 1); Bt = cr.boot(Big, B=B, seed=SEED); est = Big.mean(0)
        res = {k: stats(Bt[:, i], est[i]) for i, k in enumerate(names)}
        rows.append((tag, len(keep), res))
    if rows:
        hp = cr.holm(np.array([r[2]["G2.SP"]["p"] for r in rows]))
        md.append("| model | n | G1 SP | G2 SP [95%] | G2 SP Holm p (over models) | same sign | G1 ISP | G2 ISP [95%] |\n|---|---|---|---|---|---|---|---|")
        sat = 0
        for (tag, n, res), a in zip(rows, hp):
            same = np.sign(res["G1.SP"]["est"]) == np.sign(res["G2.SP"]["est"]); ok = same and a < 0.05; sat += ok
            out["models"][tag]["E2"] = {"n": n, **res, "SP_holm": float(a), "H3_model_satisfied": bool(ok)}
            md.append(f"| {MODELS[tag][0]} | {n} | {res['G1.SP']['est']:+.2f} | {res['G2.SP']['est']:+.2f} [{res['G2.SP']['lo']:+.2f}, {res['G2.SP']['hi']:+.2f}] | {a:.3f} | {'yes' if same else 'no'} | {res['G1.ISP']['est']:+.2f} | {res['G2.ISP']['est']:+.2f} [{res['G2.ISP']['lo']:+.2f}, {res['G2.ISP']['hi']:+.2f}] |")
        md.append(f"\n**H3: {sat} of {len(rows)} models satisfy it (needs at least 4 of 5): {'holds' if sat >= 4 and len(rows) == 5 else 'does not hold'}**")
        md.append("\n(Holm family for the H3 p-values is the five models' G2 SP values; PREREG_G2.md did not name it, so this choice is logged in DEVIATIONS.md.)")
    open("g2_results.md", "w").write("\n".join(md)); json.dump(out, open("g2_results.json", "w"), indent=1)
    print("\n".join(md))


if __name__ == "__main__":
    main()
