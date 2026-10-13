#!/usr/bin/env python3
"""
patch_orchestrator.py -- (1) share ONE synthetic base program per sample across C2/C4/C6/C8 and
                          (2) optionally match the real program's output shape.  Edits orchestrator.py in place (.bak first).

New flags on orchestrator.py:
  --shared-synth  build the synthetic base program once per sample and reuse it in every synthetic condition
  --shape-match   implies --shared-synth; also match the real program's output shape (multi-line vs single-line,
                  non-zero unless the real output is 0), using synthesize_shape.py
Without either flag the behaviour is unchanged, so the pilot manifest can still be rebuilt exactly.

Usage: python3 patch_orchestrator.py orchestrator.py
"""
import shutil
import sys

path = sys.argv[1] if len(sys.argv) > 1 else "orchestrator.py"
s = open(path).read()
if "_synthetic_base_for_sample" in s:
    raise SystemExit("already patched; nothing to do")

HELPER = '''def _synthetic_base_for_sample(base_sample, real_code, target_profile, rng, config):
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


def build_condition('''

EDITS = [
    ("def build_condition(", HELPER),
    ("            synth_code, achieved_profile, distance = generate_synthetic_script(\n                target_profile, rng=rng)\n",
     "            synth_code, achieved_profile, distance = _synthetic_base_for_sample(\n"
     "                base_sample, code, target_profile, rng, config)\n"),
    ("                                  \"distance_to_target\": distance,\n                                  \"n_stdin_cases\": len(stdin_cases),\n",
     "                                  \"distance_to_target\": distance,\n                                  \"shape_info\": base_sample.get(\"_synthetic_info\"),\n"
     "                                  \"n_stdin_cases\": len(stdin_cases),\n"),
    ("    ap.add_argument(\"--seed\", type=int, default=0)\n",
     "    ap.add_argument(\"--seed\", type=int, default=0)\n"
     "    ap.add_argument(\"--shared-synth\", action=\"store_true\", default=False,\n"
     "                    help=\"Build the synthetic base program once per sample and reuse it in every synthetic condition.\")\n"
     "    ap.add_argument(\"--shape-match\", action=\"store_true\", default=False,\n"
     "                    help=\"Implies --shared-synth. Also match the synthetic program's output shape (multi-line / zero) to the real one.\")\n"),
    ("        \"verify_x2\": args.verify_x2,\n",
     "        \"verify_x2\": args.verify_x2,\n        \"shared_synth\": args.shared_synth,\n        \"shape_match\": args.shape_match,\n"),
]
for old, new in EDITS:
    if s.count(old) != 1:
        raise SystemExit(f"expected exactly one match for:\n{old!r}\nfound {s.count(old)}; file differs from the version I patched, not writing")
    s = s.replace(old, new)
shutil.copy(path, path + ".bak")
open(path, "w").write(s)
print(f"patched {path} (backup: {path}.bak)")
