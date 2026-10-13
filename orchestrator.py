"""
Orchestrator: builds the 8 executable conditions from a base code sample,
chaining X2-X4. This is the PipelineRow contract from stubs.py made
concrete.

Two of the original five candidate factors are not chained here at all,
because they were validated and withdrawn before the executable design was
fixed rather than left as dead branches in this function:

  X1 (memorization / repository overlap): confirmed infeasible by direct
  measurement (500/500 dated CodeNet samples fall pre-cutoff; see
  design_matrix.py and x1_cutoff.py). There is no pool-selection step for
  it because there is no executable operationalization of it on this
  corpus.

  Cross-language transpilation: implemented (transpile.py, still present
  and independently tested), measured, and withdrawn on construct-validity
  grounds -- balanced coverage required a pool with median cyclomatic
  complexity 2 and median nesting depth 0. It is not called from
  build_condition() below; the module is kept because its
  differential-verification technique is reused conceptually by X3.

ORDER OF OPERATIONS for the three factors that remain:

  1. X4 (syntheticity) resolves WHAT THE BASE CONTENT IS: if 'synthetic',
     the real sample's code is REPLACED by a generated counterpart matched
     to its complexity profile (synthesize.py), before X2/X3 run -- those
     are transforms of "the content," not transforms of "whether the
     content is real."

  2. X2 (identifiers), X3 (AST structure) apply in that order to whichever
     base content step 1 resolved to.
"""
from __future__ import annotations
import ast
import json
import random
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "perturbations"))

from identifier_rename import obfuscate_identifiers
from ast_shuffle import (shuffle_ast, shuffle_and_verify,
                          shuffle_and_verify_script, verify_behavior,
                          verify_script_behavior)
from synthesize import (complexity_profile, generate_synthetic,
                        generate_synthetic_script, SCRIPT_STDIN_CASES,
                        infer_func_name, test_inputs_for)

from design_matrix import build_design_matrix, describe_matrix, FACTORS


def _synthetic_base_for_sample(base_sample, real_code, target_profile, rng, config):
    """Return (code, profile, distance) for the synthetic base program of this sample.

    Default (no flags): unchanged behaviour, a fresh program per call, i.e. per synthetic condition.
    --shared-synth / --shape-match: generated ONCE per sample and cached on base_sample, so C2, C4, C6 and C8 all start
    from the same base program and X2/X3 are the only differences between them. --shape-match additionally requires the
    synthetic program's output shape to match the real program's, measured by executing the real program on its first
    stdin case."""
    share = config.get("shared_synth") or config.get("shape_match")
    cache = base_sample.setdefault("_synthetic_base", {}) if share else {}
    if cache.get("code"):
        return cache["code"], cache["profile"], cache["distance"]
    info = None
    if config.get("shape_match"):
        from synthesize_shape import generate_synthetic_script_shaped, output_shape
        from ast_shuffle import _run_script
        out, err = _run_script(real_code, base_sample["stdin_cases"][0], 5.0)
        real_shape = output_shape(out) if not err else "single"
        code, prof, dist, info = generate_synthetic_script_shaped(
            target_profile, rng, want_multiline=(real_shape == "multi"),
            avoid_zero=(real_shape != "zero"), stdin=SCRIPT_STDIN_CASES[0])
        info = dict(info, real_shape=real_shape)
    else:
        code, prof, dist = generate_synthetic_script(target_profile, rng=rng)
    if share:
        cache.update(code=code, profile=prof, distance=dist, info=info)
    base_sample["_synthetic_info"] = info
    return code, prof, dist


