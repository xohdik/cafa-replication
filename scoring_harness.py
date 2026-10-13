"""
Scoring harness: run the model over every built condition and emit the
response matrix the Sobol/ANOVA estimator consumes.

=== WHY OUTPUT PREDICTION, AND NOT THE ALTERNATIVES ===

The task is: given a program and its stdin, predict its stdout. Scored by
exact match after whitespace normalization.

PERPLEXITY WAS REJECTED, not merely judged weaker. Perplexity on a perturbed
program is dominated by surface token statistics: renaming identifiers to
`var_0`, `var_1` raises perplexity sharply whether or not the model
understands anything about the program. S_i(lexical) would then be large by
construction, measuring the tokenizer rather than the model. A metric whose
response to an intervention is guaranteed regardless of capability cannot
decompose capability.

GENERATION pass@1 WAS REJECTED for fit: the corpus contains complete programs
with test cases, not natural-language prompts with reference solutions.
Constructing a generation task would require inventing prompts, which adds a
prompt-quality factor outside the design.

OUTPUT PREDICTION fits the available data exactly, is deterministic to score,
and every factor in the design bears on it directly: a model that has
memorized a program can recall its output; one relying on identifier
semantics loses ground when they are stripped; one relying on statement order
loses ground when independent statements are permuted.

KNOWN LIMITATION worth stating in the paper: output prediction measures
program comprehension, not program synthesis. A decomposition of comprehension
need not transfer to generation, and the paper should scope its claim
accordingly rather than saying "code intelligence" unqualified.

=== v2: CHECKPOINT/RESUME AND OVERSIZED-PROMPT HANDLING ===

A real run crashed at 2850/11544 (~25% through, ~17 minutes of GPU time) on
"Requested tokens (7664) exceed context window of 4096" -- one real
program's source, embedded in the few-shot prompt, produced a prompt longer
than the model's context. v1 had no guard against this and no way to resume,
so the crash discarded everything already scored.

Two independent fixes, because they address different failure classes:

1. Context-window handling: n_ctx default raised to 8192 (the real corpus's
   measured tail reaches 202 lines; 4096 was sized for the median case, not
   the tail). A best-effort pre-flight token count skips oversized samples
   before generation (cheaper than attempting and failing), wrapped in
   try/except since the exact tokenize() signature could not be verified
   against the actual llama-cpp-python install from this environment. A
   catch-all around the model call itself is the real safety net: it skips
   and logs ANY per-sample failure (context overflow or otherwise) rather
   than crashing the run, because a pre-check tuned to one known failure
   mode does not protect against the next one.

2. Checkpointing: progress is written to a checkpoint file after every N
   completed (sample, condition) pairs -- not just at the end -- and
   --resume loads it back and skips whatever pairs are already done. A
   long-running GPU job should never lose more than a few pairs' worth of
   work to any single failure, expected or not.

Usage:
    python3 scoring_harness.py --manifest manifest.json \\
        --gguf ./models/deepseek-coder-6.7b-base.Q4_K_M.gguf \\
        --reps 3 --out responses.json

    # resume after a crash or interruption, same command plus:
    python3 scoring_harness.py --manifest manifest.json \\
        --gguf ./models/deepseek-coder-6.7b-base.Q4_K_M.gguf \\
        --reps 3 --out responses.json --resume
"""
from __future__ import annotations
import argparse
import json
import os
import re
import sys
import time
import warnings

warnings.filterwarnings("ignore", category=SyntaxWarning)

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "perturbations"))

from ast_shuffle import _run_script


PROMPT_TEMPLATE = """# Predict the exact standard output of each Python program.

# Program:
n = int(input())
print(n * 2)
# Input:
5
# Output:
10

# Program:
{code}
# Input:
{stdin}
# Output:
"""


def normalize(s: str) -> str:
    """Whitespace-normalized comparison. Trailing-newline and trailing-space
    conventions are not semantic differences, and counting them as errors
    would add noise uncorrelated with any factor in the design."""
    if s is None:
        return ""
    return "\n".join(line.rstrip() for line in s.strip().splitlines())


def ground_truth(code: str, stdin_text: str, timeout: float = 5.0):
    """Execute the program to obtain the reference output. Computed per
    condition rather than taken from the corpus, because the perturbed
    program is what the model is being scored on -- if a perturbation
    changed behavior, the reference must change with it or the score would
    penalize the model for the operator's error."""
    out, err = _run_script(code, stdin_text, timeout)
    return (None, err) if err else (out, None)


