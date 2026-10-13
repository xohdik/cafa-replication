#!/usr/bin/env python3
"""
make_confirmation_pairs.py -- build a pairs file for a CONFIRMATION pool that is disjoint from the pilot at the PROBLEM level and has at most
one program per problem, so programs are independent draws of different tasks (no within-problem correlation to inflate precision).

Keeps only pairs whose problem has CodeNet test cases (derived/input_output/data/<problem_id>) and whose correct_code parses as Python 3.
Excludes every problem that appears in the pilot pool(s). Then picks one pair per remaining problem with a fixed seed.
Output has the same format as the input pairs file, so join_codenet_tests.py takes it unchanged.

Usage:
  python3 make_confirmation_pairs.py \
      --pairs PATH/TO/pairs_codenet_python.json \
      --codenet PATH/TO/Project_CodeNet \
      --exclude rq4_samples_verified_v2.jsonl rq4_samples_verified.jsonl rq4_samples.jsonl rq4_samples_dated.jsonl rq4_samples_dated_v2.jsonl \
      --out pairs_confirm.json --seed 1
"""
import argparse
import ast
import collections
import json
import os
import random
import warnings

warnings.filterwarnings("ignore")
ap = argparse.ArgumentParser()
ap.add_argument("--pairs", required=True)
ap.add_argument("--codenet", required=True)
ap.add_argument("--exclude", nargs="*", default=[])
ap.add_argument("--out", required=True)
ap.add_argument("--field", default="correct_code")
ap.add_argument("--seed", type=int, default=1)
a = ap.parse_args()

pairs = json.load(open(a.pairs))
excl_problems, excl_pairs = set(), set()
for f in a.exclude:
    for line in open(f):
        line = line.strip()
        if line:
            r = json.loads(line)
            excl_problems.add(r.get("problem_id"))
            excl_pairs.add(r.get("pair_id"))
print(f"pairs in file: {len(pairs)}   problems in pairs: {len({p['problem_id'] for p in pairs})}")
print(f"pilot pools exclude: {len(excl_pairs)} pairs from {len(excl_problems)} distinct problems")

tests_root = os.path.join(a.codenet, "derived", "input_output", "data")
have_tests = set(os.listdir(tests_root))
by_problem = collections.defaultdict(list)
n_notests = n_unparse = n_excl = 0
for p in pairs:
    pid = p["problem_id"]
    if pid in excl_problems:
        n_excl += 1
        continue
    if pid not in have_tests:
        n_notests += 1
        continue
    try:
        ast.parse(p[a.field])
    except Exception:
        n_unparse += 1
        continue
    by_problem[pid].append(p)
print(f"dropped: pilot problems {n_excl}, no test cases {n_notests}, unparseable {n_unparse}")
rng = random.Random(a.seed)
chosen = [rng.choice(v) for k, v in sorted(by_problem.items())]
rng.shuffle(chosen)
json.dump(chosen, open(a.out, "w"))
print(f"problems available: {len(by_problem)}   one pair per problem written to {a.out}: {len(chosen)}")
