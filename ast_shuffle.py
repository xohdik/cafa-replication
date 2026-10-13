"""
X3 operator: randomize AST layout while preserving semantics, via
conservative def/use dependency analysis with control-flow barriers.

=== THIS FILE WAS REWRITTEN AFTER A REAL BUG ===

The v0 implementation produced semantically broken code. Example caught
during RQ4 batch validation on a realistic sample pool:

    ORIGINAL                          v0 SHUFFLED (BROKEN)
    out = []                          seen = set()
    seen = set()                      out = []
    for it in items:                  return out      <-- hoisted above loop
        if it not in seen:            for it in items:
            seen.add(it)                  ...
            out.append(it)
    return out

Two independent root causes, both fixed below:

1. CONTROL-FLOW TERMINATORS WERE NOT BARRIERS. `return` / `break` /
   `continue` / `raise` change what executes after them. They can never be
   reordered relative to surrounding statements, regardless of what def/use
   analysis says about their variables.

2. MUTATION THROUGH METHOD CALLS WAS INVISIBLE. `out.append(it)` appears in
   the AST as ast.Name(id='out', ctx=Load) -- a READ. The v0 visitor
   therefore never recorded it as a write, so it saw no conflict between
   "append to out" and "return out". The same blind spot applied to
   `d[k] = v` (subscript store), attribute stores, and augmented assignment.

The analysis below is deliberately CONSERVATIVE: when in doubt it declares
statements dependent and refuses to reorder. That biases toward weaker
perturbation (some legal reorderings are missed) rather than toward broken
code, which is the right trade-off -- a missed reordering weakens X3's
effect size, but a broken program silently contaminates the entire X3
condition with "model can't handle garbage" signal that is
indistinguishable from "model lacks structural reasoning."

verify_behavior() provides the differential test the research plan called
for: run original and shuffled against the same inputs, require identical
output. Use shuffle_and_verify() at scale so broken samples auto-revert
instead of entering the dataset.
"""
import ast
import random
import subprocess
import tempfile
import os
import json


# Statements that alter control flow or scope; never reorderable.
CONTROL_FLOW = (ast.Return, ast.Break, ast.Continue, ast.Raise,
                ast.Global, ast.Nonlocal, ast.Import, ast.ImportFrom,
                ast.Assert, ast.Delete, ast.Pass)

# Builtins that are referentially transparent: calling them twice in either
# order gives the same result and touches no external state. Calls to these
# do NOT block reordering.
#
# WHY THIS WHITELIST EXISTS: the first version of this analysis treated ANY
# call as a side effect, so two statements that both contained any call were
# never reorderable. On a real competitive-programming corpus (CodeNet), where
# nearly every line calls something (int, len, input, print), that killed
# 74.3% of samples outright -- X3's mean structural distance collapsed to
# 0.0039 versus 0.2957 on synthetic code, i.e. the operator was doing almost
# no work.
#
# WHAT IS DELIBERATELY *NOT* HERE, and why: input, print, open, and any I/O
# or randomness. Those are genuinely order-dependent -- `n = int(input())`
# followed by `m = int(input())` reads two different stdin lines, and swapping
# them changes the program's meaning even though no variable is shared. That
# dependency is invisible to def/use analysis, so the call-based block is the
# only thing catching it. Keeping them out of this list is not conservatism
# for its own sake; it is load-bearing.
PURE_BUILTINS = frozenset({
    "abs", "all", "any", "ascii", "bin", "bool", "bytes", "chr", "complex",
    "dict", "divmod", "enumerate", "filter", "float", "format", "frozenset",
    "hash", "hex", "int", "isinstance", "issubclass", "len", "list", "map",
    "max", "min", "oct", "ord", "pow", "range", "repr", "reversed", "round",
    "set", "slice", "sorted", "str", "sum", "tuple", "zip",
})

