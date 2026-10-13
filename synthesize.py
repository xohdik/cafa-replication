"""
X5 operator: synthetic/counterfactual program generation, matched to the
real-code complexity distribution of the sample it stands in for.

Why match complexity: an unmatched synthetic condition confounds
syntheticity with difficulty -- if synthetic samples are systematically
simpler than real ones, a model's better performance on X5=synthetic gets
misread as "abstract reasoning is easier," when it's actually just "these
samples are easier," a confound indistinguishable from the real effect
(RESEARCH_PLAN.md, stubs.py SynthesizeOperator contract).

Complexity profile: cyclomatic complexity (McCabe), line count, max nesting
depth. All computed via Python's ast module, no external dependencies.
"""
from __future__ import annotations
import ast
import random
from dataclasses import dataclass


@dataclass
class ComplexityProfile:
    cyclomatic: int
    lines: int
    max_depth: int

    def distance(self, other: "ComplexityProfile") -> float:
        """Normalized L1 distance across the three dimensions, for reporting
        how well a generated synthetic sample matched its target."""
        return (
            abs(self.cyclomatic - other.cyclomatic) / max(self.cyclomatic, other.cyclomatic, 1)
            + abs(self.lines - other.lines) / max(self.lines, other.lines, 1)
            + abs(self.max_depth - other.max_depth) / max(self.max_depth, other.max_depth, 1)
        ) / 3


class CyclomaticVisitor(ast.NodeVisitor):
    """McCabe cyclomatic complexity: 1 + one per decision point
    (if/elif, for, while, except, boolean operators, comprehension ifs)."""
    def __init__(self):
        self.complexity = 1

    def visit_If(self, node): self.complexity += 1; self.generic_visit(node)
    def visit_For(self, node): self.complexity += 1; self.generic_visit(node)
    def visit_While(self, node): self.complexity += 1; self.generic_visit(node)
    def visit_ExceptHandler(self, node): self.complexity += 1; self.generic_visit(node)
    def visit_BoolOp(self, node): self.complexity += len(node.values) - 1; self.generic_visit(node)
    def visit_comprehension(self, node): self.complexity += len(node.ifs); self.generic_visit(node)


def _max_depth(node: ast.AST, depth: int = 0) -> int:
    """Max nesting depth of compound statements (If/For/While/Try/With/FunctionDef)."""
    compound = (ast.If, ast.For, ast.While, ast.Try, ast.With, ast.FunctionDef)
    children_depths = [
        _max_depth(child, depth + (1 if isinstance(node, compound) else 0))
        for child in ast.iter_child_nodes(node)
    ]
    own = depth + (1 if isinstance(node, compound) else 0)
    return max([own] + children_depths) if children_depths else own


def complexity_profile(source_code: str) -> ComplexityProfile:
    tree = ast.parse(source_code)
    visitor = CyclomaticVisitor()
    visitor.visit(tree)
    lines = len([l for l in source_code.splitlines() if l.strip()])
    depth = _max_depth(tree) - 1  # subtract the implicit Module-level "depth"
    return ComplexityProfile(cyclomatic=visitor.complexity, lines=lines, max_depth=max(depth, 0))


# ---- template library -------------------------------------------------------
# Each template is parameterized by (n_branches, n_loops, depth) knobs so we
# can tune toward a target complexity profile rather than emit one fixed shape.

def _template_accumulator(n_branches: int, rng: random.Random) -> str:
    """Linear accumulator with n_branches conditional adjustments -- low
    nesting, cyclomatic complexity scales directly with n_branches."""
    lines = ["def synth_accumulate(items):", "    total = 0", "    for item in items:"]
    ops = ["+=", "-=", "*="]
    for i in range(n_branches):
        cmp = rng.choice([">", "<", ">=", "<=", "=="])
        thresh = rng.randint(-10, 10)
        op = rng.choice(ops)
        val = rng.randint(1, 5)
        kw = "if" if i == 0 else "elif"
        lines.append(f"        {kw} item {cmp} {thresh}:")
        lines.append(f"            total {op} {val}")
    lines.append("        else:")
    lines.append("            total += 1")
    lines.append("    return total")
    return "\n".join(lines)


def _template_nested(depth: int, rng: random.Random) -> str:
    """Nested conditional/loop structure -- max_depth scales directly with depth."""
    lines = ["def synth_nested(x):", "    result = 0"]
    indent = "    "
    for i in range(depth):
        indent_next = indent + "    "
        if i % 2 == 0:
            lines.append(f"{indent}for i_{i} in range(x + {i}):")
        else:
            lines.append(f"{indent}if x > {rng.randint(-5, 5)}:")
        indent = indent_next
    lines.append(f"{indent}result += 1")
    lines.append("    return result")
    return "\n".join(lines)


