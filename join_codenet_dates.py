"""
Join CodeNet submission dates onto samples, so X1's temporal partition can be
attempted at all.

The X1 feasibility check reported 0% date coverage on a 500-sample pool: not
because the corpus lacks dates, but because the pairs file does not carry
them. CodeNet stores per-submission metadata in

    Project_CodeNet/metadata/<problem_id>.csv

with one row per submission, keyed by submission_id, including a date field.
The EMSE pairs retain `correct_sub_id`, so the join is direct.

Usage:
    python3 join_codenet_dates.py \\
        --samples rq4_samples_verified.jsonl \\
        --codenet PATH/TO/Project_CodeNet \\
        --output rq4_samples_dated.jsonl
"""
from __future__ import annotations
import argparse
import csv
import json
import os
import re
from collections import defaultdict

# Confirmed anonymization pattern from CodeNet's own documentation:
# "submission ids are anonymized and follow this pattern: s[0-9]{9}"
SUBMISSION_ID_RE = re.compile(r"s\d{9}")


def extract_id_from_pair_id(pair_id) -> str | None:
    """Fallback when the named --id-field is missing or None.

    join_codenet_tests.py (the script that built rq4_samples_verified.jsonl)
    never carried correct_sub_id/buggy_sub_id through from the original
    pairs file -- it only wrote source_code, pair_id, problem_id, field, and
    stdin_cases. The submission id is still recoverable because pair_id
    embeds it, e.g. "codenet_p03312_s595608579".

    CAVEAT, stated rather than assumed away: it is not fully confirmed
    whether pair_id always embeds the CORRECT submission's id or the BUGGY
    one -- an earlier inspected example matched buggy_sub_id. For a sample
    built with field="correct_code", this fallback may therefore date the
    wrong side of the pair. This is an approximation, not a fix on the same
    footing as a real join; regenerating rq4_samples_verified.jsonl with
    correct_sub_id/buggy_sub_id carried through (a one-line change to
    join_codenet_tests.py) gives an exact join and should replace this
    fallback before the number is used in the paper."""
    if not pair_id:
        return None
    m = SUBMISSION_ID_RE.search(str(pair_id))
    return m.group(0) if m else None


def load_problem_dates(codenet_root: str, problem_id: str) -> dict:
    """submission_id -> unix timestamp string, for one problem.

    Schema confirmed from IBM's own documentation, no header row:
        submission_id,problem_id,user_id,date,language,original_language,
        filename_ext,status,cpu_time,memory,code_size,accuracy
    `date` is field index 3 (0-indexed), Unix timestamp in seconds. Earlier
    versions of this loader guessed at column names from several possible
    schemas; this is the confirmed one, so guessing is no longer needed."""
    path = os.path.join(codenet_root, "metadata", f"{problem_id}.csv")
    if not os.path.isfile(path):
        return {}
    out = {}
    try:
        with open(path, newline="", errors="replace") as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) < 4:
                    continue
                sid, date = row[0], row[3]
                if sid and date:
                    out[sid] = date
    except OSError:
        return {}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", required=True)
    ap.add_argument("--codenet", required=True)
    ap.add_argument("--output", default="rq4_samples_dated.jsonl")
    ap.add_argument("--id-field", default="correct_sub_id")
    args = ap.parse_args()

    rows = []
    with open(args.samples) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))

    by_problem = defaultdict(list)
    for r in rows:
        by_problem[r.get("problem_id")].append(r)

    n_dated = 0
    n_dated_via_fallback = 0
    n_no_meta = 0
    n_no_id_at_all = 0
    for pid, group in by_problem.items():
        if not pid:
            continue
        dates = load_problem_dates(args.codenet, pid)
        if not dates:
            n_no_meta += len(group)
            continue
        for r in group:
            sid = r.get(args.id_field)
            via_fallback = False
            if not sid:
                sid = extract_id_from_pair_id(r.get("pair_id"))
                via_fallback = True
            if not sid:
                n_no_id_at_all += 1
                continue
            if sid in dates:
                r["date"] = dates[sid]
                r["date_source"] = "pair_id_fallback" if via_fallback else args.id_field
                n_dated += 1
                if via_fallback:
                    n_dated_via_fallback += 1

    with open(args.output, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")

    n = len(rows)
    print(json.dumps({
        "n_samples": n,
        "n_dated": n_dated,
        "n_dated_via_named_field": n_dated - n_dated_via_fallback,
        "n_dated_via_pair_id_fallback": n_dated_via_fallback,
        "date_coverage": round(n_dated / n, 4) if n else 0.0,
        "n_missing_problem_metadata": n_no_meta,
        "n_no_id_recoverable": n_no_id_at_all,
        "output": args.output,
    }, indent=2))
    if n_dated_via_fallback:
        print(f"\nNOTE: {n_dated_via_fallback}/{n_dated} dated samples used the "
              f"pair_id fallback (--id-field '{args.id_field}' was absent). "
              f"See the caveat in extract_id_from_pair_id()'s docstring before "
              f"relying on this for the paper -- regenerating "
              f"rq4_samples_verified.jsonl with correct_sub_id carried through "
              f"gives an exact join instead.")
    if n_dated == 0:
        print("\nNo dates joined. Check the metadata layout:")
        print(f"  ls {os.path.join(args.codenet, 'metadata')} | head")
        print("  head -2 <one of those .csv files>")
        print("Then set --id-field to whichever column matches the pairs file.")
    else:
        print(f"\nNext: python3 x1_cutoff.py --samples {args.output} --cutoff 2023-03-01")


if __name__ == "__main__":
    main()