def build_condition(base_sample: dict, condition: dict, config: dict) -> dict:
    """
    base_sample: {"source_code", "func_name", "test_inputs", "repo_id" (optional)}
    condition: one row dict from design_matrix.describe_matrix(), e.g.
      {"condition_id": 1, "identifiers": "obfuscated_renamed",
       "ast_structure": "randomized_valid_ast", "syntheticity": "real_world_code"}
    config: {
        "rng": random.Random,
        "shuffle_seed": int or None,
    }

    Returns a dict describing the built sample plus a per-operator status
    log, so failures at any stage are visible in the manifest rather than
    silently producing a broken or skipped condition.
    """
    rng = config.get("rng") or random.Random()
    log = {"condition_id": condition["condition_id"], "steps": []}

    code = base_sample["source_code"]
    func_name = base_sample.get("func_name")
    test_inputs = base_sample.get("test_inputs")
    stdin_cases = base_sample.get("stdin_cases")

    # Step 1 (X4): resolve base content.
    if condition["syntheticity"] == "synthetic_counterfactual":
        target_profile = complexity_profile(code)
        # Match the FORM of the base sample, not just its complexity. If the
        # base is a stdin->stdout script, generate a script; if it is a
        # callable function, generate a function. Mismatching forms makes X4
        # validate scripts in one X5 level and functions in the other, so X4
        # coverage becomes a function of X5 and the language contrast is
        # confounded with the syntheticity contrast.
        if stdin_cases:
            synth_code, achieved_profile, distance = _synthetic_base_for_sample(
                base_sample, code, target_profile, rng, config)
            code = synth_code
            func_name = None
            test_inputs = None
            stdin_cases = list(SCRIPT_STDIN_CASES)
            log["steps"].append({"op": "syntheticity", "value": "synthetic",
                                  "form": "script",
                                  "distance_to_target": distance,
                                  "shape_info": base_sample.get("_synthetic_info"),
                                  "n_stdin_cases": len(stdin_cases),
                                  "note": "script-form synthetic so X3/X4 validate the "
                                          "same way as in real cells"})
        else:
            synth_code, achieved_profile, distance = generate_synthetic(target_profile, rng=rng)
            code = synth_code
            func_name = infer_func_name(code)
        # The original sample's test inputs do not fit the synthetic
        # signature, so they are replaced -- NOT dropped. Dropping them would
        # leave synthetic samples unverifiable, and X3 refuses to shuffle
        # unverifiable code; since 4 of the 8 shuffle conditions are also
        # synthetic (3, 8, 12, 15), that would silently void half the X3
        # cells and bias S_i(structure) toward zero.
            test_inputs = test_inputs_for(code)
            stdin_cases = None
            log["steps"].append({"op": "syntheticity", "value": "synthetic",
                                  "form": "function",
                                  "distance_to_target": distance, "func_name": func_name,
                                  "n_test_inputs": len(test_inputs),
                                  "note": "template-matched test inputs substituted so X3 "
                                          "remains verifiable on synthetic samples"})
    else:
        log["steps"].append({"op": "syntheticity", "value": "real", "note": "base content unchanged"})

    # Step 3a (X2): identifiers.
    if condition["identifiers"] == "obfuscated_renamed":
        try:
            code, mapping = obfuscate_identifiers(code)
            if func_name in mapping:
                func_name = mapping[func_name]
            log["steps"].append({"op": "identifiers", "value": "obfuscated", "n_renamed": len(mapping)})
        except SyntaxError as e:
            log["steps"].append({"op": "identifiers", "value": "FAILED", "error": str(e)})
            return {"condition_id": condition["condition_id"], "source_code": None, "log": log, "status": "failed"}
    else:
        log["steps"].append({"op": "identifiers", "value": "original"})

    # Step 3b (X3): AST structure.
    #
    # Uses the VERIFIED shuffle variants, not bare shuffle_ast(). Measured
    # corruption on a real CodeNet pool ran as high as 7.1% before the
    # operator was hardened, and a residual 0.4% defect only appeared when
    # the verification pool was enlarged from 100 to 500 samples. Bare
    # shuffling would put silently-broken programs into the X3 condition,
    # where the model is penalized for reasons unrelated to structure and
    # S_i(structure) becomes an artifact of the instrument.
    if condition["ast_structure"] == "randomized_valid_ast":
        seed = config.get("shuffle_seed")
        verify_mode = config.get("verify_x3", True)
        try:
            if not verify_mode:
                code, stats = shuffle_ast(code, seed=seed)
                log["steps"].append({"op": "ast_structure", "value": "shuffled",
                                      "verified": False,
                                      "warning": "verification disabled -- corrupted "
                                                 "samples may enter the dataset",
                                      **stats})
            elif stdin_cases:
                # Top-level script: verify by running the whole program.
                code, stats, report = shuffle_and_verify_script(
                    code, stdin_cases, seed=seed)
                log["steps"].append({"op": "ast_structure",
                                      "value": "original (reverted)" if stats.get("reverted")
                                               else "shuffled",
                                      "verified": True, "mode": "script",
                                      "n_shuffled_blocks": stats.get("n_shuffled_blocks"),
                                      "reverted": stats.get("reverted"),
                                      "verification_passed": report.get("passed")})
            elif test_inputs:
                # Function-mode: verify by calling the function.
                code, stats, report = shuffle_and_verify(
                    code, func_name, test_inputs, seed=seed)
                log["steps"].append({"op": "ast_structure",
                                      "value": "original (reverted)" if stats.get("reverted")
                                               else "shuffled",
                                      "verified": True, "mode": "function",
                                      "n_shuffled_blocks": stats.get("n_shuffled_blocks"),
                                      "reverted": stats.get("reverted"),
                                      "verification_passed": report.get("passed")})
            else:
                # No way to verify. Refuse to shuffle rather than emit
                # unverified code -- consistent with the operator's own
                # policy in shuffle_and_verify_script().
                log["steps"].append({"op": "ast_structure", "value": "SKIPPED",
                                      "note": "no stdin_cases or test_inputs available; "
                                              "refusing to shuffle unverified"})
        except SyntaxError as e:
            log["steps"].append({"op": "ast_structure", "value": "FAILED", "error": str(e)})
            return {"condition_id": condition["condition_id"], "source_code": None,
                    "log": log, "status": "failed"}
    else:
        log["steps"].append({"op": "ast_structure", "value": "original"})

    # Optional: normalise formatting identically in every condition (see patch_normalize.py).
    if config.get("normalize_baseline") and code:
        try:
            normalised = ast.unparse(ast.parse(code))
        except SyntaxError as e:
            log["steps"].append({"op": "normalize", "value": "FAILED", "error": str(e)})
            return {"condition_id": condition["condition_id"], "source_code": None, "log": log, "status": "failed"}
        if normalised != code:
            if stdin_cases:
                rep = verify_script_behavior(code, normalised, stdin_cases[:1])
            elif test_inputs and func_name:
                rep = verify_behavior(code, normalised, func_name, test_inputs[:1])
            else:
                rep = {"passed": True}
            if not rep["passed"]:
                log["steps"].append({"op": "normalize", "value": "FAILED", "error": "round-trip changed behavior"})
                return {"condition_id": condition["condition_id"], "source_code": None, "log": log, "status": "failed"}
            code = normalised
        log["steps"].append({"op": "normalize", "value": "ast_roundtrip"})

    return {
        "condition_id": condition["condition_id"],
        "source_code": code,
        "func_name": func_name,
        "test_inputs": test_inputs,
        # Carried through so downstream scoring can execute the built program.
        # These are the cases for THIS condition: a synthetic condition
        # replaces them with template-appropriate ones, so taking the base
        # sample's cases downstream would feed the wrong inputs.
        "stdin_cases": stdin_cases,
        "log": log,
        "status": "ok",
    }