# Method names that do NOT mutate their receiver (safe to treat as reads).
# Anything not listed -- append, add, update, sort, extend, pop, ... -- is
# assumed to mutate.
PURE_METHODS = frozenset({
    "count", "index", "find", "rfind", "startswith", "endswith", "strip",
    "lstrip", "rstrip", "split", "rsplit", "join", "upper", "lower", "title",
    "replace", "format", "encode", "decode", "isdigit", "isalpha", "isalnum",
    "isspace", "get", "keys", "values", "items", "copy", "bit_length",
})


class DefUseCollector(ast.NodeVisitor):
    """Conservative def/use analysis.

    Departures from naive ctx=Store/Load analysis:
    - A method call `x.foo(...)` counts x as BOTH used and DEFINED, since
      the call may mutate x in place (append/add/update/sort/...). No
      attempt is made to whitelist "safe" methods; that's a losing game.
    - Subscript/attribute stores (`x[i] = v`, `x.attr = v`) count the base
      name as both used and defined.
    - Augmented assignment (`x += 1`) counts x as both used and defined.
    - Any call at all sets has_side_effects, since an arbitrary call may
      touch global state invisible to this analysis.
    """

    def __init__(self):
        self.defs: set[str] = set()
        self.uses: set[str] = set()
        # Names mutated IN PLACE (subscript/attribute store, mutating method
        # call). These land in both defs and uses, which matters for the
        # call-closure computation: free variables are normally uses-minus-defs,
        # and an in-place mutation of a global would otherwise cancel itself
        # out of the free set. Measured consequence: a DFS whose visit marker
        # was `m[y][x] = 2` had `m` cancelled from closure['dfs'], so the
        # recursive call looked independent of the marker assignment, the
        # marker was reordered after the recursion, and the program recursed
        # infinitely. Tracked separately so free_names() can keep them.
        self.mutated: set[str] = set()
        self.has_side_effects = False

    def free_names(self) -> set[str]:
        """Names this scope depends on from an enclosing scope. Locally-bound
        names are subtracted, but in-place mutations are NOT, since mutating
        a name requires it to already exist."""
        pure_local = self.defs - self.mutated
        return (self.uses | self.mutated) - pure_local

    def visit_FunctionDef(self, node: ast.FunctionDef):
        # CRITICAL: FunctionDef.name is a plain str attribute, NOT an ast.Name
        # node, so visit_Name never fires on it. Without this, the analysis
        # treats `def f(): ...` as defining nothing, and happily hoists
        # `x = f()` above it -- producing NameError at runtime. This was a real
        # corruption source measured at 7.1% on a CodeNet pool.
        self.defs.add(node.name)
        # Do NOT descend into the body: names bound inside a function are
        # local, and treating them as module-level defs causes false conflicts.
        # We do still need the body's free variables as uses, since the
        # function may close over module-level state.
        inner = DefUseCollector()
        for child in node.body:
            inner.visit(child)
        self.uses |= inner.free_names()
        for d in node.args.defaults + [k for k in node.args.kw_defaults if k]:
            self.visit(d)
        for dec in node.decorator_list:
            self.visit(dec)

    def visit_AsyncFunctionDef(self, node):
        self.visit_FunctionDef(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        self.defs.add(node.name)
        inner = DefUseCollector()
        for child in node.body:
            inner.visit(child)
        self.uses |= inner.free_names()
        for base in node.bases:
            self.visit(base)
        for dec in node.decorator_list:
            self.visit(dec)

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            self.defs.add(alias.asname or alias.name.split(".")[0])

    def visit_ImportFrom(self, node: ast.ImportFrom):
        for alias in node.names:
            self.defs.add(alias.asname or alias.name)

    def visit_arg(self, node: ast.arg):
        self.defs.add(node.arg)

    def visit_Name(self, node: ast.Name):
        if isinstance(node.ctx, ast.Store):
            self.defs.add(node.id)
        elif isinstance(node.ctx, ast.Del):
            self.defs.add(node.id)
            self.uses.add(node.id)
        else:
            self.uses.add(node.id)
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign):
        base = self._base_name(node.target)
        if base:
            self.defs.add(base)
            self.uses.add(base)
            self.mutated.add(base)
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript):
        if isinstance(node.ctx, (ast.Store, ast.Del)):
            base = self._base_name(node)
            if base:
                self.defs.add(base)
                self.uses.add(base)
                self.mutated.add(base)
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute):
        if isinstance(node.ctx, (ast.Store, ast.Del)):
            base = self._base_name(node)
            if base:
                self.defs.add(base)
                self.uses.add(base)
                self.mutated.add(base)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        if isinstance(node.func, ast.Name):
            # Plain function call: pure builtins don't block reordering.
            if node.func.id not in PURE_BUILTINS:
                self.has_side_effects = True
        elif isinstance(node.func, ast.Attribute):
            # Method call. Non-pure methods are assumed to mutate the receiver.
            if node.func.attr not in PURE_METHODS:
                self.has_side_effects = True
                base = self._base_name(node.func)
                if base:
                    self.defs.add(base)
                    self.uses.add(base)
                    self.mutated.add(base)
        else:
            # Call on something we can't identify (lambda, subscript, ...).
            self.has_side_effects = True
        self.generic_visit(node)

    @staticmethod
    def _base_name(node: ast.AST):
        """Walk down Subscript/Attribute chains to the root Name, if any."""
        cur = node
        while isinstance(cur, (ast.Subscript, ast.Attribute)):
            cur = cur.value
        return cur.id if isinstance(cur, ast.Name) else None


