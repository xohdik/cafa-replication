#!/usr/bin/env python3
"""
patch_normalize.py -- add --normalize-baseline to orchestrator.py (run AFTER patch_orchestrator.py).

C1 and C2 are the raw text while every perturbed condition passes through an ast.unparse round-trip, so "perturbed vs
baseline" also contains a formatting change. With --normalize-baseline EVERY condition's final program goes through the same
round-trip (idempotent for those that already did) and is checked to behave identically (script: first stdin case;
function: first test input). Comments are dropped in ALL conditions. Without the flag behaviour is unchanged.

Usage: python3 patch_normalize.py orchestrator.py
"""
import shutil
import sys

path = sys.argv[1] if len(sys.argv) > 1 else "orchestrator.py"
s = open(path).read()
if "normalize_baseline" in s:
    raise SystemExit("already patched; nothing to do")

NORM = '''    # Optional: normalise formatting identically in every condition (see patch_normalize.py).
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

'''
ANCHOR_RET = ('    return {\n        "condition_id": condition["condition_id"],\n        "source_code": code,\n'
              '        "func_name": func_name,\n')
EDITS = [
    (ANCHOR_RET, NORM + ANCHOR_RET),
    ("    ap.add_argument(\"--shared-synth\"",
     "    ap.add_argument(\"--normalize-baseline\", action=\"store_true\", default=False,\n"
     "                    help=\"Pass EVERY condition (incl. C1/C2) through the same ast.unparse round-trip so formatting is not confounded with X2/X3.\")\n"
     "    ap.add_argument(\"--shared-synth\""),
    ("        \"shared_synth\": args.shared_synth,\n",
     "        \"shared_synth\": args.shared_synth,\n        \"normalize_baseline\": args.normalize_baseline,\n"),
]
for old, new in EDITS:
    if s.count(old) != 1:
        raise SystemExit(f"expected exactly one match for:\n{old!r}\nfound {s.count(old)}; file differs from the version I patched, not writing")
    s = s.replace(old, new)
shutil.copy(path, path + ".bak2")
open(path, "w").write(s)
print(f"patched {path} (backup: {path}.bak2)")
