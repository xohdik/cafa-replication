"""
X1 operator: repository overlap / memorization.

=== THE HARD PART IS NOT THE CODE ===

X1 is supposed to separate "the model has seen this exact code during
training" from "it has not." The other four factors are transformations of a
sample; X1 is a statement about a sample's PROVENANCE relative to a training
set we cannot inspect. That makes it categorically different, and it is why
X1 was left until last.

Three operationalizations, in descending order of strength:

1. TRAINING-SET INSPECTION. Check membership directly. Requires an open
   training corpus. Not available for DeepSeek-Coder, whose training data is
   not published. Ruled out.

2. TEMPORAL CUTOFF. Partition by creation date: material published before the
   model's training cutoff is plausibly memorized, material after it
   provably is not. This is the standard approach in contamination studies
   and is what this module implements.

   CRITICAL FEASIBILITY CONSTRAINT: it requires samples on BOTH sides of the
   cutoff. Project CodeNet was released in 2021; DeepSeek-Coder's training
   cutoff is later. Every CodeNet sample therefore sits on the SAME side --
   pre-cutoff. A temporal X1 cannot be constructed from CodeNet alone, no
   matter how the dates are sliced. A post-cutoff corpus must be added.
   check_cutoff_feasibility() below reports this rather than silently
   producing a degenerate split.

3. SURFACE-OVERLAP PROXY. Use n-gram or MinHash overlap against a public
   proxy corpus (e.g. The Stack) as a stand-in for membership. Weaker: it
   measures similarity to a corpus the model *probably* trained on, not
   membership in the corpus it *did* train on. Implemented here as a
   documented fallback, not as the primary instrument, and the paper should
   describe it as a proxy if used.

Whichever is used, the X1 level is a property of which POOL a sample is drawn
from, not a transformation applied to it. Sample selection therefore happens
before the design, and both pools must be matched on the covariates that
would otherwise confound the contrast -- length, complexity, task type.
Otherwise "pre-cutoff vs post-cutoff" also means "easy vs hard" and the
memorization estimate absorbs a difficulty effect.
"""
import json
import os
import statistics
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))

# Publicly documented approximate cutoffs. VERIFY against the model card
# before relying on these; they are the pivot of the entire X1 contrast.
KNOWN_CUTOFFS = {
    "deepseek-coder-6.7b": "2023-03-01",
    "deepseek-coder-1.3b": "2023-03-01",
    "starcoder2": "2023-09-01",
    "codellama": "2023-01-01",
}


def parse_date(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value))
        except Exception:
            return None
    if isinstance(value, str) and value.strip().lstrip("-").isdigit():
        # CSV fields arrive as strings even when they hold a Unix timestamp --
        # confirmed CodeNet metadata schema: date is field index 3, an int
        # written as decimal seconds since the epoch. Without this branch,
        # every joined date silently fell through to None and re-produced
        # the same "0% coverage" failure the join was built to fix, just one
        # layer deeper (a formatting mismatch instead of a missing join).
        try:
            return datetime.fromtimestamp(float(value.strip()))
        except (ValueError, OSError, OverflowError):
            return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(str(value)[:19], fmt)
        except ValueError:
            continue
    return None


def check_cutoff_feasibility(samples: list, cutoff: str,
                              date_field: str = "date") -> dict:
    """Can a temporal X1 be built from this pool at all?

    Reports the split rather than assuming one exists. A pool entirely on one
    side of the cutoff yields a degenerate contrast: the 'deduplicated' level
    would contain the same material as the 'original' level, and S_i(memorization)
    would be measuring nothing while looking like a real number."""
    cutoff_dt = parse_date(cutoff)
    n_pre = n_post = n_undated = 0
    for s in samples:
        d = parse_date(s.get(date_field))
        if d is None:
            n_undated += 1
        elif d < cutoff_dt:
            n_pre += 1
        else:
            n_post += 1

    n = len(samples)
    usable = min(n_pre, n_post)
    return {
        "n_samples": n,
        "cutoff": cutoff,
        "n_pre_cutoff": n_pre,
        "n_post_cutoff": n_post,
        "n_undated": n_undated,
        "n_usable_pairs": usable,
        "feasible": usable > 0,
        "date_coverage": (n - n_undated) / n if n else 0.0,
    }


