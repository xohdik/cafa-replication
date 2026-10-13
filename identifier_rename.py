"""
X2 operator: identifier obfuscation via AST alpha-renaming.

Isolates lexical dependence while leaving program structure untouched.

=== REWRITTEN AFTER MEASURED BREAKAGE ===

v0 was validated only by STRUCTURAL distance (0.0000 across 447 real
samples -- correct, since renaming does not change AST shape). That check is
blind to whether the renamed program still RUNS. Behavioral verification on a
probe set showed v0 broke 62.5% of programs, via four bugs that share one root
cause: in Python's AST, DEFINITION names are plain string attributes
(`alias.asname`, `ClassDef.name`, `FunctionDef.name`) while USAGE sites are
`ast.Name` nodes. v0 renamed usages but not definitions, so the two drifted
apart:

    import sys          ->  import sys            # alias untouched
    sys.stdin.readline()->  var_1.stdin.read...   # usage renamed  -> NameError

    class C: ...        ->  class C: ...          # ClassDef.name untouched
    C().m()             ->  var_1().m()           # usage renamed  -> NameError

    def m(self): ...    ->  def var_0(self): ...  # method renamed
    obj.m()             ->  obj.m()               # attribute NOT renamed -> breaks

    exec("z = 7")       ->  exec("z = 7")         # string opaque
    print(z)            ->  print(var_0)          # usage renamed  -> NameError

This is the same class of defect found in ast_shuffle.py (FunctionDef.name is
a str, so a def appeared to define nothing). Any AST rewriter that treats
`ast.Name` as the only binding site will hit it.

POLICY IN v1, chosen to prefer refusing over corrupting:
  - Imported module names are PROTECTED, never renamed. They refer to external
    modules; renaming them buys no lexical obfuscation of the program's own
    logic and risks exactly the mismatch above.
  - Class names and their usages are renamed CONSISTENTLY.
  - Methods (FunctionDef inside ClassDef) are NOT renamed, because their call
    sites are attribute accesses, which cannot be safely renamed in general
    (an attribute may belong to a library object).
  - Attribute names are never renamed, for the same reason.
  - If the module contains exec/eval, renaming is SKIPPED entirely and the
    original is returned, since names may be referenced inside opaque strings.

Python-only. Multi-language needs a tree-sitter rewrite of the same idea.
"""
import ast
import builtins

PROTECTED = set(dir(builtins)) | {"self", "cls", "__init__", "__main__", "__name__"}

# Renaming cannot be guaranteed correct when names may be referenced from
# inside string literals evaluated at runtime.
OPAQUE_CALLS = {"exec", "eval", "compile", "globals", "locals", "vars", "getattr",
                "setattr", "delattr", "__import__"}


def _collect_imported_names(tree: ast.AST) -> set:
    """Names bound by import statements. Protected from renaming."""
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                names.add(a.asname or a.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            for a in node.names:
                names.add(a.asname or a.name)
    return names


def _collect_method_names(tree: ast.AST) -> set:
    """Function names defined inside a class. Not renamed: their call sites
    are attribute accesses, which we do not rename."""
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    names.add(child.name)
    return names


def _has_opaque_call(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in OPAQUE_CALLS:
                return True
    return False


class IdentifierObfuscator(ast.NodeTransformer):
    def __init__(self, protected: set):
        self.mapping: dict[str, str] = {}
        self.counter = 0
        self.protected = protected

    def _new_name(self, old_name: str) -> str:
        if old_name in self.protected or old_name.startswith("__"):
            return old_name
        if old_name not in self.mapping:
            self.mapping[old_name] = f"var_{self.counter}"
            self.counter += 1
        return self.mapping[old_name]

    def visit_Name(self, node: ast.Name):
        node.id = self._new_name(node.id)
        return node

    def visit_FunctionDef(self, node: ast.FunctionDef):
        node.name = self._new_name(node.name)
        self.generic_visit(node)
        return node

    def visit_AsyncFunctionDef(self, node):
        node.name = self._new_name(node.name)
        self.generic_visit(node)
        return node

    def visit_ClassDef(self, node: ast.ClassDef):
        # Rename the class name so it stays consistent with `C()` usages,
        # which visit_Name rewrites.
        node.name = self._new_name(node.name)
        self.generic_visit(node)
        return node

    def visit_arg(self, node: ast.arg):
        node.arg = self._new_name(node.arg)
        return node

    def visit_Attribute(self, node: ast.Attribute):
        # Recurse into the value (so `obj` in `obj.attr` is renamed) but never
        # rename `.attr` itself -- it may belong to a library object.
        self.generic_visit(node)
        return node

    def visit_Global(self, node: ast.Global):
        node.names = [self._new_name(n) for n in node.names]
        return node

    def visit_Nonlocal(self, node: ast.Nonlocal):
        node.names = [self._new_name(n) for n in node.names]
        return node


def obfuscate_identifiers(source_code: str) -> tuple[str, dict]:
    """Returns (perturbed_source, old_name -> new_name mapping).

    Returns the ORIGINAL source with an empty mapping when renaming cannot be
    guaranteed safe (module contains exec/eval). Callers should treat an empty
    mapping as "X2 not applied" and account for it in coverage statistics
    rather than assuming the treatment landed."""
    tree = ast.parse(source_code)

    if _has_opaque_call(tree):
        return source_code, {}

    protected = (PROTECTED
                 | _collect_imported_names(tree)
                 | _collect_method_names(tree))

    obfuscator = IdentifierObfuscator(protected)
    new_tree = obfuscator.visit(tree)
    ast.fix_missing_locations(new_tree)
    return ast.unparse(new_tree), obfuscator.mapping


if __name__ == "__main__":
    cases = [
        ("plain", "def compute_average(values, weights):\n"
                   "    total = 0\n"
                   "    for value, weight in zip(values, weights):\n"
                   "        total += value * weight\n"
                   "    return total"),
        ("import", "import sys\nn = int(sys.stdin.readline())\nprint(n * 2)"),
        ("class", "class C:\n    def m(self):\n        return 9\nprint(C().m())"),
        ("exec", 'exec("z = 7")\nprint(z)'),
        ("global", "x = 1\ndef g():\n    global x\n    x = 5\ng()\nprint(x)"),
        ("fromimport", "from collections import Counter\nc = Counter([1,1,2])\nprint(c[1])"),
    ]
    for label, src in cases:
        out, mapping = obfuscate_identifiers(src)
        status = "SKIPPED (opaque call)" if not mapping else f"{len(mapping)} renamed"
        print(f"=== {label}: {status}")
        print(out)
        print()