def prompt_too_long(llm, prompt: str, max_tokens: int, n_ctx: int) -> bool:
    """Best-effort pre-flight check. Returns False (assume it fits) on any
    failure to introspect the tokenizer, rather than block scoring on an
    unverified API call -- the catch-all around the actual model call in
    score_one() is the real safety net regardless of whether this succeeds."""
    try:
        n_tokens = len(llm.tokenize(prompt.encode("utf-8")))
        return (n_tokens + max_tokens) > n_ctx
    except Exception:
        return False


def score_one(llm, code: str, stdin_text: str, expected: str,
              max_tokens: int = 64, temperature: float = 0.0,
              n_ctx: int = 8192) -> dict:
    prompt = PROMPT_TEMPLATE.format(code=code.strip(), stdin=stdin_text.strip())

    if prompt_too_long(llm, prompt, max_tokens, n_ctx):
        return {"status": "skipped_too_long", "correct": None}

    try:
        out = llm(prompt, max_tokens=max_tokens, temperature=temperature,
                  stop=["\n# Program:", "\n# Input:", "\n\n\n"])
    except Exception as e:
        # Catch-all, not just context-overflow: any per-sample model failure
        # skips that sample rather than killing an hour of GPU time on one
        # bad input. The exact exception is logged so a recurring cause can
        # still be diagnosed rather than silently masked.
        return {"status": f"error: {type(e).__name__}: {str(e)[:150]}", "correct": None}

    pred = out["choices"][0]["text"]
    return {
        "status": "ok",
        "prediction": pred[:300],
        "expected": expected[:300],
        "correct": normalize(pred) == normalize(expected),
    }


def _checkpoint_path(out_path: str) -> str:
    return out_path + ".checkpoint"


def load_checkpoint(out_path: str):
    path = _checkpoint_path(out_path)
    if not os.path.exists(path):
        return None
    with open(path) as f:
        data = json.load(f)
    data["completed_pairs"] = {tuple(p) for p in data["completed_pairs"]}
    return data


def save_checkpoint(out_path: str, per_condition: dict, completed_pairs: set,
                     n_scored: int, n_skipped: int, error_log: list,
                     attempt_counts: dict = None, per_sample_results: dict = None):
    path = _checkpoint_path(out_path)
    tmp = path + ".tmp"
    data = {
        "per_condition": per_condition,
        "completed_pairs": sorted(list(completed_pairs)),
        "attempt_counts": attempt_counts or {},
        "per_sample_results": per_sample_results or {},
        "n_scored": n_scored,
        "n_skipped": n_skipped,
        "error_log": error_log[-100:],  # bounded, not unlimited
    }
    with open(tmp, "w") as f:
        json.dump(data, f)
    os.replace(tmp, path)  # atomic on POSIX -- no torn/partial checkpoint file


