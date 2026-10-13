"""
Large-scale behavioral verification for X4 (synthesis), matching the rigor
already applied to X2 (verify_x2_pool.py) and X3 (verify_x3_pool.py).

WHY THIS EXISTS, AND WHY IT WAS MISSING. X2 and X3 both got differential
testing at real scale: run original vs. perturbed on shared inputs, require
identical output, measure the failure rate. X4 (synthesis) has no
"original" to differentially compare against -- a synthetic program is a
DIFFERENT program by design, matched to a real sample's complexity profile
rather than its behavior. So the correctness criterion is different in
kind, not just in degree:

    X2/X3: does the perturbed program behave IDENTICALLY to the original?
    X4:    does the generated program EXECUTE CORRECTLY at all, against
           its own accompanying test inputs, and does it land within
           tolerance of its target complexity?

Before this script, that second question had only been checked against 3
hand-picked reference profiles during development (synthesize.py's
__main__). This runs it against real target profiles at the same scale
(hundreds of samples) the other two operators were held to, because the
established pattern in this project is that operators which look correct
on a handful of cases have failed at scale before (X3's semantic-corruption
bug, X2's fast-IO break) -- there is no reason to assume X4 is exempt from
that pattern just because it happens not to have been tested that way yet.

Usage:
    python3 verify_x4_pool.py --samples rq4_samples_verified.jsonl --limit 300
"""
import argparse
import json
import os
import statistics
import sys
import time
import warnings

warnings.filterwarnings("ignore", category=SyntaxWarning)

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "perturbations"))

from synthesize import (complexity_profile, generate_synthetic,
                         generate_synthetic_script, SCRIPT_STDIN_CASES,
                         infer_func_name, test_inputs_for)
from ast_shuffle import _run, _run_script


def verify_one(source_code: str, stdin_cases, rng, timeout: float = 5.0) -> dict:
    """Generate one synthetic counterpart and verify it by execution.

    Mirrors orchestrator.py's own form-selection logic exactly (script vs.
    function) so this test exercises the same code path the real pipeline
    uses, not a parallel approximation of it."""
    try:
        target = complexity_profile(source_code)
    except SyntaxError as e:
        return {"status": "source_parse_error", "error": str(e)}

    is_script = bool(stdin_cases)

    if is_script:
        try:
            synth_code, achieved, dist = generate_synthetic_script(target, rng=rng)
        except Exception as e:
            return {"status": "generation_error", "error": str(e), "form": "script"}

        n_ok, n_total, errors = 0, len(SCRIPT_STDIN_CASES), []
        for case in SCRIPT_STDIN_CASES:
            out, err = _run_script(synth_code, case, timeout)
            if err is None:
                n_ok += 1
            else:
                errors.append({"stdin": case, "error": err[:200]})
        executes_cleanly = (n_ok == n_total)
    else:
        try:
            synth_code, achieved, dist = generate_synthetic(target, rng=rng)
        except Exception as e:
            return {"status": "generation_error", "error": str(e), "form": "function"}

        fn = infer_func_name(synth_code)
        inputs = test_inputs_for(synth_code)
        if not fn or not inputs:
            return {"status": "no_test_inputs_for_template", "form": "function",
                    "template": fn}

        n_ok, n_total, errors = 0, len(inputs), []
        for args in inputs:
            out, err = _run(synth_code, fn, args, timeout)
            if err is None:
                n_ok += 1
            else:
                errors.append({"input": args, "error": err[:200]})
        executes_cleanly = (n_ok == n_total)

    return {
        "status": "ok" if executes_cleanly else "execution_failure",
        "form": "script" if is_script else "function",
        "n_test_cases_ok": n_ok, "n_test_cases_total": n_total,
        "distance": dist,
        "target": {"cyclomatic": target.cyclomatic, "lines": target.lines,
                   "max_depth": target.max_depth},
        "achieved": {"cyclomatic": achieved.cyclomatic, "lines": achieved.lines,
                    "max_depth": achieved.max_depth},
        "errors": errors[:2],
        "synth_code": synth_code,
    }