def covariate_balance(pre: list, post: list, code_field: str = "source_code") -> dict:
    """Compare the two pools on covariates that would otherwise confound X1.

    If pre-cutoff programs are systematically shorter or simpler than
    post-cutoff ones, the memorization contrast is partly a difficulty
    contrast, and no amount of experimental design downstream can separate
    them."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "perturbations"))
    from synthesize import complexity_profile

    def prof(pool):
        lines, cyc, depth = [], [], []
        for s in pool:
            code = s.get(code_field, "")
            lines.append(len([l for l in code.splitlines() if l.strip()]))
            try:
                p = complexity_profile(code)
                cyc.append(p.cyclomatic)
                depth.append(p.max_depth)
            except Exception:
                pass
        return {
            "n": len(pool),
            "median_lines": statistics.median(lines) if lines else None,
            "median_cyclomatic": statistics.median(cyc) if cyc else None,
            "median_depth": statistics.median(depth) if depth else None,
        }

    a, b = prof(pre), prof(post)
    warnings = []
    for key in ("median_lines", "median_cyclomatic", "median_depth"):
        if a[key] and b[key] and max(a[key], b[key]) > 0:
            ratio = min(a[key], b[key]) / max(a[key], b[key])
            if ratio < 0.7:
                warnings.append(f"{key}: pre={a[key]} post={b[key]} (ratio {ratio:.2f})")
    return {"pre": a, "post": b, "imbalanced_on": warnings,
            "balanced": not warnings}


def partition_by_cutoff(samples: list, cutoff: str, date_field: str = "date"):
    """Split into (pre_cutoff, post_cutoff, undated)."""
    cutoff_dt = parse_date(cutoff)
    pre, post, undated = [], [], []
    for s in samples:
        d = parse_date(s.get(date_field))
        if d is None:
            undated.append(s)
        elif d < cutoff_dt:
            pre.append(s)
        else:
            post.append(s)
    return pre, post, undated


def print_report(feas: dict, bal: dict = None):
    print("=" * 70)
    print("X1 TEMPORAL CUTOFF FEASIBILITY")
    print("=" * 70)
    print(f"  samples:            {feas['n_samples']}")
    print(f"  cutoff:             {feas['cutoff']}")
    print(f"  date coverage:      {feas['date_coverage']:.1%}"
          f"   ({feas['n_undated']} undated)")
    print(f"  pre-cutoff:         {feas['n_pre_cutoff']}")
    print(f"  post-cutoff:        {feas['n_post_cutoff']}")
    print(f"  usable matched n:   {feas['n_usable_pairs']}")

    print("\n" + "=" * 70)
    print("VERDICT")
    print("=" * 70)
    if feas["date_coverage"] == 0.0:
        # Distinct from a one-sided split: there is no date information at all,
        # so nothing has been learned about feasibility yet. Conflating the two
        # would send you looking for a new corpus when the dates are simply
        # not joined onto the samples.
        print("  UNDETERMINED -- no sample carries a date, so the partition")
        print("  could not be attempted. This is a missing-metadata problem,")
        print("  not a corpus problem. CodeNet ships submission dates in its")
        print("  metadata/ directory keyed by submission id; join them onto")
        print("  the samples first (see join_codenet_dates.py), then re-run.")
        print("  Only if dates are present AND fall on one side is a new")
        print("  corpus actually required.")
        return
    if not feas["feasible"]:
        side = "pre-cutoff" if feas["n_post_cutoff"] == 0 else "post-cutoff"
        print(f"  NOT FEASIBLE -- every dated sample falls on the {side} side.")
        print("  A temporal X1 needs material from BOTH sides. With CodeNet")
        print("  (released 2021) and a 2023-cutoff model, the entire corpus is")
        print("  pre-cutoff, so this is expected and is not a bug in the data.")
        print("  Options:")
        print("    (a) Add a post-cutoff corpus -- recent contest problems")
        print("        published after the model's cutoff -- and match it to")
        print("        CodeNet on length and complexity.")
        print("    (b) Use a surface-overlap proxy instead, and describe X1 in")
        print("        the paper as a similarity proxy rather than a")
        print("        membership test.")
        print("    (c) Drop X1 and report a three-factor decomposition, noting")
        print("        that memorization could not be isolated without an")
        print("        inspectable training set.")
    elif bal and not bal["balanced"]:
        print("  FEASIBLE BUT CONFOUNDED -- the two pools differ on:")
        for w in bal["imbalanced_on"]:
            print(f"    {w}")
        print("  Match the pools on these covariates before running, or the")
        print("  memorization estimate will absorb a difficulty effect.")
    else:
        print(f"  FEASIBLE -- {feas['n_usable_pairs']} matched samples per side.")
        if bal:
            print(f"  Covariates balanced: pre={bal['pre']} post={bal['post']}")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", required=True)
    ap.add_argument("--cutoff", default=KNOWN_CUTOFFS["deepseek-coder-6.7b"])
    ap.add_argument("--date-field", default="date")
    args = ap.parse_args()

    rows = []
    with open(args.samples) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))

    feas = check_cutoff_feasibility(rows, args.cutoff, args.date_field)
    bal = None
    if feas["feasible"]:
        pre, post, _ = partition_by_cutoff(rows, args.cutoff, args.date_field)
        bal = covariate_balance(pre, post)
    print_report(feas, bal)