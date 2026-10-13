#!/usr/bin/env python3
"""
name_ablation_readable.py -- is the DeepSeek C2 penalty about the SPECIFIC generator names (n, result) or about any renaming?
Renames `n` -> `count` and/or `result` -> `total` in each program's C2 (plain readable names, NOT obfuscated-looking ones):
  none = C2 as is   n = only n->count   result = only result->total   both = n->count and result->total
In name_ablation.py, renaming n or result to obfuscated-style tokens (v_xxxx) recovered the whole penalty. If readable renames
recover it too, the trigger is the specific token pair (n, result), not the obfuscated look.
Every renamed program is executed and must print the same output as C2, otherwise it is dropped (and counted).
Usage (cafa env, from capa/):
  CUDA_VISIBLE_DEVICES=0 python3 name_ablation_readable.py --manifest manifest_v2.json \
      --gguf ./models/deepseek-coder-6.7b-base.Q4_K_M.gguf --out readable_deepseek.json
Resumable: finished variants are kept in --out.
"""
import argparse
import json
import os
import re
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scoring_harness as H

GROUPS = ["none", "n", "result", "both"]
READABLE = {"n": "count", "result": "total"}


def rename(code, which):
    if which == "none":
        return code
    sel = {k: v for k, v in READABLE.items() if which == "both" or which == k}
    if any(re.search(r"\b" + v + r"\b", code) for v in sel.values()):
        return None                       # new name already used in this program: skip rather than collide
    if not all(re.search(r"\b" + k + r"\b", code) for k in sel):
        return None                       # program lacks that identifier
    pat = re.compile(r"\b(" + "|".join(sel) + r")\b")
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
                new = rename(code, g)
                if new is None:
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
            print(f"finished {g}: scored {len(sc)} of {present} eligible programs, dropped {dropped}", flush=True)
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
