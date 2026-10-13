"""
Pull actual model predictions on a handful of matched real/synthetic pairs,
since scoring_harness.py's persisted responses.json only keeps aggregated
0/1 correctness -- the prediction/expected text is computed in score_one()
and discarded, never saved. This exists to answer one question directly
rather than guess: is the large X4 (syntheticity) effect measuring
benchmark-artifact detection, or is it confounded by synthetic programs'
essentially-random arithmetic requiring true execution simulation, versus
real programs' disproportionate share of common, pattern-completable
algorithmic idioms?

Cheap by design: scores ~10-20 samples total, not the full manifest.

Usage:
    python3 inspect_predictions.py --manifest manifest.json \\
        --gguf ./models/deepseek-coder-6.7b-base.Q4_K_M.gguf --n 5
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "perturbations"))

from scoring_harness import PROMPT_TEMPLATE, ground_truth, normalize


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--gguf", required=True)
    ap.add_argument("--n", type=int, default=5,
                    help="Number of matched real/synthetic sample pairs to inspect.")
    ap.add_argument("--n-ctx", type=int, default=8192)
    args = ap.parse_args()

    manifest = json.load(open(args.manifest))
    from llama_cpp import Llama
    print(f"Loading {args.gguf} ...")
    llm = Llama(model_path=args.gguf, n_gpu_layers=-1, n_ctx=args.n_ctx, verbose=False)

    shown = 0
    for s in manifest.get("samples", []):
        if shown >= args.n:
            break
        by_cid = {c["condition_id"]: c for c in s.get("conditions", [])}
        # Condition 1 = (Original, Original, Real), Condition 2 = (Original, Original, Synthetic)
        real_c, synth_c = by_cid.get(1), by_cid.get(2)
        if not real_c or not synth_c:
            continue
        if real_c.get("status") != "ok" or synth_c.get("status") != "ok":
            continue

        print("=" * 78)
        print(f"SAMPLE {s.get('sample_index')}")
        print("=" * 78)

        for label, built in [("REAL (C1)", real_c), ("SYNTHETIC (C2)", synth_c)]:
            code = built["source_code"]
            stdin_cases = built.get("stdin_cases") or s.get("stdin_cases")
            if not stdin_cases:
                continue
            stdin_text = stdin_cases[0]
            expected, err = ground_truth(code, stdin_text)
            if err is not None:
                print(f"--- {label}: program does not run ({err[:80]}) ---")
                continue

            prompt = PROMPT_TEMPLATE.format(code=code.strip(), stdin=stdin_text.strip())
            out = llm(prompt, max_tokens=64, temperature=0.0,
                      stop=["\n# Program:", "\n# Input:", "\n\n\n"])
            pred = out["choices"][0]["text"]
            correct = normalize(pred) == normalize(expected)

            print(f"--- {label} ---")
            print("PROGRAM:")
            print(code[:400])
            print(f"INPUT: {stdin_text.strip()!r}")
            print(f"EXPECTED: {expected.strip()!r}")
            print(f"MODEL PREDICTED: {pred.strip()!r}")
            print(f"CORRECT: {correct}")
            print()

        shown += 1


if __name__ == "__main__":
    main()