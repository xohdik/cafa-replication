#!/usr/bin/env python3
"""
demo_sensitivity.py -- is the C2 (synthetic + original names) failure caused by the one-shot DEMONSTRATION in the prompt?
Reruns conditions C1, C2, C5, C6 (identifiers x syntheticity; AST is null and left out) under three demonstrations:
  v0 = the harness's own demo (n*2)  -- must reproduce the existing run (sanity check)
  v1 = a = int(input()); print(a + 7)
  v2 = s = input(); print(s[::-1])
Reports accuracy and the four simple effects per demonstration. Resumable: finished variants are kept in --out.
Usage (cafa env, from capa/):
  CUDA_VISIBLE_DEVICES=0 python3 demo_sensitivity.py --manifest manifest_v2.json \
      --gguf ./models/deepseek-coder-6.7b-base.Q4_K_M.gguf --out demo_deepseek.json
"""
import argparse
import json
import os

import numpy as np

import scoring_harness as H

VARIANTS = {
    "v0_n_times_2": None,  # harness default
    "v1_a_plus_7": ("a = int(input())\nprint(a + 7)", "5", "12"),
    "v2_reverse_string": ("s = input()\nprint(s[::-1])", "abc", "cba"),
}
BASE = H.PROMPT_TEMPLATE


def template(v):
    if v is None:
        return BASE
    code, stdin, out = v
    return ("# Predict the exact standard output of each Python program.\n\n# Program:\n" + code +
            "\n# Input:\n" + stdin + "\n# Output:\n" + out + "\n\n# Program:\n{code}\n# Input:\n{stdin}\n# Output:\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--gguf", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--conds", default="1,2,5,6")
    ap.add_argument("--n-ctx", type=int, default=8192)
    ap.add_argument("--boot", type=int, default=10000)
    a = ap.parse_args()
    conds = [int(c) for c in a.conds.split(",")]
    man = json.load(open(a.manifest))
    res = json.load(open(a.out)) if os.path.exists(a.out) else {}
    todo = [k for k in VARIANTS if k not in res]
    if todo:
        from llama_cpp import Llama
        llm = Llama(model_path=a.gguf, n_gpu_layers=-1, n_ctx=a.n_ctx, verbose=False)
        for k in todo:
            H.PROMPT_TEMPLATE = template(VARIANTS[k])
            r = {}
            for s in man["samples"]:
                pid = str(s["sample_index"])
                for built in s["conditions"]:
                    cid = built["condition_id"]
                    if cid not in conds or built.get("status") != "ok" or not built.get("source_code"):
                        continue
                    sc = built.get("stdin_cases") or s.get("stdin_cases")
                    if not sc:
                        continue
                    exp, err = H.ground_truth(built["source_code"], sc[0])
                    if err is not None:
                        continue
                    o = H.score_one(llm, built["source_code"], sc[0], exp, n_ctx=a.n_ctx)
                    if o["status"] == "ok":
                        r.setdefault(pid, {})[str(cid)] = 1.0 if o["correct"] else 0.0
            res[k] = r
            json.dump(res, open(a.out, "w"))
            print(f"finished {k}: {len(r)} programs", flush=True)
    H.PROMPT_TEMPLATE = BASE
    rng = np.random.default_rng(0)
    for k, r in res.items():
        pids = [p for p in r if all(str(c) in r[p] for c in conds)]
        P = np.array([[r[p][str(c)] for c in conds] for p in pids])
        col = {c: i for i, c in enumerate(conds)}
        idx = rng.integers(0, len(pids), (a.boot, len(pids)))

        def line(name, v):
            b = v[idx].mean(1)
            lo, hi = np.percentile(b, [2.5, 97.5])
            print(f"  {name:<36}{v.mean():>+8.3f}   [{lo:+.3f}, {hi:+.3f}]")
        print(f"\n== {k}  (programs={len(pids)}) ==")
        print("  accuracy: " + "  ".join(f"C{c}={P[:, col[c]].mean():.3f}" for c in conds))
        if all(c in col for c in (1, 2, 5, 6)):
            line("synthetic | original identifiers", P[:, col[2]] - P[:, col[1]])
            line("synthetic | obfuscated identifiers", P[:, col[6]] - P[:, col[5]])
            line("identifiers | real code", P[:, col[5]] - P[:, col[1]])
            line("identifiers | synthetic code", P[:, col[6]] - P[:, col[2]])


main()