def build_all_conditions(base_sample: dict, config: dict) -> list:
    """Builds all 16 conditions for one base sample. Returns list of the
    dicts build_condition() produces, in condition_id order."""
    matrix = build_design_matrix()
    conditions = describe_matrix(matrix)
    return [build_condition(base_sample, c, config) for c in conditions]


def check_sample_eligibility(base_sample: dict, config: dict) -> tuple[bool, str]:
    """A sample may enter the design ONLY if it can receive every treatment.

    WHY THIS IS A HARD GATE, not a per-condition fallback. Allowing a sample
    to be treated in some cells and skipped in others makes treatment coverage
    a function of the other factors, which confounds the contrast. This was
    measured, not hypothesized: samples lacking test inputs were skipped by X3
    in real-code cells but shuffled fine in synthetic cells (synthetic
    templates supply their own inputs), giving X3 coverage of 66.7% in
    conditions 4/7/11/16 versus 100% in 3/8/12/15 -- exactly the cells where
    X5 differs. The X3 contrast would then have been partly an X5 contrast.

    Excluding such samples up front costs pool size but keeps every cell
    comparable, which is the property the whole factorial design rests on."""
    code = base_sample.get("source_code")
    if not code:
        return False, "no source_code"

    try:
        ast.parse(code)
    except (SyntaxError, ValueError, RecursionError) as e:
        return False, f"does not parse: {type(e).__name__}"

    # X3 needs behavioral verification, which needs either stdin cases (script
    # mode) or test inputs plus a function name (function mode).
    if config.get("verify_x3", True):
        has_stdin = bool(base_sample.get("stdin_cases"))
        has_fn_tests = bool(base_sample.get("test_inputs")) and bool(base_sample.get("func_name"))
        if not (has_stdin or has_fn_tests):
            return False, "no stdin_cases or (func_name + test_inputs) for X3 verification"

    # X2 must not break the program. Verified by EXECUTION, not by structure:
    # renaming leaves AST shape untouched by construction, so a structural
    # metric reports 0.0000 while silently breaking programs. Measured break
    # rate was 62.5% on a probe set before the obfuscator was fixed, and 1.0%
    # on real CodeNet code afterwards (a fast-IO idiom that redefines the
    # `input` builtin).
    #
    # Excluded rather than reverted, for the same reason as above: if X2
    # silently no-ops on some samples, X2 coverage varies across cells and the
    # lexical contrast is confounded. Costs pool size, keeps cells comparable.
    if config.get("verify_x2", True):
        try:
            renamed, mapping = obfuscate_identifiers(code)
        except Exception as e:
            return False, f"X2 raised {type(e).__name__}"
        if not mapping:
            return False, "X2 skipped (opaque exec/eval call) -- would no-op in obfuscated cells"
        stdin_cases = base_sample.get("stdin_cases")
        test_inputs = base_sample.get("test_inputs")
        if stdin_cases:
            rep = verify_script_behavior(code, renamed, stdin_cases[:1])
            if not rep["passed"]:
                reason = (rep["mismatches"][0].get("reason", "") if rep["mismatches"] else "")
                if reason.startswith("original failed"):
                    return False, "original program fails its own test case"
                return False, "X2 renaming changes behavior"
        elif test_inputs and base_sample.get("func_name"):
            rep = verify_behavior(code, renamed, base_sample["func_name"], test_inputs[:1])
            if not rep["passed"]:
                reason = (rep["mismatches"][0].get("reason", "") if rep["mismatches"] else "")
                if reason.startswith("original failed"):
                    return False, "original program fails its own test case"
                return False, "X2 renaming changes behavior"

    return True, "eligible"


