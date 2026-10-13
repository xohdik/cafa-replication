#!/usr/bin/env python3
"""
check_synth_pairing_ast.py -- are C2, C4, C6, C8 built from ONE synthetic base program?  (AST-level, formatting-proof)

Compares the multiset of statements as parsed:
  * simple statement -> ast.dump(node)
  * compound statement (if/for/while/def/...) -> type + header expressions only (test / iter / target), not its body
Unchanged by formatting and by reordering statements within a block (what X3 does). For renamed pairs, names are masked.
With --shape: tallies the shape_info the orchestrator logged for the synthetic base programs.
Usage: python3 check_synth_pairing_ast.py manifest.json [--shape]
"""
import ast
import collections
import json
import sys

HEADER_FIELDS = ("test", "iter", "target", "items", "name", "args", "returns", "bases")


class Mask(ast.NodeTransformer):
    def visit_Name(self, n):
        return ast.copy_location(ast.Name(id="ID", ctx=ast.Load()), n)

    def visit_arg(self, n):
        n.arg = "ID"
        n.annotation = None
        return n

    def visit_FunctionDef(self, n):
        n.name = "ID"
        self.generic_visit(n)
        return n


def sig(src, mask=False):
    tree = ast.parse(src)
    if mask:
        tree = ast.fix_missing_locations(Mask().visit(tree))
    c = collections.Counter()
    for node in ast.walk(tree):
        if not isinstance(node, ast.stmt):
            continue
        if hasattr(node, "body") and isinstance(getattr(node, "body"), list):
            hdr = [(f, ast.dump(getattr(node, f))) for f in HEADER_FIELDS
                   if hasattr(node, f) and getattr(node, f) is not None and not isinstance(getattr(node, f), list)]
            c[(type(node).__name__, tuple(hdr))] += 1
        else:
            c[ast.dump(node)] += 1
    return c


def main():
    m = json.load(open(sys.argv[1]))
    samples = m["samples"] if isinstance(m, dict) else m
    tot = a24 = a68 = a26 = a2468 = bad = 0
    shapes = collections.Counter()
    for s in samples:
        conds = {x["condition_id"]: x for x in s["conditions"]}
        c = {i: (conds.get(i) or {}).get("source_code") for i in (2, 4, 6, 8)}
        if "--shape" in sys.argv and conds.get(2):
            for st in (conds[2].get("log") or {}).get("steps", []):
                if st.get("op") == "syntheticity" and st.get("shape_info"):
                    si = st["shape_info"]
                    shapes[(si.get("real_shape"), si.get("shape"), bool(si.get("shape_ok")))] += 1
        if not all(c.values()):
            continue
        try:
            u = {i: sig(c[i]) for i in c}
            mk = {i: sig(c[i], mask=True) for i in c}
        except SyntaxError:
            bad += 1
            continue
        tot += 1
        a24 += u[2] == u[4]
        a68 += mk[6] == mk[8]
        a26 += mk[2] == mk[6]
        a2468 += (mk[2] == mk[4] == mk[6] == mk[8])
    print(f"samples compared: {tot}   (unparseable: {bad})")
    print(f"C2 vs C4 same statements (AST multiset)            : {a24} ({a24 / tot:.1%})")
    print(f"C6 vs C8 same statements (names masked)            : {a68} ({a68 / tot:.1%})")
    print(f"C2 vs C6 same statements (names masked)            : {a26} ({a26 / tot:.1%})")
    print(f"all four identical up to names/order (names masked): {a2468} ({a2468 / tot:.1%})")
    if shapes:
        print("\nlogged shape_info: (real_shape, synthetic shape, shape_ok) -> count")
        for k, v in sorted(shapes.items(), key=lambda kv: -kv[1]):
            print(f"  {k}: {v}")
    print("\n~100% => the four synthetic cells share one base program. Low => independent programs.")


main()