def _template_mixed(n_branches: int, depth: int, rng: random.Random) -> str:
    """Combination template for mid-range complexity targets that neither
    pure template hits well on its own."""
    lines = ["def synth_mixed(data):", "    out = []", "    for row in data:"]
    indent = "        "
    for i in range(depth):
        lines.append(f"{indent}if row {rng.choice(['>', '<', '!='])} {rng.randint(-5, 5)}:")
        indent += "    "
    for i in range(n_branches):
        kw = "if" if i == 0 else "elif"
        lines.append(f"{indent}{kw} row % {rng.randint(2, 5)} == 0:")
        lines.append(f"{indent}    out.append(row)")
    lines.append(f"{indent}else:" if n_branches else f"{indent}pass")
    if n_branches:
        lines.append(f"{indent}    out.append(-row)")
    lines.append("    return out")
    return "\n".join(lines)


TEMPLATES = [_template_accumulator, _template_nested, _template_mixed]

# Test inputs per template signature. These exist so that SYNTHETIC samples
# remain verifiable under X3 (AST shuffle), which refuses to shuffle code it
# cannot behaviorally verify.
#
# WHY THIS MATTERS FOR THE DESIGN, not just for tidiness: in the Resolution V
# matrix, 4 of the 8 shuffle conditions are also synthetic (conditions 3, 8,
# 12, 15). Without test inputs for synthetic programs, X3 silently skips half
# its own cells, the X3 treatment is applied inconsistently across the design,
# and S_i(AST structure) is biased toward zero for a purely mechanical reason
# that would be invisible in the results.
TEMPLATE_TEST_INPUTS = {
    "synth_accumulate": [[[1, 2, 3, 4]], [[]], [[-7, 0, 7]], [[5, 5, 5, 5, 5]]],
    "synth_nested":     [[3], [0], [7], [1]],
    "synth_mixed":      [[[1, 2, 3, 4, 5]], [[]], [[-3, -2, -1]], [[10, 20]]],
}


def infer_func_name(code: str) -> str:
    """Template functions are named after their template."""
    for name in TEMPLATE_TEST_INPUTS:
        if f"def {name}(" in code:
            return name
    return ""


def test_inputs_for(code: str) -> list:
    """Test inputs matching whichever template generated `code`."""
    return TEMPLATE_TEST_INPUTS.get(infer_func_name(code), [])