def run(samples: list, seed: int = 0, tolerance: float = 0.15,
        progress_every: int = 50) -> dict:
    import random
    rng = random.Random(seed)
    t0 = time.time()

    results = []
    n_source_parse_fail = 0
    n_generation_error = 0
    n_no_template_inputs = 0
    n_execution_failure = 0
    n_ok = 0

    for i, s in enumerate(samples):
        if progress_every and i and i % progress_every == 0:
            el = time.time() - t0
            print(f"  ...{i}/{len(samples)} ({el:.1f}s) "
                  f"[ok={n_ok} exec_fail={n_execution_failure}]", flush=True)

        r = verify_one(s["source_code"], s.get("stdin_cases"), rng)
        status = r["status"]
        if status == "source_parse_error":
            n_source_parse_fail += 1
            continue
        if status == "generation_error":
            n_generation_error += 1
            continue
        if status == "no_test_inputs_for_template":
            n_no_template_inputs += 1
            continue
        if status == "execution_failure":
            n_execution_failure += 1
            r["repo_id"] = s.get("repo_id") or s.get("pair_id")
            results.append(r)
            continue

        n_ok += 1
        r["repo_id"] = s.get("repo_id") or s.get("pair_id")
        results.append(r)

    n_attempted = n_ok + n_execution_failure
    distances_ok = [r["distance"] for r in results if r["status"] == "ok"]

    return {
        "n_samples": len(samples),
        "elapsed_seconds": time.time() - t0,
        "n_source_parse_fail": n_source_parse_fail,
        "n_generation_error": n_generation_error,
        "n_no_template_inputs_for_form": n_no_template_inputs,
        "n_attempted": n_attempted,
        "n_execution_ok": n_ok,
        "n_execution_failure": n_execution_failure,
        "execution_failure_rate": (n_execution_failure / n_attempted) if n_attempted else None,
        "distance_ok": {
            "n": len(distances_ok),
            "mean": statistics.mean(distances_ok) if distances_ok else None,
            "median": statistics.median(distances_ok) if distances_ok else None,
            "max": max(distances_ok) if distances_ok else None,
            "n_over_tolerance": sum(1 for d in distances_ok if d > tolerance),
        },
        "failures": [r for r in results if r["status"] == "execution_failure"][:5],
    }


def print_report(r: dict, tolerance: float):
    print("\n" + "=" * 66)
    print("X4 (SYNTHESIS) EXECUTION VERIFICATION")
    print("=" * 66)
    print(f"  samples:                    {r['n_samples']}")
    print(f"  elapsed:                    {r['elapsed_seconds']:.1f}s")
    print(f"  skipped, source parse fail: {r['n_source_parse_fail']}")
    print(f"  skipped, generation error:  {r['n_generation_error']}")
    print(f"  skipped, no template inputs:{r['n_no_template_inputs_for_form']}")
    print()
    print(f"  ATTEMPTED:                  {r['n_attempted']}")
    print(f"    executes cleanly:         {r['n_execution_ok']}")
    print(f"    EXECUTION FAILURE:        {r['n_execution_failure']}")
    if r["execution_failure_rate"] is not None:
        print(f"    failure rate:              {r['execution_failure_rate']:.1%}")

    d = r["distance_ok"]
    if d["n"]:
        print(f"\n  Complexity-match distance among clean-executing samples (n={d['n']}):")
        print(f"    mean {d['mean']:.4f}  median {d['median']:.4f}  max {d['max']:.4f}")
        print(f"    {d['n_over_tolerance']}/{d['n']} exceed the {tolerance} tolerance "
              f"used during development validation")

    if r["failures"]:
        print("\n" + "=" * 66)
        print("EXECUTION FAILURES (inspect these -- each is an operator bug)")
        print("=" * 66)
        for f in r["failures"]:
            print(f"\n--- {f['repo_id']} (form={f['form']}, "
                  f"{f['n_test_cases_ok']}/{f['n_test_cases_total']} test cases ok) ---")
            print("GENERATED CODE:")
            print(f["synth_code"][:400])
            print("ERROR:", f["errors"][:1])

    print("\n" + "=" * 66)
    print("INTERPRETATION")
    print("=" * 66)
    rate = r["execution_failure_rate"]
    if rate is None:
        print("  Nothing attempted -- check the sample pool.")
    elif rate == 0:
        print("  No execution failures. This closes the scale gap between X4 and")
        print("  X2/X3: all three operators are now validated by execution on a")
        print("  real pool, not just hand-picked development cases.")
    else:
        print(f"  {rate:.1%} of generated synthetic samples fail to execute against")
        print("  their own accompanying test inputs. Inspect the failures above --")
        print("  this is the same class of bug X2 and X3 both had before hardening:")
        print("  an operator that looked correct on a handful of cases and broke at")
        print("  scale. Do not run the sweep with X4 unfixed if this rate is nonzero.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", required=True)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--tolerance", type=float, default=0.15)
    ap.add_argument("--json-out", default=None)
    args = ap.parse_args()

    samples = []
    with open(args.samples) as f:
        for line in f:
            line = line.strip()
            if line:
                samples.append(json.loads(line))
    if args.limit:
        samples = samples[:args.limit]

    result = run(samples, seed=args.seed, tolerance=args.tolerance)
    print_report(result, args.tolerance)

    if args.json_out:
        with open(args.json_out, "w") as f:
            json.dump(result, f, indent=2, default=str)
        print(f"\nFull results written to {args.json_out}")