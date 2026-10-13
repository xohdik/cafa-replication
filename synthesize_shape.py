#!/usr/bin/env python3
"""
synthesize_shape.py -- shape-aware synthetic script generation (wraps synthesize.py; does not modify it).

Problem measured in the pilot: the synthetic generator never prints more than one line, and about a fifth of
its programs print exactly "0", while a third of real programs print several lines and only ~2% print "0".
The pooled syntheticity effect therefore mixes an output-shape difference into the contrast.

Cause (synthesize.py::_script_flexible): when a target's cyclomatic complexity is reached by loop/if NESTING alone,
no `result += ...` statement exists, so result stays 0 (a structural zero); otherwise the random sibling
conditions can all be false on the fixed stdin (n = 3). print(result) sits outside all nesting, so one line only.

This module adds two controllable properties, WITHOUT changing the complexity profile (print placement,
an unconditional increment and an extra print do not alter cyclomatic complexity or nesting depth, and the
distance to the target is re-measured and enforced):
  want_multiline : the program prints more than one line
                   - k >= 1 (a for loop exists): print(result) moves INSIDE the outermost for loop, so it prints the
                     running total once per iteration (n lines; values differ because result accumulates)
                   - k == 0 : two extra print(result + j) statements at top level
  avoid_zero     : the program does not print exactly "0" on the stdin used for scoring
Every candidate is EXECUTED on that stdin; a candidate is accepted only if its output shape matches the request
and its complexity distance is within tolerance. If nothing matches within max_tries, the best complexity match
is returned with shape_ok = False so the caller can log and report it instead of silently accepting it.

Usage in code:
    from synthesize_shape import generate_synthetic_script_shaped, output_shape
    code, profile, dist, info = generate_synthetic_script_shaped(
        target, rng, want_multiline=(real_shape == "multi"), avoid_zero=(real_shape != "zero"))
Self-test: python3 synthesize_shape.py
"""
from __future__ import annotations
import operator
import random
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import synthesize as S  # noqa: E402

_OPS = {">": operator.gt, "<": operator.lt, ">=": operator.ge, "<=": operator.le, "==": operator.eq}


def _default_runner():
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "perturbations"))
        from ast_shuffle import _run_script
        return _run_script
    except Exception:  # pragma: no cover
        return None


def output_shape(out) -> str:
    """zero / empty / multi / single -- the same strata used in the analysis."""
    s = "\n".join(l.rstrip() for l in (out or "").strip().splitlines())
    if s == "0":
        return "zero"
    if s == "":
        return "empty"
    return "multi" if "\n" in s else "single"


def _script_flexible_shaped(target, rng, n_val, multiline, avoid_zero):
    D = max(0, target.max_depth)
    C = max(1, target.cyclomatic)
    L = max(1, target.lines)
    k = min(D, C - 1)
    remaining_cyc = (C - 1) - k
    if remaining_cyc > 0:
        b, w = remaining_cyc, 0
    else:
        b, w = 0, max(0, D + 1 - k)

    if C == 1 and D == 0 and L <= 2 and not multiline:
        return "print(int(input()))" if L == 1 else "n = int(input())\nprint(n)"

    lines = []
    if w > 0:
        lines.append("import contextlib")
    lines.append("n = int(input())")
    lines.append("result = 0")
    indent = ""
    outer_loop_indent = None
    hi = 2 if avoid_zero else 3          # `if n > t` is true at n = 3 only when t <= 2
    for i in range(k):
        if i % 2 == 0:
            if outer_loop_indent is None:
                outer_loop_indent = indent
            lines.append(f"{indent}for i_{i} in range(n):")
        else:
            lines.append(f"{indent}if n > {rng.randint(-3, hi)}:")
        indent += "    "
    for _ in range(w):
        lines.append(f"{indent}with contextlib.nullcontext():")
        indent += "    "
    body = indent

    if avoid_zero and b == 0:
        lines.append(f"{body}result += {rng.randint(1, 9)}")          # unconditional increment (no complexity cost)
    for i in range(b):
        op, c = rng.choice(list(_OPS)), rng.randint(-9, 9)
        if avoid_zero and i == 0:                                       # first sibling is guaranteed true at this n
            for _ in range(50):
                op, c = rng.choice(list(_OPS)), rng.randint(-9, 9)
                if _OPS[op](n_val, c):
                    break
        lines.append(f"{body}if n {op} {c}: result += {rng.randint(1, 9)}")

    tail = []
    if multiline and outer_loop_indent is not None:
        tail_in_loop = f"{outer_loop_indent}    print(result)"
    else:
        tail_in_loop = None
        if multiline:
            tail += [f"print(result + {j})" for j in (1, 2)]
    n_pad = max(0, L - len(lines) - len(tail) - 1 - (1 if tail_in_loop else 0))
    for i in range(n_pad):
        lines.append(f"{body}_pad{i} = {rng.randint(0, 99)}")
    if (k > 0 or w > 0) and b == 0 and n_pad == 0 and not (avoid_zero):
        lines.append(f"{body}pass")
    if tail_in_loop:
        lines.append(tail_in_loop)
    lines += tail
    if not tail_in_loop:
        lines.append("print(result)")
    return "\n".join(lines)


