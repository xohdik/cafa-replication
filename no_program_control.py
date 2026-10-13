#!/usr/bin/env python3
"""
no_program_control.py -- how much of the measured accuracy survives WITHOUT the right program?

For every program, for target conditions C1 (real) and C2 (synthetic), the model is asked for the
output of the TRUE program's input, scored against the TRUE program's output, under three prompts:
  true  : the actual program                    (replicates the main run; sanity check)
  blank : the program replaced by `pass`        (input-only guessing)
  other : the program replaced by a DIFFERENT program of the same kind (same condition, other
          sample); the input and the expected output stay those of the target
Same prompt template, token limit, stop strings and scoring as the main run: score_one() is imported
from scoring_harness.py.

Also reported, with no model: the accuracy of always answering the most common expected output
(an optimistic constant-guesser bound, since the mode is taken from the same data).

Interpretation: if blank/other accuracy is close to true accuracy, the benchmark score is largely
input-pattern guessing, not program comprehension. Read the paired gaps, not the raw levels.

Usage:
  python3 no_program_control.py --manifest manifest.json --gguf ./models/<model>.gguf --out npc_deepseek.json --limit 20   # smoke test
  python3 no_program_control.py --manifest manifest.json --gguf ./models/<model>.gguf --out npc_deepseek.json --resume
Run from the capa directory (imports scoring_harness.py and ast_shuffle.py).
"""
import argparse
import collections
import json
import os
import random
import sys
import time
import warnings

import numpy as np

warnings.filterwarnings("ignore", category=SyntaxWarning)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "perturbations"))
from scoring_harness import ground_truth, normalize, score_one  # noqa: E402

TARGETS = (1, 2)                       # C1 real, C2 synthetic
LABEL = {1: "real (C1)", 2: "synthetic (C2)"}
VARIANTS = ("true", "blank", "other")


def build_pool(manifest):
    pool = []
    for s in manifest["samples"]:
        conds = {c["condition_id"]: c for c in s["conditions"]}
        item, ok = {"sid": s["sample_index"]}, True
        for t in TARGETS:
            c = conds.get(t)
            if not c or c.get("status") != "ok" or not c.get("source_code"):
                ok = False
                break
            cases = c.get("stdin_cases") or s.get("stdin_cases")
            if not cases:
                ok = False
                break
            exp, err = ground_truth(c["source_code"], cases[0])
            if err is not None:
                ok = False
                break
            item[t] = {"code": c["source_code"], "stdin": cases[0], "expected": exp}
        if ok:
            pool.append(item)
    return pool


def run_control(pool, llm, out_path, seed=0, n_ctx=8192, resume=False, save_every=20):
    n = len(pool)
    shift = random.Random(seed).randint(1, n - 1)          # fixed derangement: other = pool[(i+shift) % n]
    results = {}
    if resume and os.path.exists(out_path):
        results = json.load(open(out_path)).get("results", {})
        print(f"resumed: {len(results)} programs already done", flush=True)
    t0, since = time.time(), 0
    for i, item in enumerate(pool):
        sid = str(item["sid"])
        if sid in results:
            continue
        other = pool[(i + shift) % n]
        row = {}
        for t in TARGETS:
            tgt = item[t]
            variants = {"true": tgt["code"], "blank": "pass", "other": other[t]["code"]}
            row[str(t)] = {}
            for v, code in variants.items():
                res = score_one(llm, code, tgt["stdin"], tgt["expected"], n_ctx=n_ctx)
                row[str(t)][v] = (1.0 if res["correct"] else 0.0) if res["status"] == "ok" else None
        results[sid] = row
        since += 1
        if since >= save_every:
            json.dump({"results": results}, open(out_path, "w"))
            since = 0
            print(f"  ...{len(results)}/{n} programs ({time.time() - t0:.0f}s)", flush=True)
    json.dump({"results": results, "seed": seed, "shift": shift, "n_pool": n}, open(out_path, "w"))
    return results


def boot(v, rng, B=10000):
    idx = rng.integers(0, len(v), (B, len(v)))
    b = v[idx].mean(1)
    return v.mean(), *np.percentile(b, [2.5, 97.5])


def summarize(results, pool, label):
    rng = np.random.default_rng(0)
    print("\n" + "=" * 84)
    print(label, f"  programs scored: {len(results)}")
    print("=" * 84)
    for t in TARGETS:
        arr = {v: [] for v in VARIANTS}
        for item in pool:
            r = results.get(str(item["sid"]))
            if r is None or any(r[str(t)][v] is None for v in VARIANTS):
                continue
            for v in VARIANTS:
                arr[v].append(r[str(t)][v])
        arr = {v: np.array(a) for v, a in arr.items()}
        n = len(arr["true"])
        if n < 5:
            print(f"{LABEL[t]}: too few complete programs ({n})")
            continue
        print(f"\n{LABEL[t]}   n = {n}")
        for v in VARIANTS:
            m, lo, hi = boot(arr[v], rng)
            print(f"  accuracy, {v:<5} program   {m:.3f}  [{lo:.3f}, {hi:.3f}]")
        for v in ("blank", "other"):
            m, lo, hi = boot(arr["true"] - arr[v], rng)
            print(f"  gap true - {v:<5}          {m:+.3f}  [{lo:+.3f}, {hi:+.3f}]")
        exp = [normalize(it[t]["expected"]) for it in pool]
        mode, cnt = collections.Counter(exp).most_common(1)[0]
        print(f"  constant-guess bound (always {mode[:20]!r}): {cnt / len(exp):.3f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--gguf", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--limit", type=int, default=0, help="only the first N programs (smoke test)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--n-ctx", type=int, default=8192)
    ap.add_argument("--resume", action="store_true")
    a = ap.parse_args()

    manifest = json.load(open(a.manifest))
    pool = build_pool(manifest)
    if a.limit:
        pool = pool[: a.limit]
    print(f"usable programs (both C1 and C2 build, run and have an input): {len(pool)}", flush=True)

    from llama_cpp import Llama
    llm = Llama(model_path=a.gguf, n_gpu_layers=-1, n_ctx=a.n_ctx, verbose=False)
    results = run_control(pool, llm, a.out, seed=a.seed, n_ctx=a.n_ctx, resume=a.resume)
    summarize(results, pool, os.path.basename(a.gguf))


if __name__ == "__main__":
    main()
