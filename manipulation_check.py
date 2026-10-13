"""
Prerequisite RQ A: manipulation check.

v0 proxy metrics only -- dependency-free, good enough to sanity-check the
pipeline end to end, but NOT a substitute for a real tree-edit-distance.
Before the actual paper, replace order_sensitive_distance() with
Zhang-Shasha or APTED tree edit distance (both have maintained Python
packages) so the manipulation-check numbers in Section III are defensible.

IMPORTANT, found by actually running this: an earlier version of this file
used an AST node-type *multiset* distance (count of each node type,
order-ignored). That metric is structurally blind to reordering -- shuffling
two Assign statements doesn't change how many Assign nodes exist, so it
scored X3 (shuffle) as producing zero structural distance. Kept below as
node_type_multiset_distance() for reference/illustration only; it is NOT
the metric the manipulation check should rely on. order_sensitive_distance()
below, based on a diff over the ast.dump() serialization (which encodes
position/order), is the one that actually detects reordering.

Expected pattern to confirm before trusting anything downstream:
  order_sensitive_distance(original, X2_perturbed)  ~ near 0 (or entirely
    driven by the renamed identifier tokens, not structural position)
  order_sensitive_distance(original, X3_perturbed)  >> 0
"""
import ast
import difflib


def node_type_multiset(source_code: str) -> dict[str, int]:
    """Order-insensitive. Kept for illustration -- do not use this as the
    manipulation-check metric, see module docstring."""
    tree = ast.parse(source_code)
    counts: dict[str, int] = {}
    for node in ast.walk(tree):
        t = type(node).__name__
        counts[t] = counts.get(t, 0) + 1
    return counts


def node_type_multiset_distance(source_a: str, source_b: str) -> float:
    ca, cb = node_type_multiset(source_a), node_type_multiset(source_b)
    keys = set(ca) | set(cb)
    diff = sum(abs(ca.get(k, 0) - cb.get(k, 0)) for k in keys)
    total = sum(ca.get(k, 0) for k in keys) + sum(cb.get(k, 0) for k in keys)
    return diff / total if total else 0.0


IDENTIFIER_FIELDS = {
    ("Name", "id"), ("arg", "arg"), ("FunctionDef", "name"),
    ("ClassDef", "name"), ("Attribute", "attr"), ("keyword", "arg"),
}


class IdentifierBlanker(ast.NodeTransformer):
    """Structural normalization pass: replace every identifier-carrying
    string field with a fixed placeholder so ast.dump() reflects shape and
    order only, not identifier content. This is what makes the X2 vs X3
    comparison apples-to-apples."""
    def generic_visit(self, node):
        super().generic_visit(node)
        node_type = type(node).__name__
        for field in list(node._fields):
            if (node_type, field) in IDENTIFIER_FIELDS:
                setattr(node, field, "_ID_")
        return node


def structure_only_dump(source_code: str) -> str:
    """Kept for debugging/inspection. NOT used by the distance metric anymore
    -- see the PERFORMANCE note on structure_token_sequence() below."""
    tree = ast.parse(source_code)
    blanked = IdentifierBlanker().visit(tree)
    return ast.dump(blanked)


def structure_token_sequence(source_code: str, structure_only: bool = True) -> list:
    """Document-order sequence of AST node-type tokens.

    PERFORMANCE, and why this replaced the previous ast.dump()-string approach:
    the old metric ran difflib.SequenceMatcher over ast.dump() STRINGS, which
    is O(n^2) in characters. That was fine on 5-line fixtures (~500 chars) and
    effectively hung on a real CodeNet pool. Measured on synthetic functions:

        400-line function -> dump 95,002 chars -> 0.927 s per comparison
                          -> token seq 5,607 items -> 0.0018 s  (~512x faster)

    Two comparisons per sample over 500 samples is ~15 minutes the old way
    versus ~2 seconds this way, and the growth curve was clean quadratic
    (0.055 / 0.202 / 0.927 s at 100 / 200 / 400 lines), so longer real
    solutions were far worse.

    The token sequence preserves document order, so it stays sensitive to
    statement reordering (which is the entire point for X3), while being
    ~100x shorter than the serialized string. Identifier values are dropped
    entirely when structure_only=True, which is what makes X2 (pure renaming)
    score ~0.
    """
    tree = ast.parse(source_code)
    if structure_only:
        tree = IdentifierBlanker().visit(tree)
        return [type(n).__name__ for n in ast.walk(tree)]
    # Non-structure-only: include identifier values as their own tokens.
    toks = []
    for n in ast.walk(tree):
        toks.append(type(n).__name__)
        for field in ("id", "arg", "name", "attr"):
            v = getattr(n, field, None)
            if isinstance(v, str):
                toks.append(f"#{v}")
    return toks


def order_sensitive_distance(source_a: str, source_b: str, structure_only: bool = True) -> float:
    """1 - SequenceMatcher.ratio() over AST node-type token sequences.

    With structure_only=True (default), identifiers are blanked so the
    distance reflects shape/order only -- the correct setting for comparing
    X2 (should score ~0) against X3 (should score higher).

    Still a proxy. The research plan calls for real tree edit distance
    (Zhang-Shasha / APTED) before submission; note that those are O(n^3) or
    worse, so if adopted they should be applied to a bounded subsample rather
    than the full pool, or the runtime problem documented above returns in a
    worse form."""
    seq_a = structure_token_sequence(source_a, structure_only)
    seq_b = structure_token_sequence(source_b, structure_only)
    # autojunk is a heuristic tuned for text; it misfires on repetitive token
    # sequences like ASTs, so disable it.
    ratio = difflib.SequenceMatcher(None, seq_a, seq_b, autojunk=False).ratio()
    return 1.0 - ratio


def run_manipulation_check(original: str, x2_perturbed: str, x3_perturbed: str) -> dict:
    d_x2 = order_sensitive_distance(original, x2_perturbed, structure_only=True)
    d_x3 = order_sensitive_distance(original, x3_perturbed, structure_only=True)
    return {
        "structure_only_distance_X2_rename": round(d_x2, 4),
        "structure_only_distance_X3_shuffle": round(d_x3, 4),
        "X2_isolates_lexical_only": d_x2 < 0.02,
        "X3_perturbs_more_than_X2": d_x3 > d_x2,
    }


"""
FINDING FROM RUNNING THIS ON A REAL SAMPLE (keep for the paper, Section III):
when the independent statements X3 swaps are structurally interchangeable
after identifier-blanking (e.g. two bare `x = 0` / `y = 0` initializations),
structure_only_distance correctly reports ~0 for that swap -- the reordering
is genuinely structurally invisible, not a pipeline bug. This means X3's
*effective* perturbation strength varies with how structurally heterogeneous
a function's independent statements are, not just with how many independent
statements exist. Report the distribution of per-sample structural distance
across the manipulation-check pool, not just its mean -- a pool dominated by
homogeneous-statement functions will understate X3's true strength.
"""


if __name__ == "__main__":
    from identifier_rename import obfuscate_identifiers
    from ast_shuffle import shuffle_ast

    sample = '''
def process(items):
    count = 0
    total = 0
    log = []
    for item in items:
        count += 1
        total += item
        log.append(item)
    average = total / count
    return average, log
'''
    renamed, _ = obfuscate_identifiers(sample)
    shuffled, _ = shuffle_ast(sample, seed=42)
    result = run_manipulation_check(sample, renamed, shuffled)
    for k, v in result.items():
        print(f"{k}: {v}")