def build_manifest(samples: list, config: dict) -> dict:
    """
    samples: list of base_sample dicts (one per real code sample in your pool).
    Returns a manifest: for each sample, all 16 built conditions plus a
    summary of failure counts per operator -- this is the thing to inspect
    before handing off to model scoring, since a condition with status
    'failed' must be excluded or redrawn, not scored as-is.
    """
    manifest = {"samples": [], "excluded": [],
                "summary": {"n_samples_submitted": len(samples), "n_samples_eligible": 0,
                            "n_samples_excluded": 0, "n_conditions_total": 0,
                            "n_conditions_ok": 0, "n_conditions_failed": 0,
                            "n_x3_reverted": 0, "n_x3_skipped_unverifiable": 0,
                            "n_x3_shuffled": 0}}

    # Gate the pool BEFORE building any condition -- see
    # check_sample_eligibility() for why this must not be a per-condition
    # fallback.
    eligible = []
    for i, sample in enumerate(samples):
        ok, reason = check_sample_eligibility(sample, config)
        if ok:
            eligible.append((i, sample))
        else:
            manifest["excluded"].append({"sample_index": i,
                                          "repo_id": sample.get("repo_id"),
                                          "reason": reason})
    manifest["summary"]["n_samples_eligible"] = len(eligible)
    manifest["summary"]["n_samples_excluded"] = len(manifest["excluded"])

    for i, sample in eligible:
        built = build_all_conditions(sample, config)
        manifest["samples"].append({"sample_index": i, "base_repo_id": sample.get("repo_id"), "problem_id": sample.get("problem_id"), "stdin_cases": sample.get("stdin_cases"), "conditions": built})
        manifest["summary"]["n_conditions_total"] += len(built)
        manifest["summary"]["n_conditions_ok"] += sum(1 for c in built if c["status"] == "ok")
        manifest["summary"]["n_conditions_failed"] += sum(1 for c in built if c["status"] == "failed")
        for c in built:
            for step in c["log"]["steps"]:
                if step.get("op") != "ast_structure":
                    continue
                if step.get("reverted"):
                    manifest["summary"]["n_x3_reverted"] += 1
                elif step.get("value") == "SKIPPED":
                    manifest["summary"]["n_x3_skipped_unverifiable"] += 1
                elif step.get("value") == "shuffled":
                    manifest["summary"]["n_x3_shuffled"] += 1
    return manifest


