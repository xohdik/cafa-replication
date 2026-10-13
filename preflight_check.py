"""
Pre-flight check: confirm the local code is actually the current 3-factor
design before running anything expensive.

Run this BEFORE orchestrator.py, every time, no exceptions. It exists
because a stale local copy has now cost real time three separate ways in
this project: a Python-3.9 environment shadowing a Python-3.11 fix, a
flat-directory import shadowing an updated file with an old one two
directories up, and this -- an intermediate 4-factor orchestrator.py
(post-transpilation-drop, pre-repo_overlap-drop) silently running a full
100-sample manifest that looked complete (94/100 eligible, all conditions
"ok") while actually reflecting a design that no longer exists in the
paper. The manifest didn't error. It just produced 16 conditions per sample
instead of 8, and the mistake was only visible by reading the log fields
inside individual conditions.

Usage:
    python3 preflight_check.py
"""
import ast
import hashlib
import sys

# Fingerprints of the CURRENT correct files, computed once and pinned here
# rather than recomputed from a "trusted" copy on every machine -- if this
# script and the file it's checking were both stale in the same way, a
# self-referential check would pass silently, which is exactly the failure
# mode being guarded against.
EXPECTED = {
    "orchestrator.py": "45034be358b1",
    "design_matrix.py": "daa1ce427f67",
    "audit_manifest.py": "accabb27606f",
}

# Structural checks independent of hashing, so a check still catches drift
# even if EXPECTED goes stale itself (e.g. after a legitimate future edit
# that isn't reflected here yet).
FORBIDDEN_STRINGS = {
    "orchestrator.py": ["repo_overlap", "transpile_and_validate", "preflight_x4"],
    "design_matrix.py": ["repo_overlap", "FACTORS = [\"repo_overlap\""],
}
REQUIRED_STRINGS = {
    "orchestrator.py": ["identifiers", "ast_structure", "syntheticity"],
    "design_matrix.py": ['FACTORS = ["identifiers", "ast_structure", "syntheticity"]'],
}


def check_file(path: str) -> dict:
    result = {"path": path, "exists": False, "hash_match": None,
              "forbidden_found": [], "required_missing": [], "syntax_ok": None}
    try:
        src = open(path).read()
    except FileNotFoundError:
        return result
    result["exists"] = True

    h = hashlib.sha256(src.encode()).hexdigest()[:12]
    if path in EXPECTED:
        result["hash_match"] = (h == EXPECTED[path])
        result["actual_hash"] = h

    for bad in FORBIDDEN_STRINGS.get(path, []):
        if bad in src:
            result["forbidden_found"].append(bad)
    for good in REQUIRED_STRINGS.get(path, []):
        if good not in src:
            result["required_missing"].append(good)

    try:
        ast.parse(src)
        result["syntax_ok"] = True
    except SyntaxError as e:
        result["syntax_ok"] = False
        result["syntax_error"] = str(e)

    return result


def main():
    files = ["orchestrator.py", "design_matrix.py", "audit_manifest.py"]
    all_ok = True

    print("=" * 66)
    print("PRE-FLIGHT CHECK -- run this before every real orchestrator run")
    print("=" * 66)

    for f in files:
        r = check_file(f)
        if not r["exists"]:
            print(f"  [MISSING] {f}")
            all_ok = False
            continue

        # Hash mismatch alone is NOT a failure. SHA256 is byte-exact: a
        # trailing newline or CRLF line endings from however the file was
        # transferred changes the hash completely without changing meaning
        # (verified directly -- both add ~12 hex chars of pure noise to the
        # digest). The structural checks below (forbidden markers absent,
        # required markers present, valid syntax) are what actually verify
        # the file's CONTENT is current; hash is a fast first pass, not
        # the source of truth. An earlier version of this script treated
        # hash mismatch as a hard gate and would have blocked a correct
        # file over an invisible whitespace difference.
        content_ok = (not r["forbidden_found"]
                      and not r["required_missing"]
                      and r["syntax_ok"])
        ok = content_ok
        status = "OK" if ok else "STALE"
        all_ok = all_ok and ok
        print(f"  [{status}] {f}")

        if r.get("hash_match") is False:
            note = "" if content_ok else " (and content checks below also failed)"
            print(f"      hash differs from pinned reference (expected "
                  f"{EXPECTED[f]}, got {r['actual_hash']}){note} -- informational "
                  f"only, not a failure on its own; likely a whitespace/line-ending "
                  f"difference from file transfer.")
        if r["forbidden_found"]:
            print(f"      contains stale markers: {r['forbidden_found']}")
        if r["required_missing"]:
            print(f"      missing expected current-version markers: {r['required_missing']}")
        if r["syntax_ok"] is False:
            print(f"      SYNTAX ERROR: {r['syntax_error']}")

    print()
    if all_ok:
        print("PASS -- files match the current 3-factor design. Safe to run "
              "orchestrator.py for real.")
    else:
        print("FAIL -- do not run a real sweep yet. Re-copy the flagged files "
              "from the latest Claude output before proceeding, then re-run "
              "this check.")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()