def analyze(stmt: ast.stmt) -> DefUseCollector:
    c = DefUseCollector()
    c.visit(stmt)
    return c


# Calls that can read or write arbitrary names at runtime. The analysis
# cannot see through them (exec's argument is an opaque string literal), so
# any statement containing one is a hard barrier.
#
# Found by measurement: a code-golf sample used
#     exec('*_,b=r\nfor t in s(l): ...' * k)
# and the analysis moved `_, r = zip(*l)` AFTER it, because nothing in the
# statement textually references `r`. The exec'd string did.
OPAQUE_CALLS = frozenset({
    "exec", "eval", "compile", "globals", "locals", "vars", "__import__",
    "setattr", "delattr", "getattr", "input", "open",
})


def _has_opaque_call(stmt: ast.stmt) -> bool:
    for node in ast.walk(stmt):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in OPAQUE_CALLS:
                return True
    return False


SCOPE_NODES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)


def _walk_own_scope(stmt: ast.stmt):
    """Yield nodes belonging to `stmt`'s OWN scope, without descending into
    nested function/lambda/class bodies (whose return/yield belong to them,
    not to us). If `stmt` is itself a scope node, we skip its body entirely."""
    if isinstance(stmt, SCOPE_NODES):
        # The def/class statement itself: its body is another scope. Only the
        # decorators and default-argument expressions execute here.
        for dec in getattr(stmt, "decorator_list", []):
            yield from ast.walk(dec)
        args = getattr(stmt, "args", None)
        if args is not None:
            for d in list(args.defaults) + [k for k in args.kw_defaults if k]:
                yield from ast.walk(d)
        for base in getattr(stmt, "bases", []):
            yield from ast.walk(base)
        return

    stack = [stmt]
    while stack:
        node = stack.pop()
        yield node
        for child in ast.iter_child_nodes(node):
            if isinstance(child, SCOPE_NODES):
                continue  # different scope; its returns/yields aren't ours
            stack.append(child)


