#!/usr/bin/env python3
"""g2_rank.py -- H4 of PREREG_G2.md. 15 models; real = condition 1, G1 = condition 2 (rank study files), G2 = condition 2 from g2_out.
Uses rank_analysis.analyse unchanged (Kendall tau-b, program-level bootstrap 10,000, split-half noise ceiling 1,000, seed 20261012).
Rule: ranking instability replicates if real-vs-G2 tau-b < 5th percentile of the real-vs-real split-half tau under BOTH prompts; depends on prompt if one; does not replicate if neither."""
import glob, json, os, re
import numpy as np
import rank_analysis as ra

norm = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())
TAGS = [("deepseekcoder67b", "ds"), ("starcoder27b", "sc2"), ("codellama7b", "cl"), ("qwen25coder7b", "q7"), ("qwen25coder14b", "q14"),
        ("codegemma7b", "cg7"), ("codellama13b", "cl13"), ("deepseekcoder13b", "ds13"), ("granitecode3b", "gr3"), ("granitecode8b", "gr8"),
        ("qwen25coder15b", "q15"), ("qwen25coder3b", "q3"), ("starcoder215b", "sc15"), ("starcoder23b", "sc3"), ("yicoder9b", "yi9")]
BASE = {"ds": "DeepSeek-Coder-6.7B", "sc2": "StarCoder2-7B", "cl": "CodeLlama-7B", "q7": "Qwen2.5-Coder-7B", "q14": "Qwen2.5-Coder-14B"}
models = {}   # tag -> dict(name, orig=(real/G1 file, G2 file), none=...)
for tag, name in BASE.items():
    n = {"ds": "ds", "sc2": "sc2", "cl": "cl", "q7": "q7", "q14": "q14"}[tag]
    models[tag] = dict(name=name, orig=(f"rerun_{n}_q4.jsonl", f"g2_out/e1_{tag}.jsonl"), none=(f"rerun_{n}none_q4.jsonl", f"g2_out/e2_{tag}.jsonl"))
for f in sorted(glob.glob("rank_out/*_orig.jsonl")):
    stem = os.path.basename(f)[:-len("_orig.jsonl")]; key = norm(stem); hit = [t for p, t in TAGS if key.startswith(p) and t not in BASE]
    if len(hit) != 1: print("unmatched rank_out file:", f, hit); continue
    t = hit[0]; models[t] = dict(name=stem.replace("_", "-"), orig=(f, f"g2_out/e3_{t}_orig.jsonl"), none=(f"rank_out/{stem}_none.jsonl", f"g2_out/e3_{t}_none.jsonl"))
assert len(models) == 15, f"expected 15 models, got {len(models)}: {sorted(models)}"
md, summary, material = ["# H4: ranking of 15 models on real, G1 and G2 programs (PREREG_G2.md)\n"], {}, {}
for pr in ("orig", "none"):
    names, dR, dG = [], {}, {}
    for t, m in models.items():
        a, b = m[pr]
        if not (os.path.exists(a) and os.path.exists(b)): print("missing", pr, t, a, b); continue
        names.append(m["name"]); dR[m["name"]] = ra.load_correct(a); dG[m["name"]] = ra.load_correct(b)
    common = None
    for n in names:
        ok = {s for (s, c) in dR[n] if c == 1 and (s, 2) in dR[n] and (s, 2) in dG[n]}
        common = ok if common is None else common & ok
    progs = sorted(common); N = len(progs)
    R = np.array([[dR[n][(s, 1)] for s in progs] for n in names]); S1 = np.array([[dR[n][(s, 2)] for s in progs] for n in names]); S2 = np.array([[dG[n][(s, 2)] for s in progs] for n in names])
    res2, aR, a2 = ra.analyse(R, S2, names, 10000, 1000, np.random.default_rng(20261012))
    res1, _, a1 = ra.analyse(R, S1, names, 10000, 1000, np.random.default_rng(20261012))
    iu, ju = np.triu_indices(len(names), 1)
    t12 = float(ra.tau_b(a1[:, None], a2[:, None], iu, ju)[0]); rk = [ra.average_ranks(x) for x in (aR, a1, a2)]
    order = np.argsort(rk[0])
    md += [f"\n## Prompt: {pr}  ({len(names)} models, {N} programs scored for every model under real, G1 and G2)\n", "| model | real % | G1 % | G2 % | rank real | rank G1 | rank G2 |", "|---|---|---|---|---|---|---|"]
    md += [f"| {names[i]} | {100*aR[i]:.1f} | {100*a1[i]:.1f} | {100*a2[i]:.1f} | {rk[0][i]:g} | {rk[1][i]:g} | {rk[2][i]:g} |" for i in order]
    md += [f"\n- real vs G2: tau-b = {res2['tau']:.3f} [95% CI {res2['tau_ci'][0]:.3f}, {res2['tau_ci'][1]:.3f}]; discordant pairs {100*res2['flip_share']:.1f}% of {res2['pairs']}; among {res2['decisive_pairs']} pairs resolved on real programs, {res2['decisive_flips']} flip",
           f"- split-half noise ceiling (real vs real): median {res2['split_half_real']['median']:.3f}, 5th percentile {res2['split_half_real']['p05']:.3f} -> **material (instability replicates): {res2['material']}**",
           f"- reference, real vs G1 on the same programs: tau-b = {res1['tau']:.3f} [{res1['tau_ci'][0]:.3f}, {res1['tau_ci'][1]:.3f}]; discordant {100*res1['flip_share']:.1f}%; material: {res1['material']}",
           f"- G1 vs G2 orderings: tau-b = {t12:.3f}", f"- split-half ceiling within G2 programs: median {res2['split_half_synth']['median']:.3f}, 5th percentile {res2['split_half_synth']['p05']:.3f}"]
    material[pr] = res2["material"]; summary[pr] = {"G2": res2, "G1": res1, "tau_G1_vs_G2": t12, "models": names, "N": N}
k = sum(material.values())
verdict = "replicates under both prompts" if k == 2 else ("depends on the prompt (" + ", ".join(p for p in material if material[p]) + " only)" if k == 1 else "does not replicate")
md.append(f"\n**H4: ranking instability {verdict}.**")
txt = "\n".join(md); open("g2_rank.md", "w").write(txt); json.dump(summary, open("g2_rank.json", "w"), indent=1); print(txt)
