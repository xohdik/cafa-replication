#!/usr/bin/env python3
"""
inspect_idiom_failures.py -- WHY does DeepSeek fail on C2 but not on C6 (same synthetic program, identifiers obfuscated)?
Takes programs where condition A was wrong and condition B was right (default A=2, B=6) in an existing responses file, re-runs the
model on both with the harness's own prompt/scoring, prints the model's output next to the expected output, and tallies failure types.
Usage:
  python3 inspect_idiom_failures.py --manifest manifest_v2.json --responses responses_deepseek_v2.json \
      --gguf ./models/deepseek-coder-6.7b-base.Q4_K_M.gguf --a 2 --b 6 --n 60 --show 6
Run in the cafa env (needs llama_cpp), from the capa/ folder.
"""
import argparse
import collections
import json
import random

import scoring_harness as H

ap = argparse.ArgumentParser()
ap.add_argument("--manifest", required=True)
ap.add_argument("--responses", required=True)
ap.add_argument("--gguf", required=True)
ap.add_argument("--a", type=int, default=2)
ap.add_argument("--b", type=int, default=6)
ap.add_argument("--n", type=int, default=60)
ap.add_argument("--show", type=int, default=6)
ap.add_argument("--seed", type=int, default=0)
ap.add_argument("--n-ctx", type=int, default=8192)
args = ap.parse_args()

man = json.load(open(args.manifest))
res = json.load(open(args.responses))["per_sample_results"]
samples = {str(s["sample_index"]): s for s in man["samples"]}
cand = [pid for pid, r in res.items()
        if r.get(str(args.a)) and r.get(str(args.b)) and r[str(args.a)][0] == 0.0 and r[str(args.b)][0] == 1.0]
print(f"programs with C{args.a} wrong and C{args.b} right: {len(cand)} of {len(res)}")
random.Random(args.seed).shuffle(cand)
cand = cand[:args.n]

from llama_cpp import Llama
llm = Llama(model_path=args.gguf, n_gpu_layers=-1, n_ctx=args.n_ctx, verbose=False)


def run(pid, cid):
    s = samples[pid]
    built = next(c for c in s["conditions"] if c["condition_id"] == cid)
    code = built["source_code"]
    stdin = (built.get("stdin_cases") or s.get("stdin_cases"))[0]
    exp, err = H.ground_truth(code, stdin)
    r = H.score_one(llm, code, stdin, exp, n_ctx=args.n_ctx)
    return code, stdin, exp, r


def kind(pred, exp):
    p, e = H.normalize(pred), H.normalize(exp)
    pl, el = p.splitlines(), e.splitlines()
    if not p:
        return "empty prediction"
    if len(pl) < len(el):
        return "fewer lines than expected"
    if len(pl) > len(el):
        return "more lines than expected"
    if len(pl) == 1 and pl[0].lstrip("-").isdigit() and el[0].lstrip("-").isdigit():
        return "single number, wrong value"
    return "same line count, wrong content"


tally = collections.Counter()
repro = 0
for k, pid in enumerate(cand):
    codeA, stdinA, expA, rA = run(pid, args.a)
    codeB, stdinB, expB, rB = run(pid, args.b)
    if rA["status"] == "ok" and not rA["correct"]:
        repro += 1
        tally[kind(rA["prediction"], expA)] += 1
    if k < args.show and rA["status"] == "ok":
        print("\n" + "=" * 78 + f"\nprogram {pid}   C{args.a}: {'OK' if rA['correct'] else 'WRONG'}   "
              f"C{args.b}: {'OK' if rB['correct'] else 'WRONG'}\n" + "=" * 78)
        print(codeA.strip()[:700])
        print(f"--- stdin: {stdinA.strip()!r}")
        print(f"--- expected : {expA.strip()[:160]!r}")
        print(f"--- C{args.a} predicted: {rA['prediction'].strip()[:160]!r}")
        print(f"--- C{args.b} predicted: {rB.get('prediction', '').strip()[:160]!r}")
print(f"\nre-run reproduced the C{args.a} failure on {repro} of {len(cand)} programs")
print(f"failure types for C{args.a} (what the model actually produced):")
for k, v in tally.most_common():
    print(f"  {k:<34}{v:>4}  ({v / max(repro, 1):.0%})")