def generate_synthetic(target: ComplexityProfile, rng: random.Random = None,
                        max_tries: int = 25, tolerance: float = 0.15):
    """
    Search over template + knob combinations for one whose complexity
    profile is within `tolerance` (normalized distance) of the target.
    Returns (code, achieved_profile, distance) for the best candidate found,
    even if tolerance isn't hit within max_tries -- caller should check
    distance and log/skip samples that don't converge rather than silently
    accept a poor match.
    """
    rng = rng or random.Random()
    best = None  # (distance, code, profile)

    for _ in range(max_tries):
        n_branches = max(1, target.cyclomatic - 1 + rng.randint(-1, 1))
        depth = max(1, target.max_depth + rng.randint(-1, 1))

        template_fn = rng.choice(TEMPLATES)
        if template_fn is _template_accumulator:
            code = _template_accumulator(n_branches, rng)
        elif template_fn is _template_nested:
            code = _template_nested(depth, rng)
        else:
            code = _template_mixed(max(1, n_branches // 2), max(1, depth // 2), rng)

        try:
            profile = complexity_profile(code)
        except SyntaxError:
            continue  # shouldn't happen given the templates, but don't let it kill the search

        dist = target.distance(profile)
        if best is None or dist < best[0]:
            best = (dist, code, profile)
        if dist <= tolerance:
            break

    dist, code, profile = best
    return code, profile, dist


def match_complexity_distribution(real_samples: list, rng: random.Random = None) -> list:
    """For each real sample, generate a matched synthetic counterpart.
    Returns list of dicts: {real_source, synthetic_source, target_profile,
    achieved_profile, distance} -- report the distance distribution across
    the pool, don't just assume convergence, same principle as the
    manipulation-check finding in Section VIII of the paper."""
    rng = rng or random.Random()
    results = []
    for real_code in real_samples:
        target = complexity_profile(real_code)
        synth_code, achieved, dist = generate_synthetic(target, rng)
        results.append({
            "real_source": real_code, "synthetic_source": synth_code,
            "target_profile": target, "achieved_profile": achieved, "distance": dist,
        })
    return results


if __name__ == "__main__":
    real_samples = [
        "def f(items):\n    total = 0\n    for x in items:\n        if x > 0:\n            total += x\n    return total",
        "def g(a, b, c):\n    if a > b:\n        if b > c:\n            return a\n        return b\n    return c",
        "def h(n):\n    result = 0\n    for i in range(n):\n        for j in range(n):\n            if i == j:\n                result += 1\n    return result",
    ]

    print("Real sample complexity profiles:")
    for s in real_samples:
        p = complexity_profile(s)
        print(f"  cyclomatic={p.cyclomatic}, lines={p.lines}, max_depth={p.max_depth}")

    print("\nGenerating matched synthetic counterparts...")
    results = match_complexity_distribution(real_samples, rng=random.Random(42))
    for i, r in enumerate(results):
        print(f"\n--- Sample {i} ---")
        print(f"Target:   cyclomatic={r['target_profile'].cyclomatic}, "
              f"lines={r['target_profile'].lines}, max_depth={r['target_profile'].max_depth}")
        print(f"Achieved: cyclomatic={r['achieved_profile'].cyclomatic}, "
              f"lines={r['achieved_profile'].lines}, max_depth={r['achieved_profile'].max_depth}")
        print(f"Distance: {r['distance']:.3f}")
        print("Generated code:")
        print(r["synthetic_source"])


# ---- script-form templates --------------------------------------------------
# The synthetic condition must match the FORM of the corpus, not only its
# complexity profile. A real CodeNet pool is ~58% top-level stdin->stdout
# scripts, while the function templates above produce callable functions.
# That difference is not cosmetic: X4 (transpilation) validates scripts by
# whole-program stdout comparison and functions by return-value comparison,
# so if X5 switches the form, X4's success rate becomes a function of X5 and
# the language contrast is confounded with the syntheticity contrast.
# Generating synthetic programs in script form keeps X4 doing the same job in
# every cell.

def _script_flexible(target: "ComplexityProfile", rng: random.Random) -> str:
    """Constructively build a script targeting all three dimensions largely
    independently, rather than picking from a small fixed template.

    WHY THIS EXISTS. Diagnosis on a real 300-sample CodeNet pool found the
    previous three fixed templates' achievable range (cyclomatic<=4,
    lines<=11, depth<=2) falling far short of real targets: median real
    target was cyclomatic=6, lines=19, depth=2; p90 was cyclomatic=16,
    lines=61, depth=4; max was cyclomatic=58, lines=202, depth=7. More than
    half the corpus was structurally unreachable regardless of search
    attempts -- a range problem, not a search problem.

    A second, independent bug compounded it: the old accumulator template
    added branches as an if/elif/elif chain. Each elif desugars to a nested
    If inside the previous one's orelse, so a long elif chain silently
    inflates AST nesting depth as a side effect of adding cyclomatic
    complexity -- confirmed directly: a 4-way elif chain (flat branching to
    a human) measures max_depth=3, not 1. Worst measured case: target
    depth=2, achieved depth=23, while chasing target cyclomatic=25 via
    elif-chaining. Fixed here by using INDEPENDENT sibling if-statements
    (not elif) for cyclomatic, so branch count no longer inflates depth:
    siblings all sit at the same AST level regardless of how many there
    are, contributing at most one additional depth level.

    Construction: nesting (for/if chained, the only mechanism that
    legitimately increases AST depth) supplies as much of the cyclomatic
    target as the depth budget allows; any remaining cyclomatic need is
    supplied by independent sibling if-statements at the innermost level
    (at most +1 more depth, regardless of how many); line count is padded
    afterward with simple filler assignments, decoupled from both.
    """
    D = max(0, target.max_depth)
    C = max(1, target.cyclomatic)
    L = max(1, target.lines)

    # Empirically calibrated (not derived by hand -- an earlier derivation
    # assumed a 1:1 mapping and was off by one; see measurement notes
    # below). Three mechanisms, each contributing to (cyclomatic, depth) in
    # a DIFFERENT and independently measured way:
    #
    #   for/if nesting chain, k levels: cyclomatic +k, and (with -1 for the
    #     implicit module frame) raw depth contribution k.
    #   with contextlib.nullcontext() chain, w levels: cyclomatic +0 (not
    #     counted by CyclomaticVisitor), raw depth contribution w. This is
    #     the ONLY mechanism that adds depth without also adding cyclomatic
    #     -- needed because a target with high depth but low cyclomatic
    #     (e.g. cyc=1, depth=6) cannot be reached by for/if nesting alone,
    #     which always couples the two. Measured directly: 3 chained
    #     with-blocks give cyclomatic=1 (unchanged), depth=2.
    #   independent sibling if-branches, b of them: cyclomatic +b, and at
    #     most +1 to depth regardless of how many siblings (they don't
    #     nest inside each other). Measured directly: 1, 3, and 10 sibling
    #     branches at the same nesting position all measured depth+1,
    #     never more.
    #
    # k covers as much of the shared (cyclomatic AND depth) budget as
    # possible; whichever of the two remains after k is supplied by w
    # (pure depth) or b (pure cyclomatic) -- never both, since k already
    # exhausts whichever of C-1/D is smaller.
    k = min(D, C - 1)
    remaining_cyc = (C - 1) - k
    if remaining_cyc > 0:
        b = remaining_cyc
        w = 0
    else:
        b = 0
        w = max(0, D + 1 - k)

    # Two targeted refinements after the first real-corpus check found 4/300
    # residual misses, all dominated by "lines": tight targets where the
    # minimum line-cost of this generator's own formatting exceeded the
    # target (e.g. a genuine 1-line target -- `print(int(input()))` in one
    # statement -- versus this generator's structural minimum of 2 lines
    # for separate read-then-print; and a 4-branch target in 4 lines versus
    # this generator's 2-lines-per-branch cost). Neither is a structural
    # complexity failure -- cyclomatic and max_depth matched exactly on all
    # 300 real samples, including all 4 of these misses -- purely a
    # formatting-density gap on already-tight targets.
    if C == 1 and D == 0 and L <= 2:
        return "print(int(input()))" if L == 1 else "n = int(input())\nprint(n)"

    lines = []
    if w > 0:
        lines.append("import contextlib")
    lines.append("n = int(input())")
    # result initialized OUTSIDE all nesting, unconditionally -- if it were
    # only set inside a conditional branch (e.g. `if n > 3:`), a test input
    # that makes that branch false would leave `result` undefined, and the
    # now-external print(result) would raise NameError. Confirmed directly:
    # this crashed on exactly that input shape when only print() (not this
    # initialization) had been moved outside.
    lines.append("result = 0")
    indent = ""
    for i in range(k):
        if i % 2 == 0:
            lines.append(f"{indent}for i_{i} in range(n):")
        else:
            lines.append(f"{indent}if n > {rng.randint(-3, 3)}:")
        indent += "    "
    for i in range(w):
        lines.append(f"{indent}with contextlib.nullcontext():")
        indent += "    "
    body_indent = indent

    for i in range(b):
        # Single-line `if cond: body` instead of two lines -- halves the
        # per-branch line cost, closing the gap on dense/tight real targets.
        lines.append(f"{body_indent}if n {rng.choice(['>', '<', '>=', '<=', '=='])} "
                     f"{rng.randint(-9, 9)}: result += {rng.randint(1, 9)}")

    n_pad = max(0, L - len(lines) - 1)
    for i in range(n_pad):
        lines.append(f"{body_indent}_pad{i} = {rng.randint(0, 99)}")

    # If nesting exists (k>0 or w>0) but nothing was placed at body_indent
    # (b==0 and n_pad==0), the innermost for/if/with block has an empty
    # body -- a Python IndentationError, not merely a semantics issue.
    # Confirmed by testing broadly across (C, D, L) combinations after
    # moving print() and result=0 outside the nesting; this case is real
    # and was not covered by the earlier b==0-and-k==0-and-w==0 check alone.
    if (k > 0 or w > 0) and b == 0 and n_pad == 0:
        lines.append(f"{body_indent}pass")

    # print() OUTSIDE all nesting (column 0), not at body_indent. Found by
    # inspecting real model predictions on the first full experimental
    # sweep: with print() inside the loop, every outer-loop iteration reset
    # `result` to 0 and recomputed the identical value (nothing in the
    # branch conditions depends on the loop variables i_0/i_2), so a
    # program with k>=1 for-loop nesting printed the SAME line n times (or
    # n^2 for double nesting) -- an output shape with no natural analog in
    # real code, and one the few-shot prompt's single-line example gives
    # the model no reason to expect regardless of its actual capability.
    # Confirmed print()'s position does not affect complexity_profile
    # (verified directly: identical cyclomatic/depth either way), so this
    # does not disturb the already-validated 0% real-corpus miss rate.
    lines.append("print(result)")
    return "\n".join(lines)


def _script_straightline(rng: random.Random) -> str:
    """Cyclomatic complexity 1, depth 0: no branches, no loops at all.

    Added after a 300-sample validation run measured 77/300 (25.7%) of
    generated synthetic scripts missing the 0.15 complexity-match tolerance
    -- and 76 of those 77 misses were this exact target shape. Neither
    _script_accumulator nor _script_nested can produce it: both force at
    least one branch or loop level via max(1, ...) in their parameter
    computation, so a target this simple was structurally unreachable no
    matter how many search attempts ran. This template closes that gap
    rather than widening the tolerance to paper over it."""
    ops = ["*", "+", "-"]
    lines = ["n = int(input())"]
    var = "n"
    for i in range(rng.randint(0, 2)):
        newvar = f"v{i}"
        lines.append(f"{newvar} = {var} {rng.choice(ops)} {rng.randint(1, 9)}")
        var = newvar
    lines.append(f"print({var})")
    return "\n".join(lines)


def _script_accumulator(n_branches: int, rng: random.Random) -> str:
    lines = ["n = int(input())", "a = list(map(int, input().split()))", "total = 0",
             "for item in a:"]
    ops = ["+=", "-="]
    for i in range(max(1, n_branches)):
        kw = "if" if i == 0 else "elif"
        lines.append(f"    {kw} item {rng.choice(['>', '<', '>=', '<='])} {rng.randint(-5, 5)}:")
        lines.append(f"        total {rng.choice(ops)} {rng.randint(1, 4)}")
    lines.append("    else:")
    lines.append("        total += 1")
    lines.append("print(total)")
    return "\n".join(lines)


def _script_nested(depth: int, rng: random.Random) -> str:
    lines = ["n = int(input())", "result = 0"]
    indent = ""
    for i in range(max(1, depth)):
        if i % 2 == 0:
            lines.append(f"{indent}for i_{i} in range(n):")
        else:
            lines.append(f"{indent}if n > {rng.randint(-3, 3)}:")
        indent += "    "
    lines.append(f"{indent}result += 1")
    lines.append("print(result)")
    return "\n".join(lines)


SCRIPT_TEMPLATES = [_script_straightline, _script_accumulator, _script_nested]

# stdin cases valid for ALL script templates (each reads one int line; the
# straight-line template ignores everything after the first line, and
# _script_accumulator additionally reads a list line which _script_nested
# simply ignores).
SCRIPT_STDIN_CASES = ["3\n1 2 3\n", "1\n5\n", "4\n-2 0 7 3\n"]


def generate_synthetic_script(target: ComplexityProfile, rng: random.Random = None,
                               max_tries: int = 25, tolerance: float = 0.15):
    """Script-form counterpart of generate_synthetic(). Returns
    (code, achieved_profile, distance).

    Routes to _script_flexible() whenever the target exceeds the small
    fixed templates' achievable range (empirically: cyclomatic<=4,
    lines<=11, depth<=2) -- which real CodeNet targets exceed most of the
    time (median real cyclomatic=6, lines=19). The fixed templates are
    tried first for small targets since they add minor stylistic variety;
    the flexible generator is the fallback that can actually reach large
    targets, and becomes the primary path once any dimension exceeds the
    small templates' range."""
    rng = rng or random.Random()
    small_template_range = (target.cyclomatic <= 4 and target.lines <= 11
                             and target.max_depth <= 2)

    best = None
    if small_template_range:
        for _ in range(max_tries):
            n_branches = max(1, target.cyclomatic - 1 + rng.randint(-1, 1))
            depth = max(1, target.max_depth + rng.randint(-1, 1))
            fn = rng.choice(SCRIPT_TEMPLATES)
            if fn is _script_straightline:
                code = _script_straightline(rng)
            elif fn is _script_accumulator:
                code = _script_accumulator(n_branches, rng)
            else:
                code = _script_nested(depth, rng)
            try:
                profile = complexity_profile(code)
            except SyntaxError:
                continue
            dist = target.distance(profile)
            if best is None or dist < best[0]:
                best = (dist, code, profile)
            if dist <= tolerance:
                break

    if best is None or best[0] > tolerance:
        for _ in range(max_tries):
            code = _script_flexible(target, rng)
            try:
                profile = complexity_profile(code)
            except SyntaxError:
                continue
            dist = target.distance(profile)
            if best is None or dist < best[0]:
                best = (dist, code, profile)
            if dist <= tolerance:
                break

    dist, code, profile = best
    return code, profile, dist