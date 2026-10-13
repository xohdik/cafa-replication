#!/usr/bin/env python3
"""
patch_sobol_anova.py -- fix the share denominator in sobol_anova.py (in place).

Defect: sobol_indices() built every numerator from the condition MEANS but the
denominator ss_total from every individual replicate observation. The shares
were therefore deflated by the number of replicates (3 -> one third), the seven
terms did not sum to 100%, and the result changed with the replicate count.

Fix: ss_total = between-condition sum of squares of the condition means, which
equals the sum of every contrast's sum of squares (Parseval), so shares sum to 100%.

Usage:  python3 patch_sobol_anova.py sobol_anova.py     (writes sobol_anova.py.bak first)
"""
import shutil
import sys

path = sys.argv[1] if len(sys.argv) > 1 else "sobol_anova.py"
s = open(path).read()
if "Between-condition sum of squares" in s:
    raise SystemExit("already patched; nothing to do")

EDITS = [
    ("    all_obs = response_matrix.flatten()\n"
     "    ss_total = float(np.sum((all_obs - all_obs.mean()) ** 2))\n",
     "    # Between-condition sum of squares of the condition means. The numerators below\n"
     "    # are built from the means, so the denominator must be in the same units.\n"
     "    # (Summing over every replicate deflated each share by the replicate count.)\n"
     "    ss_total = float(np.sum((means - means.mean()) ** 2))\n"),
    ("responses = np.zeros((16, n_reps))",
     "responses = np.zeros((dm.shape[0], n_reps))"),
    ("2^4 full factorial design.",
     "2^k full factorial design (k = len(FACTORS); k = 3 in the executable design)."),
    ("response_matrix: (16, n_reps) array",
     "response_matrix: (n_conditions, n_reps) array"),
    ("(16,) condition means", "(n_conditions,) condition means"),
    ("    columns with replacement, condition by condition.\"\"\"\n",
     "    columns with replacement, condition by condition.\n\n"
     "    WARNING: this resamples replicates only, so it captures decoding noise and\n"
     "    nothing else. Under greedy decoding replicates are near-duplicates and the\n"
     "    interval is far too narrow. Report program-level intervals from\n"
     "    cafa_shares.py instead.\n"
     "    \"\"\"\n"),
]
for old, new in EDITS:
    if s.count(old) != 1:
        raise SystemExit(f"expected exactly one match for:\n{old!r}\nfound {s.count(old)}; file differs from the version I patched, not writing")
    s = s.replace(old, new)

shutil.copy(path, path + ".bak")
open(path, "w").write(s)
print(f"patched {path} (backup: {path}.bak)")