def run(manifest: dict, llm, reps: int = 3, temperature: float = 0.0,
        progress_every: int = 25, n_ctx: int = 8192, out_path: str = "responses.json",
        resume: bool = False, checkpoint_every: int = 10,
        max_attempts: int = 3) -> dict:
    per_condition = {}
    per_sample_results = {}
    completed_pairs = set()
    attempt_counts = {}
    n_scored = n_skipped = 0
    error_log = []
    t0 = time.time()

    if resume:
        ck = load_checkpoint(out_path)
        if ck:
            per_condition = ck["per_condition"]
            per_sample_results = ck.get("per_sample_results", {})
            completed_pairs = ck["completed_pairs"]
            attempt_counts = ck.get("attempt_counts", {})
            n_scored = ck["n_scored"]
            n_skipped = ck["n_skipped"]
            error_log = ck["error_log"]
            print(f"Resumed from checkpoint: {len(completed_pairs)} pairs already "
                  f"done, {n_scored} scored, {n_skipped} skipped.", flush=True)
        else:
            print("--resume given but no checkpoint found; starting fresh.", flush=True)

    samples = manifest.get("samples", [])
    total_pairs = sum(len(s.get("conditions", [])) for s in samples)
    done_pairs = len(completed_pairs)
    since_checkpoint = 0

    for s in samples:
        sample_idx = s.get("sample_index")
        for built in s.get("conditions", []):
            cid = built["condition_id"]
            pair_key = (sample_idx, cid)
            per_condition.setdefault(str(cid), [[] for _ in range(reps)])

            if pair_key in completed_pairs:
                continue

            if built.get("status") != "ok" or not built.get("source_code"):
                n_skipped += 1
                completed_pairs.add(pair_key)
                done_pairs += 1
                continue

            code = built["source_code"]
            stdin_cases = built.get("stdin_cases") or s.get("stdin_cases")
            if not stdin_cases:
                n_skipped += 1
                completed_pairs.add(pair_key)
                done_pairs += 1
                continue
            stdin_text = stdin_cases[0]

            expected, err = ground_truth(code, stdin_text)
            if err is not None:
                n_skipped += 1
                completed_pairs.add(pair_key)
                done_pairs += 1
                continue

            pair_results = []  # (rep_index, correct_or_None, status)
            pair_fully_resolved = True
            for r in range(reps):
                res = score_one(llm, code, stdin_text, expected,
                                temperature=temperature, n_ctx=n_ctx)
                if res["status"] == "ok":
                    pair_results.append((r, 1.0 if res["correct"] else 0.0))
                elif res["status"] == "skipped_too_long":
                    # Deterministic: the prompt is identical across reps of the
                    # same pair (only temperature differs, which does not
                    # change prompt length), so this fails identically on
                    # retry. Safe to treat as permanent -- contributes no
                    # score, but does not block the pair from being marked
                    # complete.
                    error_log.append({"sample_index": sample_idx, "condition_id": cid,
                                      "rep": r, "reason": res["status"]})
                else:
                    # Generic model-call failure. NOT assumed permanent --
                    # could be a transient GPU/driver hiccup. The whole pair
                    # is discarded (not partially committed) and retried in
                    # full on --resume. Committing partial results here and
                    # retrying later would double-count the reps that DID
                    # succeed -- confirmed by test: buffering per-pair and
                    # committing atomically is what avoids that.
                    pair_fully_resolved = False
                    error_log.append({"sample_index": sample_idx, "condition_id": cid,
                                      "rep": r, "reason": res["status"]})

            if pair_fully_resolved:
                for r, val in pair_results:
                    per_condition[str(cid)][r].append(val)
                    n_scored += 1
                n_skipped += (reps - len(pair_results))
                completed_pairs.add(pair_key)
                attempt_counts.pop(str(pair_key), None)
                # Per-sample persistence, added after the first stratified
                # reanalysis attempt discovered responses.json only ever
                # stored condition-level aggregates -- there was no way to
                # ask "how did THIS sample do under THIS condition" after
                # the fact, which blocked subgroup analysis (e.g. by loop
                # nesting depth) without a fresh re-score. Committed at the
                # same atomic point as per_condition, so it inherits the
                # same crash/resume correctness guarantees rather than
                # introducing a second, unverified commit path.
                per_sample_results.setdefault(str(sample_idx), {})[str(cid)] = \
                    [val for r, val in pair_results]
            else:
                # Do not commit ANY of this pair's results and do not mark it
                # complete -- next --resume retries the whole pair cleanly.
                # Committing partial results and retrying later would
                # double-count the reps that DID succeed.
                #
                # BUT: bound the retries. A failure classified as "transient"
                # might actually be deterministic for this particular sample,
                # in which case retrying forever would mean --resume never
                # terminates. After max_attempts, give up on the pair and mark
                # it complete-with-no-data so the run can finish. Confirmed
                # necessary by test: with a failure affecting one rep of every
                # pair, zero pairs completed and the run made no forward
                # progress across resumes.
                key = str(pair_key)
                attempt_counts[key] = attempt_counts.get(key, 0) + 1
                n_skipped += len(pair_results)
                if attempt_counts[key] >= max_attempts:
                    completed_pairs.add(pair_key)
                    error_log.append({"sample_index": sample_idx, "condition_id": cid,
                                      "rep": -1,
                                      "reason": f"gave up after {max_attempts} attempts"})

            done_pairs += 1
            since_checkpoint += 1

            if progress_every and done_pairs % progress_every == 0:
                el = time.time() - t0
                print(f"  ...{done_pairs}/{total_pairs} pairs "
                      f"({n_scored} scored, {n_skipped} skipped) "
                      f"({el:.0f}s elapsed)", flush=True)

            if checkpoint_every and since_checkpoint >= checkpoint_every:
                save_checkpoint(out_path, per_condition, completed_pairs,
                                n_scored, n_skipped, error_log, attempt_counts,
                                per_sample_results)
                since_checkpoint = 0

    # Final checkpoint save, so a resume right after a clean finish is also safe.
    save_checkpoint(out_path, per_condition, completed_pairs, n_scored, n_skipped,
                    error_log, attempt_counts, per_sample_results)

    matrix = {}
    for cid, reps_lists in sorted(per_condition.items(), key=lambda kv: int(kv[0])):
        matrix[cid] = [(sum(v) / len(v)) if v else None for v in reps_lists]

    return {
        "response_matrix": matrix,
        "per_sample_results": per_sample_results,
        "n_scored": n_scored,
        "n_skipped": n_skipped,
        "reps": reps,
        "elapsed_seconds": time.time() - t0,
        "error_log_tail": error_log[-20:],
    }


