#!/usr/bin/env python3
"""
name_ablation.py -- WHICH generator names drive the C2 penalty (DeepSeek) / bump (Qwen)?
Takes each program's C2 (synthetic, original names) and renames only ONE group of its identifiers, using the same new names the
orchestrator's obfuscate_identifiers() assigns, then scores it with the harness prompt:
  none = C2 as is   all = every identifier renamed (should reproduce C6)   n = only `n`   result = only `result`
  loop = only i_0, i_1..   pad = only the dead _pad0.._padK assignments   other = any remaining identifiers
Every renamed program is executed and must print the same output as C2, otherwise it is dropped (and counted).
Usage (cafa env, from capa/):
  CUDA_VISIBLE_DEVICES=0 python3 name_ablation.py --manifest manifest_v2.json \
      --gguf ./models/deepseek-coder-6.7b-base.Q4_K_M.gguf --out ablate_deepseek.json
Resumable: finished variants are kept in --out.
"""
import argparse
import json
import os
import re
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "perturbations"))
import scoring_harness as H
from identifier_rename import obfuscate_identifiers

GROUPS = ["none", "n", "result", "loop", "pad", "other", "all"]


def group_of(name):
    if name == "n":
        return "n"
    if name == "result":
        return "result"
    if re.fullmatch(r"i_\d+", name):
        return "loop"
    if re.fullmatch(r"_pad\d+", name):
        return "pad"
    return "other"


def rename(code, mapping, which):
    sel = {o: nw for o, nw in mapping.items() if which == "all" or group_of(o) == which}
    if which == "none" or not sel:
        return code if which == "none" else None
    pat = re.compile(r"\b(" + "|".join(re.escape(k) for k in sorted(sel, key=len, reverse=True)) + r")\b")
    return pat.sub(lambda m: sel[m.group(1)], code)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--gguf", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--n-ctx", type=int, default=8192)
    ap.add_argument("--boot", type=int, default=10000)
    a = ap.parse_args()
    man = json.load(open(a.manifest))
    res = json.load(open(a.out)) if os.path.exists(a.out) else {"scores": {}, "dropped": {}, "n_groups": {}}
    todo = [g for g in GROUPS if g not in res["scores"]]
    if todo:
        from llama_cpp import Llama
        llm = Llama(model_path=a.gguf, n_gpu_layers=-1, n_ctx=a.n_ctx, verbose=False)
        for g in todo:
            sc, dropped, present = {}, 0, 0
            for s in man["samples"]:
                pid = str(s["sample_index"])
                built = next((c for c in s["conditions"] if c["condition_id"] == 2), None)
                if not built or built.get("status") != "ok" or not built.get("source_code"):
                    continue
                code = built["source_code"]
                stdin = (built.get("stdin_cases") or s.get("stdin_cases"))[0]
                exp, err = H.ground_truth(code, stdin)
                if err is not None:
                    continue
                try:
                    _, mapping = obfuscate_identifiers(code)
                except Exception:
                    continue
                new = rename(code, mapping, g)
                if new is None:        # this program has no identifiers in that group
                    continue
                present += 1
                if new != code:
                    out2, err2 = H.ground_truth(new, stdin)
                    if err2 is not None or H.normalize(out2) != H.normalize(exp):
                        dropped += 1
                        continue
                o = H.score_one(llm, new, stdin, exp, n_ctx=a.n_ctx)
                if o["status"] == "ok":
                    sc[pid] = 1.0 if o["correct"] else 0.0
            res["scores"][g], res["dropped"][g], res["n_groups"][g] = sc, dropped, present
            json.dump(res, open(a.out, "w"))
            print(f"finished {g}: scored {len(sc)} of {present} programs having that group, dropped {dropped}", flush=True)
    base = res["scores"]["none"]
    rng = np.random.default_rng(0)
    print(f"\n{'variant':<8}{'programs':>9}{'accuracy':>10}   {'change vs none (same programs)':<34}")
    for g in GROUPS:
        sc = res["scores"][g]
        pids = [p for p in sc if p in base]
        if not pids:
            print(f"{g:<8}{0:>9}")
            continue
        v = np.array([sc[p] - base[p] for p in pids])
        idx = rng.integers(0, len(pids), (a.boot, len(pids)))
        lo, hi = np.percentile(v[idx].mean(1), [2.5, 97.5])
        acc = np.mean([sc[p] for p in pids])
        print(f"{g:<8}{len(pids):>9}{acc:>10.3f}   {v.mean():>+7.3f} [{lo:+.3f}, {hi:+.3f}]   (none on these = {np.mean([base[p] for p in pids]):.3f})")


main()