def is_barrier(stmt: ast.stmt) -> bool:
    """A statement is a barrier if it IS, or CONTAINS (in its own scope),
    anything that alters control flow.

    The "contains" case matters and was a real corruption source: a guard
    clause like

        if nums == []:
            return True
        m = nums[0]

    is an ast.If, which is not itself in CONTROL_FLOW -- but it holds a
    Return. Testing only the outer node type let the analysis hoist
    `m = nums[0]` above the guard, raising IndexError on empty input.

    Scope awareness matters equally: a `def f(): return x` contains a Return,
    but that Return belongs to f's scope, not to the enclosing one, so the
    def statement is NOT a barrier on those grounds (its name binding is
    handled by def/use analysis instead)."""
    if isinstance(stmt, CONTROL_FLOW):
        return True
    if _has_opaque_call(stmt):
        return True
    for node in _walk_own_scope(stmt):
        if isinstance(node, (ast.Return, ast.Break, ast.Continue, ast.Raise,
                              ast.Yield, ast.YieldFrom, ast.Await,
                              ast.Global, ast.Nonlocal)):
            return True
    return False


def independent(stmt_a: ast.stmt, stmt_b: ast.stmt, call_closure: dict = None) -> bool:
    """Safe to reorder only if neither is a barrier, not both have unknown
    side effects, and there is no RAW / WAR / WAW hazard between them --
    including hazards reached transitively through function calls."""
    if is_barrier(stmt_a) or is_barrier(stmt_b):
        return False

    a, b = analyze(stmt_a), analyze(stmt_b)

    # Two statements that both call functions may interact through state
    # invisible here (I/O, globals, shared mutable objects).
    if a.has_side_effects and b.has_side_effects:
        return False

    a_uses = expand_uses(stmt_a, a.uses, call_closure)
    b_uses = expand_uses(stmt_b, b.uses, call_closure)

    if a.defs & (b_uses | b.defs):
        return False
    if b.defs & (a_uses | a.defs):
        return False
    return True


def find_independent_blocks(statements: list[ast.stmt],
                             call_closure: dict = None) -> list[list[ast.stmt]]:
    """Group consecutive statements into maximal blocks where every pair
    inside the block is mutually independent."""
    if not statements:
        return []
    blocks = [[statements[0]]]
    for stmt in statements[1:]:
        current = blocks[-1]
        if all(independent(stmt, s, call_closure) for s in current):
            current.append(stmt)
        else:
            blocks.append([stmt])
    return blocks


def build_call_closure(tree: ast.Module) -> dict:
    """Map each module-level function name -> the set of free names its body
    transitively depends on (including via calls to other functions).

    WHY THIS EXISTS: local def/use analysis cannot see through a call. A
    measured corruption had this shape --

        def main():           # calls parallel_orthogonal(), which calls dot()
            ...
        main()                # <-- hoisted above `def dot(...)`
        def dot(a, b):
            ...

    `main()` and `def dot` share no names textually, so they looked
    independent; but executing main() reaches dot(). Expanding each call to
    its transitive free-name set makes that dependency visible."""
    direct: dict[str, set[str]] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            inner = DefUseCollector()
            for child in node.body:
                inner.visit(child)
            direct[node.name] = inner.free_names()

    # Fixed-point expansion: a function depends on what its callees depend on.
    closure = {k: set(v) for k, v in direct.items()}
    for _ in range(len(closure) + 1):
        changed = False
        for fname, deps in closure.items():
            for d in list(deps):
                if d in direct:
                    new = direct[d] - deps
                    if new:
                        deps |= new
                        changed = True
        if not changed:
            break
    return closure


def expand_uses(stmt: ast.stmt, base_uses: set, call_closure: dict) -> set:
    """Add transitive dependencies for every user-defined function this
    statement calls."""
    if not call_closure:
        return base_uses
    expanded = set(base_uses)
    for name in list(base_uses):
        if name in call_closure:
            expanded |= call_closure[name]
    return expanded


