#!/usr/bin/env python3
"""patch_ast_subset.py -- make ast_subset_effects.py compare parsed ASTs, not raw text."""
import shutil, sys
path = sys.argv[1] if len(sys.argv) > 1 else "ast_subset_effects.py"
s = open(path).read()
if "def same_program" in s:
    raise SystemExit("already patched; nothing to do")

old_imp = "import argparse\nimport json\nimport numpy as np\n"
new_imp = ("import argparse\nimport ast\nimport json\nimport numpy as np\n")
old_flag = ("        flags = [int(src.get(b) != src.get(s_)) if (b in src and s_ in src) else 0 for b, s_ in PAIRS]\n")
new_flag = ("        flags = [int(not same_program(src[b], src[s_])) if (b in src and s_ in src) else 0 for b, s_ in PAIRS]\n")
old_def = "def changed_flags(manifest_path, pids):\n"
new_def = '''def same_program(a, b):
    """True if the two sources parse to the SAME syntax tree (same statements in the same order).
    Raw text cannot be compared: the unshuffled baseline C1 is the original text, while shuffled
    conditions went through an AST round-trip that rewrites formatting, comments and quotes."""
    try:
        return ast.dump(ast.parse(a)) == ast.dump(ast.parse(b))
    except SyntaxError:
        return a == b


def changed_flags(manifest_path, pids):
'''
for o, n in [(old_imp, new_imp), (old_flag, new_flag), (old_def, new_def)]:
    if s.count(o) != 1:
        raise SystemExit(f"expected exactly one match for:\n{o!r}\nfound {s.count(o)}; not writing")
    s = s.replace(o, n)
# also avoid the empty-slice warning
o = "AST effect {v_all[comp].mean():+.4f}\""
if s.count(o) == 1:
    s = s.replace(o, "AST effect {(v_all[comp].mean() if comp.any() else float('nan')):+.4f}\"")
shutil.copy(path, path + ".bak")
open(path, "w").write(s)
print(f"patched {path} (backup: {path}.bak)")
