"""
Join CodeNet test cases onto EMSE corpus samples, so X3 (AST shuffle) can be
behaviorally verified instead of trusted.

WHY THIS EXISTS: the X3 operator was caught emitting semantically broken code
(see ast_shuffle.py module docstring). The fix included differential
verification, but verification needs test inputs, and the EMSE pairs file
ships code only. Project_CodeNet ships the missing half:

    derived/input_output/data/<problem_id>/input.txt
    derived/input_output/data/<problem_id>/output.txt

and the EMSE pairs carry `problem_id`, so this is a lookup, not a data
collection problem.

IMPORTANT LIMITATION, state it in the paper: CodeNet provides ONE
input/output pair per problem, not a test suite. Single-case verification is
materially weaker than multi-case. We already have a concrete demonstration
of why that matters -- in transpilation validation, a translation with an
inverted operator produced the CORRECT output on one of four inputs by
coincidence and would have passed a single-case check. A shuffle that
survives one input is evidence, not proof. Treat the pass rate reported here
as a lower bound on corruption, never as a guarantee of correctness.

Usage:
    python3 join_codenet_tests.py \\
        --pairs PATH/TO/pairs_codenet_python.json \\
        --codenet PATH/TO/Project_CodeNet \\
        --output rq4_samples_verified.jsonl --n 500
"""
from __future__ import annotations
import argparse
import ast
import json
import os
import random
import sys
import warnings

warnings.filterwarnings("ignore", category=SyntaxWarning)

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "perturbations"))


def load_test_case(codenet_root: str, problem_id: str):
    """Returns (stdin_text, expected_stdout) or (None, None) if absent."""
    base = os.path.join(codenet_root, "derived", "input_output", "data", problem_id)
    inp = os.path.join(base, "input.txt")
    out = os.path.join(base, "output.txt")
    if not (os.path.isfile(inp) and os.path.isfile(out)):
        return None, None
    try:
        with open(inp, "r", errors="replace") as f:
            stdin_text = f.read()
        with open(out, "r", errors="replace") as f:
            expected = f.read()
        return stdin_text, expected
    except OSError:
        return None, None


def parses(code: str) -> bool:
    try:
        ast.parse(code)
        return True
    except Exception:
        return False


def build(pairs_path: str, codenet_root: str, output_path: str,
          n: int, field: str, seed: int, require_tests: bool,
          require_parse: bool) -> dict:
    with open(pairs_path) as f:
        pairs = json.load(f)

    key = "correct_code" if field == "correct" else "buggy_code"
    rng = random.Random(seed)

    stats = {
        "n_pairs": len(pairs),
        "n_missing_problem_id": 0,
        "n_no_test_case": 0,
        "n_parse_fail": 0,
        "n_eligible": 0,
    }

    eligible = []
    for p in pairs:
        code = p.get(key)
        if not code:
            continue

        pid = p.get("problem_id")
        if not pid:
            stats["n_missing_problem_id"] += 1
            if require_tests:
                continue

        if require_parse and not parses(code):
            stats["n_parse_fail"] += 1
            continue

        stdin_text, expected = (None, None)
        if pid:
            stdin_text, expected = load_test_case(codenet_root, pid)
        if stdin_text is None:
            stats["n_no_test_case"] += 1
            if require_tests:
                continue

        rec = {
            "source_code": code,
            "pair_id": p.get("pair_id"),
            "problem_id": pid,
            "field": key,
            # Carried through so a date join (join_codenet_dates.py) is exact
            # rather than needing to regex-recover an id from pair_id. Both
            # ids are kept, not just the one matching `field`, since a sample
            # built from correct_code may later need the buggy submission's
            # date too (e.g. to check the two sides of a pair straddle the
            # cutoff consistently).
            "correct_sub_id": p.get("correct_sub_id"),
            "buggy_sub_id": p.get("buggy_sub_id"),
        }
        if stdin_text is not None:
            # verify_script_behavior() takes a LIST of stdin cases. CodeNet
            # gives one; the list keeps the interface honest about the fact
            # that more would be better.
            rec["stdin_cases"] = [stdin_text]
            rec["expected_stdout"] = expected
        eligible.append(rec)

    stats["n_eligible"] = len(eligible)
    if n < len(eligible):
        eligible = rng.sample(eligible, n)

    with open(output_path, "w") as f:
        for r in eligible:
            f.write(json.dumps(r) + "\n")

    stats["n_written"] = len(eligible)
    stats["n_written_with_tests"] = sum(1 for r in eligible if "stdin_cases" in r)
    stats["output_path"] = output_path
    return stats


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", required=True)
    ap.add_argument("--codenet", required=True,
                    help="Project_CodeNet root (the dir containing derived/)")
    ap.add_argument("--output", default="rq4_samples_verified.jsonl")
    ap.add_argument("--n", type=int, default=500)
    ap.add_argument("--field", choices=["correct", "buggy"], default="correct")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--require-tests", action="store_true", default=True,
                    help="Only keep samples that have a CodeNet test case (default on). "
                         "Use --allow-untested to include samples without one.")
    ap.add_argument("--allow-untested", dest="require_tests", action="store_false")
    ap.add_argument("--allow-unparsed", dest="require_parse", action="store_false",
                    default=True,
                    help="Keep samples whose code does not parse as Python 3 "
                         "(default is to drop them; ~8%% of this corpus).")
    args = ap.parse_args()

    stats = build(args.pairs, args.codenet, args.output, args.n,
                  args.field, args.seed, args.require_tests, args.require_parse)
    print(json.dumps(stats, indent=2))
    print()
    print(f"  {stats['n_written_with_tests']}/{stats['n_written']} written samples "
          f"carry a CodeNet test case.")
    print("  NOTE: one test case per problem. Single-case verification catches "
          "gross\n  corruption but can miss subtle behavior changes -- report it "
          "as a lower\n  bound on corruption, not a correctness guarantee.")
    print(f"\nNext: python3 verify_x3_pool.py --samples {args.output}")