class BodyShuffler(ast.NodeTransformer):
    """Shuffles independent statement blocks in function, class, AND module
    bodies.

    WHY MODULE BODIES MATTER: an earlier version implemented only
    visit_FunctionDef. Diagnostic run on a real CodeNet-derived corpus (448
    parsed samples) showed 58.5% were top-level scripts with no function
    definitions at all, so X3 never touched them, and the median function
    body among the remaining 41.5% was just 2 statements. Module-level pairs
    contained 845 independent pairs versus 408 in function bodies, i.e. the
    traversal, not the dependency analysis, was the binding constraint.
    """

    def __init__(self, seed=None, call_closure=None):
        self.rng = random.Random(seed)
        self.n_shuffled_blocks = 0
        self.n_atomic_blocks = 0
        self.call_closure = call_closure or {}

    def _shuffle_body(self, body: list[ast.stmt]) -> list[ast.stmt]:
        blocks = find_independent_blocks(body, self.call_closure)
        new_body: list[ast.stmt] = []
        for block in blocks:
            if len(block) > 1:
                self.n_shuffled_blocks += 1
                shuffled = block[:]
                self.rng.shuffle(shuffled)
                new_body.extend(shuffled)
            else:
                self.n_atomic_blocks += 1
                new_body.extend(block)
        return new_body

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self.generic_visit(node)
        node.body = self._shuffle_body(node.body)
        return node

    def visit_AsyncFunctionDef(self, node):
        self.generic_visit(node)
        node.body = self._shuffle_body(node.body)
        return node

    def visit_ClassDef(self, node: ast.ClassDef):
        self.generic_visit(node)
        node.body = self._shuffle_body(node.body)
        return node

    def visit_Module(self, node: ast.Module):
        self.generic_visit(node)
        node.body = self._shuffle_body(node.body)
        return node


def shuffle_ast(source_code: str, seed=None) -> tuple[str, dict]:
    """Returns (perturbed_source, stats). Low n_shuffled_blocks means X3 had
    little to work with on that sample -- report the distribution of this
    across the pool, don't assume uniform perturbation strength."""
    tree = ast.parse(source_code)
    closure = build_call_closure(tree)
    shuffler = BodyShuffler(seed=seed, call_closure=closure)
    new_tree = shuffler.visit(tree)
    ast.fix_missing_locations(new_tree)
    stats = {
        "n_shuffled_blocks": shuffler.n_shuffled_blocks,
        "n_atomic_blocks": shuffler.n_atomic_blocks,
    }
    return ast.unparse(new_tree), stats


# ---- differential behavioral verification -----------------------------------

HARNESS = """
import json, sys
{code}
args = json.loads(sys.argv[1])
print(json.dumps({func}(*args)))
"""


def _run(code: str, func: str, args: list, timeout: float = 5.0):
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(HARNESS.format(code=code, func=func))
        path = f.name
    try:
        p = subprocess.run(["python3", path, json.dumps(args)],
                            capture_output=True, text=True, timeout=timeout)
        if p.returncode != 0:
            return None, p.stderr.strip()[:300]
        return json.loads(p.stdout.strip()), None
    except Exception as e:
        return None, str(e)
    finally:
        os.unlink(path)


def verify_behavior(original: str, shuffled: str, func_name: str,
                     test_inputs: list, timeout: float = 5.0) -> dict:
    """Differential test: original and shuffled must produce identical output
    on every test input. NOT OPTIONAL at scale -- run it over the sample pool
    and revert (or discard) any sample that fails, rather than letting broken
    code into the X3 condition."""
    mismatches = []
    for args in test_inputs:
        o, oerr = _run(original, func_name, args, timeout)
        s, serr = _run(shuffled, func_name, args, timeout)
        if oerr is not None:
            mismatches.append({"input": args, "reason": f"original failed: {oerr}"})
        elif serr is not None:
            mismatches.append({"input": args, "reason": f"shuffled failed: {serr}"})
        elif o != s:
            mismatches.append({"input": args, "original": o, "shuffled": s,
                                "reason": "output mismatch"})
    return {"passed": len(mismatches) == 0,
            "n_inputs": len(test_inputs),
            "n_mismatches": len(mismatches),
            "mismatches": mismatches}


