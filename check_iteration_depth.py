"""
Test the hypothesis that synthetic-condition accuracy is driven by loop
ITERATION COUNT (long sequential arithmetic accumulation), not by
"artificiality" recognition per se. Buckets real corpus samples' C2
(Original,Original,Synthetic) programs by nested for-loop depth (0, 1, 2),
scores a capped sample from each bucket, and reports accuracy per bucket.

If accuracy drops sharply as depth increases (0 -> 1 -> 2 nested loops,
i.e. 1 -> n -> n^2 required accumulation steps), that supports iteration
count as the driver. If accuracy is flat across depths, that points back
toward artificiality/surface-form recognition instead.

Usage:
    python3 check_iteration_depth.py --manifest manifest.json \\
        --gguf ./models/deepseek-coder-6.7b-base.Q4_K_M.gguf --per-bucket 25
"""
import argparse
import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "perturbations"))

from scoring_harness import PROMPT_TEMPLATE, ground_truth, normalize


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--gguf", required=True)
    ap.add_argument("--per-bucket", type=int, default=25,
                    help="Max samples to score per loop-depth bucket.")
    ap.add_argument("--n-ctx", type=int, default=8192)
    args = ap.parse_args()

    manifest = json.load(open(args.manifest))
    from llama_cpp import Llama
    print(f"Loading {args.gguf} ...")
    llm = Llama(model_path=args.gguf, n_gpu_layers=-1, n_ctx=args.n_ctx, verbose=False)

    buckets = defaultdict(list)  # depth -> [(code, stdin, sample_index), ...]
    for s in manifest.get("samples", []):
        for c in s.get("conditions", []):
            if c["condition_id"] != 2:  # Original, Original, Synthetic
                continue
            if c.get("status") != "ok" or not c.get("source_code"):
                continue
            depth = c["source_code"].count("for i_")
            stdin_cases = c.get("stdin_cases") or s.get("stdin_cases")
            if not stdin_cases:
                continue
            buckets[depth].append((c["source_code"], stdin_cases[0], s.get("sample_index")))

    print("Bucket sizes (total available):", {d: len(v) for d, v in sorted(buckets.items())})
    print()

    results = {}
    for depth in sorted(buckets):
        items = buckets[depth][:args.per_bucket]
        n_correct = n_scored = n_skipped = 0
        for code, stdin_text, sample_idx in items:
            expected, err = ground_truth(code, stdin_text)
            if err is not None:
                n_skipped += 1
                continue
            prompt = PROMPT_TEMPLATE.format(code=code.strip(), stdin=stdin_text.strip())
            try:
                out = llm(prompt, max_tokens=64, temperature=0.0,
                          stop=["\n# Program:", "\n# Input:", "\n\n\n"])
            except Exception:
                n_skipped += 1
                continue
            pred = out["choices"][0]["text"]
            n_scored += 1
            if normalize(pred) == normalize(expected):
                n_correct += 1

        acc = n_correct / n_scored if n_scored else float("nan")
        results[depth] = (acc, n_scored, n_skipped)
        print(f"depth={depth} nested for-loops: accuracy={acc:.3f} "
              f"({n_correct}/{n_scored} scored, {n_skipped} skipped)")

    print()
    print("INTERPRETATION")
    accs = [results[d][0] for d in sorted(results) if results[d][1] > 0]
    if len(accs) >= 2 and accs == sorted(accs, reverse=True):
        print("  Accuracy strictly DECREASES with loop depth -- supports the")
        print("  'long sequential accumulation is hard' hypothesis over pure")
        print("  artificiality recognition.")
    elif len(accs) >= 2 and max(accs) - min(accs) < 0.05:
        print("  Accuracy is roughly FLAT across depths -- does not support")
        print("  iteration count as the primary driver; points back toward")
        print("  surface-form/artificiality recognition or another mechanism.")
    else:
        print("  Mixed pattern -- inspect the per-bucket numbers directly")
        print("  rather than trust either hypothesis by default.")


if __name__ == "__main__":
    main()