def generate_synthetic_script_shaped(target, rng=None, want_multiline=False, avoid_zero=True,
                                      stdin="3\n1 2 3\n", max_tries=60, tolerance=0.15, runner=None):
    """Returns (code, profile, dist, info). info = {shape, shape_ok, dist_ok, tries}."""
    rng = rng or random.Random()
    runner = runner or _default_runner()
    if runner is None:
        raise RuntimeError("need ast_shuffle._run_script on the path (or pass runner=...)")
    try:
        n_val = int(stdin.split()[0])
    except Exception:
        n_val = 3
    best_any = None            # (dist, code, profile, shape)
    best_ok = None
    for t in range(1, max_tries + 1):
        code = _script_flexible_shaped(target, rng, n_val, want_multiline, avoid_zero)
        try:
            prof = S.complexity_profile(code)
        except SyntaxError:
            continue
        dist = target.distance(prof)
        out, err = runner(code, stdin, 5.0)
        if err:
            continue
        shape = output_shape(out)
        shape_ok = ((("multi" in shape) if want_multiline else (shape != "multi"))
                    and not (avoid_zero and shape == "zero"))
        if best_any is None or dist < best_any[0]:
            best_any = (dist, code, prof, shape)
        if shape_ok and (best_ok is None or dist < best_ok[0]):
            best_ok = (dist, code, prof, shape)
        if shape_ok and dist <= tolerance:
            break
    if best_ok is not None:
        dist, code, prof, shape = best_ok
        return code, prof, dist, {"shape": shape, "shape_ok": True, "dist_ok": dist <= tolerance, "tries": t}
    if best_any is None:
        raise RuntimeError("no executable candidate produced")
    dist, code, prof, shape = best_any
    return code, prof, dist, {"shape": shape, "shape_ok": False, "dist_ok": dist <= tolerance, "tries": t}


if __name__ == "__main__":
    import collections
    rng = random.Random(0)

    def sample_target():
        c = max(1, int(rng.lognormvariate(1.8, 0.7)))
        L = max(1, int(rng.lognormvariate(2.9, 0.7)))
        d = min(7, int(rng.lognormvariate(0.5, 0.8)))
        return S.ComplexityProfile(cyclomatic=c, lines=L, max_depth=d)

    run = _default_runner()
    for label, ml in (("single-line requested", False), ("multi-line requested", True)):
        shapes, ok, dist_bad, n = collections.Counter(), 0, 0, 300
        for _ in range(n):
            code, prof, d, info = generate_synthetic_script_shaped(sample_target(), rng, want_multiline=ml,
                                                                   avoid_zero=True, runner=run)
            shapes[info["shape"]] += 1
            ok += info["shape_ok"]
            dist_bad += not info["dist_ok"]
        print(f"{label}: shapes {dict(shapes)}   shape_ok {ok / n:.3f}   distance>tolerance {dist_bad / n:.3f}")