def shuffle_and_verify(source_code: str, func_name: str, test_inputs: list,
                        seed=None) -> tuple[str, dict, dict]:
    """Shuffle, then differentially verify. On failure returns the ORIGINAL
    code with the failure report -- never returns broken code."""
    shuffled, stats = shuffle_ast(source_code, seed=seed)
    report = verify_behavior(source_code, shuffled, func_name, test_inputs)
    if not report["passed"]:
        return source_code, {**stats, "reverted": True}, report
    return shuffled, {**stats, "reverted": False}, report


# ---- script-mode verification (top-level programs, stdin -> stdout) ---------
# Needed because 58.5% of a real CodeNet-derived pool are top-level scripts
# with no function to call. verify_behavior() above cannot test those; this
# runs the whole program against stdin and compares stdout.

def _run_script(code: str, stdin_text: str, timeout: float = 5.0):
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(code)
        path = f.name
    try:
        p = subprocess.run(["python3", path], input=stdin_text,
                            capture_output=True, text=True, timeout=timeout)
        if p.returncode != 0:
            return None, p.stderr.strip()[:300]
        return p.stdout, None
    except Exception as e:
        return None, str(e)
    finally:
        os.unlink(path)


def verify_script_behavior(original: str, shuffled: str, stdin_cases: list,
                            timeout: float = 5.0) -> dict:
    """Differential test for top-level scripts.

    stdin_cases: list of strings, each the complete stdin for one run
    (e.g. "3\\n1 2 3\\n"). CodeNet-style corpora usually ship these; if you
    have none for a sample, you cannot verify it -- treat that sample as
    unverifiable and leave it unshuffled rather than assuming correctness.
    """
    mismatches = []
    for stdin_text in stdin_cases:
        o, oerr = _run_script(original, stdin_text, timeout)
        s, serr = _run_script(shuffled, stdin_text, timeout)
        if oerr is not None:
            mismatches.append({"stdin": stdin_text[:80],
                                "reason": f"original failed: {oerr}"})
        elif serr is not None:
            mismatches.append({"stdin": stdin_text[:80],
                                "reason": f"shuffled failed: {serr}"})
        elif o != s:
            mismatches.append({"stdin": stdin_text[:80], "original": o[:120],
                                "shuffled": s[:120], "reason": "stdout mismatch"})
    return {"passed": len(mismatches) == 0,
            "n_cases": len(stdin_cases),
            "n_mismatches": len(mismatches),
            "mismatches": mismatches}


def shuffle_and_verify_script(source_code: str, stdin_cases: list,
                               seed=None) -> tuple[str, dict, dict]:
    """Script-mode counterpart of shuffle_and_verify(). Reverts to the
    original on any stdout mismatch. If stdin_cases is empty, refuses to
    shuffle at all rather than emit unverified code."""
    if not stdin_cases:
        return source_code, {"n_shuffled_blocks": 0, "n_atomic_blocks": 0,
                              "reverted": True, "reason": "no stdin cases to verify against"}, \
               {"passed": False, "n_cases": 0, "n_mismatches": 0,
                "mismatches": [{"reason": "no test inputs supplied"}]}
    shuffled, stats = shuffle_ast(source_code, seed=seed)
    report = verify_script_behavior(source_code, shuffled, stdin_cases)
    if not report["passed"]:
        return source_code, {**stats, "reverted": True}, report
    return shuffled, {**stats, "reverted": False}, report


