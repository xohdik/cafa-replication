"""
Diagnose X4 (transpilation): show what the model actually produces and where
validation rejects it.

Motivation: a manifest audit showed X4 at 0% coverage with two distinct
patterns -- SKIPPED on real samples (they carry stdin_cases, and the operator
only handled function-mode test_inputs) and FAILED on synthetic samples
(translation attempted, validation rejected all). The skip is a code gap. The
failure could be model quality or a harness defect, and those need different
responses, so this prints the raw output rather than guessing.

Usage:
    python3 diagnose_x4.py --gguf ./models/deepseek-coder-6.7b-base.Q4_K_M.gguf --n 3
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "perturbations"))

from transpile import (make_llama_cpp_translate_fn, validate_equivalence,
                        _strip_markdown_fences, _run_snippet)
from synthesize import complexity_profile, generate_synthetic, infer_func_name, test_inputs_for
import random


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gguf", required=True)
    ap.add_argument("--n", type=int, default=3)
    ap.add_argument("--target", default="javascript")
    ap.add_argument("--max-tokens", type=int, default=768)
    ap.add_argument("--samples", default=None,
                    help="If given, diagnose REAL script-mode samples from this "
                         ".jsonl instead of synthetic functions. This is the case "
                         "that matters: real corpora are mostly stdin->stdout "
                         "scripts, which are harder to translate than functions.")
    ap.add_argument("--translatable-only", action="store_true",
                    help="Skip samples whose imports have no target-language "
                         "equivalent. Without this the measured rate mixes in "
                         "samples that are impossible for ANY model, which "
                         "understates what the operator achieves in scope.")
    ap.add_argument("--instruct", action="store_true",
                    help="Treat the GGUF as instruct-tuned (pass the instruction "
                         "prompt through instead of few-shot completion).")
    args = ap.parse_args()

    print(f"Loading {args.gguf} ...")
    translate = make_llama_cpp_translate_fn(
        args.gguf, max_tokens=args.max_tokens, base_model=not args.instruct,
        target_language="JavaScript" if args.target == "javascript" else args.target)
    print(f"mode: {'instruct passthrough' if args.instruct else 'base few-shot completion'}")

    # Use synthetic samples: simple, self-contained, known signature and
    # test inputs. If the model cannot translate THESE, the problem is not
    # the complexity of real CodeNet code.
    rng = random.Random(0)
    target_profile = complexity_profile(
        "def f(x):\n    t = 0\n    for i in range(x):\n        if i > 0:\n            t += i\n    return t")

    if args.samples:
        from transpile import (validate_script_equivalence, _run_script_lang,
                                _looks_like_script)
        rows = []
        with open(args.samples) as f:
            for line in f:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
        rows = [r for r in rows if r.get("stdin_cases")]
        if args.translatable_only:
            from transpile import uses_untranslatable_imports
            before = len(rows)
            rows = [r for r in rows if not uses_untranslatable_imports(r["source_code"])]
            print(f"translatable filter: {len(rows)}/{before} samples in scope")
        rows = rows[:args.n]

        n_pass = 0
        for i, row in enumerate(rows):
            code = row["source_code"]
            cases = row["stdin_cases"]
            print("\n" + "=" * 70)
            print(f"SCRIPT SAMPLE {i+1}  (problem {row.get('problem_id')}, "
                  f"script={_looks_like_script(code)})")
            print("=" * 70)
            print("--- PYTHON SOURCE ---")
            print(code[:600])
            src_out, src_err = _run_script_lang("python", code, cases[0])
            print(f"\n--- SOURCE EXECUTES: {'yes' if src_err is None else 'NO -> ' + str(src_err)[:200]}")
            if src_err is not None:
                continue

            prompt = (f"Translate the following complete python program to "
                      f"{args.target}. It reads from standard input and writes to "
                      f"standard output; preserve that behavior exactly, including "
                      f"output format. Output ONLY the translated program, no "
                      f"explanation, no markdown fences.\n\n{code}")
            raw = translate(prompt)
            cleaned = _strip_markdown_fences(raw)
            print("\n--- RAW MODEL OUTPUT (first 700 chars) ---")
            print(repr(raw[:700]))
            tgt_out, tgt_err = _run_script_lang(args.target, cleaned, cases[0])
            print(f"\n--- TARGET EXECUTES: {'yes' if tgt_err is None else 'NO'}")
            if tgt_err:
                print(f"    error: {str(tgt_err)[:300]}")
            else:
                print(f"    python stdout: {src_out!r}")
                print(f"    node   stdout: {tgt_out!r}")
            res = validate_script_equivalence(code, cleaned, cases)
            print(f"\n--- VALIDATION: {res.summary()}")
            if res.passed:
                n_pass += 1

        print("\n" + "=" * 70)
        print(f"RESULT: {n_pass}/{len(rows)} script translations validated")
        print("=" * 70)
        if n_pass == 0:
            print("  Script translation is failing. Check whether the model emits")
            print("  code at all, whether it reads stdin the way the exemplar")
            print("  shows, and whether output formatting differs (extra spaces,")
            print("  float formatting, trailing newlines). Those are three very")
            print("  different problems with different fixes.")
        return

    n_pass = 0
    for i in range(args.n):
        code, prof, dist = generate_synthetic(target_profile, rng=rng)
        fn = infer_func_name(code)
        tis = test_inputs_for(code)

        print("\n" + "=" * 70)
        print(f"SAMPLE {i+1}  (func={fn}, {len(tis)} test inputs)")
        print("=" * 70)
        print("--- PYTHON SOURCE ---")
        print(code)

        # Confirm the SOURCE runs before blaming the translation.
        src_out, src_err = _run_snippet("python", code, fn, tis[0])
        print(f"\n--- SOURCE EXECUTES: {'yes' if src_err is None else 'NO -> ' + str(src_err)[:200]}")
        if src_err is not None:
            print("    (harness problem, not model quality -- stop here)")
            continue

        prompt = (f"Translate the following python function to {args.target}. "
                  f"Preserve the exact function name `{fn}` and behavior. "
                  f"Output ONLY the translated code, no explanation, no markdown "
                  f"fences.\n\n{code}")
        raw = translate(prompt)
        cleaned = _strip_markdown_fences(raw)

        print("\n--- RAW MODEL OUTPUT ---")
        print(repr(raw[:700]))
        print("\n--- AFTER FENCE STRIPPING ---")
        print(cleaned[:700])

        # Does the translated code even run standalone?
        tgt_out, tgt_err = _run_snippet(args.target, cleaned, fn, tis[0])
        print(f"\n--- TARGET EXECUTES: {'yes' if tgt_err is None else 'NO'}")
        if tgt_err is not None:
            print(f"    error: {str(tgt_err)[:400]}")

        result = validate_equivalence(code, cleaned, fn, tis,
                                       source_lang="python", target_lang=args.target)
        print(f"\n--- VALIDATION: {result.summary()}")
        for r in result.per_input[:3]:
            print(f"    input={r['input']} src={r['source_output']} "
                  f"tgt={r['target_output']} match={r['match']}"
                  + (f" err={str(r['error'])[:120]}" if r.get("error") else ""))
        if result.passed:
            n_pass += 1

    print("\n" + "=" * 70)
    print(f"RESULT: {n_pass}/{args.n} translations validated")
    print("=" * 70)
    if n_pass == 0:
        print("  If RAW MODEL OUTPUT looks like reasonable target-language code but")
        print("  TARGET EXECUTES is NO, the harness is at fault (wrong wrapper,")
        print("  wrong function invocation, output not JSON-serializable).")
        print("  If RAW MODEL OUTPUT is truncated, repeats the Python, or emits")
        print("  prose, the base model is at fault: a 6.7B BASE (non-instruct)")
        print("  model often does not follow 'output only code' instructions.")
        print("  In that case try an instruct-tuned model, or the DeepSeek API")
        print("  fallback, before concluding X4 is infeasible.")


if __name__ == "__main__":
    main()