def to_numpy_matrix(result: dict):
    """(n_conditions, reps) array in condition order, for sobol_anova."""
    import numpy as np
    cids = sorted(result["response_matrix"], key=int)
    rows = []
    for cid in cids:
        row = result["response_matrix"][cid]
        if any(v is None for v in row):
            raise ValueError(
                f"Condition {cid} has no scored samples in at least one "
                f"replicate. The decomposition cannot be computed with a "
                f"missing cell -- check the manifest audit and the skip count.")
        rows.append(row)
    return np.array(rows)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--gguf", required=True)
    ap.add_argument("--reps", type=int, default=3,
                    help="Replicate seeds per condition. Replicates vary the "
                         "sampling temperature draw; at temperature 0 they "
                         "differ only through the stochastic operators, so "
                         "the bootstrap CI reflects operator variance.")
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--out", default="responses.json")
    ap.add_argument("--n-ctx", type=int, default=8192,
                    help="Raised from 4096 after a real crash: the corpus's "
                         "measured tail (max 202 lines) can produce prompts "
                         "exceeding 4096 tokens once embedded in the few-shot "
                         "template.")
    ap.add_argument("--resume", action="store_true",
                    help="Resume from <out>.checkpoint if present, skipping "
                         "(sample, condition) pairs already completed.")
    ap.add_argument("--checkpoint-every", type=int, default=10,
                    help="Write a checkpoint after this many completed pairs. "
                         "Lower = safer against crashes, higher = less I/O "
                         "overhead relative to the size of a run like this.")
    ap.add_argument("--max-attempts", type=int, default=3,
                    help="Give up on a (sample, condition) pair after this "
                         "many failed attempts across resumes, so a "
                         "deterministically-failing sample cannot block the "
                         "run from ever completing.")
    args = ap.parse_args()

    with open(args.manifest) as f:
        manifest = json.load(f)

    from llama_cpp import Llama
    print(f"Loading {args.gguf} (n_ctx={args.n_ctx}) ...")
    llm = Llama(model_path=args.gguf, n_gpu_layers=-1, n_ctx=args.n_ctx,
                verbose=False)

    result = run(manifest, llm, reps=args.reps, temperature=args.temperature,
                 n_ctx=args.n_ctx, out_path=args.out, resume=args.resume,
                 checkpoint_every=args.checkpoint_every,
                 max_attempts=args.max_attempts)

    with open(args.out, "w") as f:
        json.dump(result, f, indent=2)

    print(f"\nscored={result['n_scored']}  skipped={result['n_skipped']}  "
          f"elapsed={result['elapsed_seconds']:.0f}s")
    if result["n_skipped"]:
        print(f"\nLast {len(result['error_log_tail'])} skip reasons "
              f"(full log in {args.out}.checkpoint):")
        for e in result["error_log_tail"]:
            print(f"  sample={e['sample_index']} cond={e['condition_id']} "
                  f"rep={e['rep']}: {e['reason']}")

    print("\nPer-condition accuracy (mean over replicates):")
    for cid in sorted(result["response_matrix"], key=int):
        row = result["response_matrix"][cid]
        vals = [v for v in row if v is not None]
        mean = sum(vals) / len(vals) if vals else float("nan")
        print(f"  C{cid:<3} {mean:.3f}   {['%.3f' % v if v is not None else 'na' for v in row]}")

    print(f"\nWritten to {args.out}")
    print(f"Checkpoint retained at {args.out}.checkpoint (safe to delete once "
          f"you have the final {args.out} and are done with this run).")
    print(f"Next: python3 analysis/decompose.py --responses {args.out}")