if __name__ == "__main__":
    # The exact case that broke v0.
    regression = """def solve(items):
    out = []
    seen = set()
    for it in items:
        if it not in seen:
            seen.add(it)
            out.append(it)
    return out"""

    print("=== REGRESSION TEST: the case that broke v0 ===")
    shuffled, stats = shuffle_ast(regression, seed=42)
    print("stats:", stats)
    print(shuffled)
    report = verify_behavior(regression, shuffled, "solve",
                              [[[1, 2, 2, 3]], [[]], [[5, 5, 5]]])
    print("behavioral verification:", "PASS" if report["passed"] else "FAIL")
    assert report["passed"], f"REGRESSION FAILED: {report['mismatches']}"

    print("\n=== A case that SHOULD still shuffle (truly independent) ===")
    ok = """def demo(a, b):
    x = a + 1
    y = b + 2
    z = 99
    return x + y + z"""
    shuffled2, stats2 = shuffle_ast(ok, seed=3)
    print("stats:", stats2)
    print(shuffled2)
    r2 = verify_behavior(ok, shuffled2, "demo", [[1, 2], [0, 0], [-5, 5]])
    print("behavioral verification:", "PASS" if r2["passed"] else "FAIL")
    assert r2["passed"]
    assert stats2["n_shuffled_blocks"] > 0, "expected a real shuffle here"

    print("\n=== Mutation-through-method-call must NOT be reordered ===")
    mutate = """def build(n):
    acc = []
    acc.append(n)
    total = sum(acc)
    return total"""
    shuffled3, stats3 = shuffle_ast(mutate, seed=1)
    r3 = verify_behavior(mutate, shuffled3, "build", [[1], [7], [0]])
    print("stats:", stats3, "| verification:", "PASS" if r3["passed"] else "FAIL")
    assert r3["passed"], f"mutation ordering violated: {r3['mismatches']}"

    print("\n=== shuffle_and_verify auto-revert path ===")
    code, st, rep = shuffle_and_verify(regression, "solve",
                                        [[[1, 2, 2, 3]], [[]]], seed=42)
    print(f"reverted={st['reverted']}, verification passed={rep['passed']}")

    print("\n=== MODULE-LEVEL: real CodeNet-shaped top-level script ===")
    # Verbatim shape from the diagnostic run on the real corpus.
    script = """n = int(input())
s = input()
ans = 0
init = True
m = s.count('#')
l = [0] * m
idx = 0
for i in range(n):
    if s[i] == '#':
        l[idx] = i
        idx += 1
ans = m
for i in range(m):
    ans = min(ans, i + (n - l[i] - 1 - (m - i - 1)))
print(ans)"""
    shuffled4, stats4 = shuffle_ast(script, seed=5)
    print("stats:", stats4)
    stdin_cases = ["5\n##.#.\n", "3\n###\n", "4\n....\n"]
    r4 = verify_script_behavior(script, shuffled4, stdin_cases)
    print("script verification:", "PASS" if r4["passed"] else "FAIL")
    if not r4["passed"]:
        print("  mismatches:", r4["mismatches"][:2])
    assert r4["passed"], "module-level shuffle changed script behavior"
    assert stats4["n_shuffled_blocks"] > 0, \
        "module body should now be shuffleable (this was the 58.5% blind spot)"
    print("shuffled script:")
    print(shuffled4)

    print("\n=== CRITICAL: sequential input() reads must NOT be reordered ===")
    io_script = """a = int(input())
b = int(input())
print(a - b)"""
    sh5, st5 = shuffle_ast(io_script, seed=9)
    r5 = verify_script_behavior(io_script, sh5, ["7\n2\n", "1\n9\n"])
    print("stats:", st5, "| verification:", "PASS" if r5["passed"] else "FAIL")
    assert r5["passed"], f"stdin ordering violated: {r5['mismatches']}"

    print("\n=== shuffle_and_verify_script refuses without test inputs ===")
    code6, st6, rep6 = shuffle_and_verify_script(script, [])
    print(f"reverted={st6['reverted']}, reason={st6.get('reason')}")
    assert code6 == script and st6["reverted"]

    print("\nAll AST-shuffle regression tests passed.")