def load_samples(path: str, limit: int = None) -> list:
    """Load the .jsonl produced by join_codenet_tests.py."""
    out = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out[:limit] if limit else out


def _jsonable(o):
    if isinstance(o, dict):
        return {k: _jsonable(v) for k, v in o.items()}
    if isinstance(o, list):
        return [_jsonable(v) for v in o]
    if isinstance(o, (str, int, float, bool)) or o is None:
        return o
    return str(o)


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(
        description="Build the 16 Resolution V conditions for each sample.")
    ap.add_argument("--samples", required=True,
                    help=".jsonl from join_codenet_tests.py "
                         "(needs source_code plus stdin_cases or test_inputs)")
    ap.add_argument("--manifest-out", default="manifest.json")
    ap.add_argument("--limit", type=int, default=None,
                    help="Process only the first N samples. Start small: X3 "
                         "verification runs each program in a subprocess.")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--normalize-baseline", action="store_true", default=False,
                    help="Pass EVERY condition (incl. C1/C2) through the same ast.unparse round-trip so formatting is not confounded with X2/X3.")
    ap.add_argument("--shared-synth", action="store_true", default=False,
                    help="Build the synthetic base program once per sample and reuse it in every synthetic condition.")
    ap.add_argument("--shape-match", action="store_true", default=False,
                    help="Implies --shared-synth. Also match the synthetic program's output shape (multi-line / zero) to the real one.")
    ap.add_argument("--no-verify-x2", dest="verify_x2", action="store_false",
                    default=True,
                    help="Skip the X2 eligibility check (executes each sample "
                         "once). Faster, but samples whose renaming breaks them "
                         "will enter the pool and confound the lexical contrast.")
    ap.add_argument("--no-verify-x3", dest="verify_x3", action="store_false",
                    default=True,
                    help="Disable X3 behavioral verification. NOT recommended: "
                         "measured corruption reached 7.1%% before hardening, and "
                         "unverified shuffles put broken programs into the X3 "
                         "condition where they are scored as structural failures.")
    args = ap.parse_args()

    samples = load_samples(args.samples, args.limit)
    print(f"Loaded {len(samples)} samples from {args.samples}")

    config = {
        "rng": random.Random(args.seed),
        "shuffle_seed": args.seed,
        "verify_x3": args.verify_x3,
        "verify_x2": args.verify_x2,
        "shared_synth": args.shared_synth,
        "normalize_baseline": args.normalize_baseline,
        "shape_match": args.shape_match,
    }

    manifest = build_manifest(samples, config)
    with open(args.manifest_out, "w") as f:
        json.dump(_jsonable(manifest), f)

    s = manifest["summary"]
    print(json.dumps(s, indent=2))
    print(f"\nManifest written to {args.manifest_out}")
    if s["n_samples_excluded"]:
        print(f"{s['n_samples_excluded']} samples excluded before the design; "
              f"reasons in manifest['excluded'].")
    print(f"\nNext: python3 audit_manifest.py --manifest {args.manifest_out}")