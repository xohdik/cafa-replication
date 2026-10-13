"""
Interface stubs for the three operators that need infrastructure this
sandbox doesn't have (your entity-leakage tooling, an LLM/transpiler call,
or a template-generation pipeline). Fill in the bodies on the R740 side --
the interface contract is what matters for wiring into the orchestrator.
"""
from typing import Protocol


class DedupOperator(Protocol):
    """X1: repo-overlap removal / strict temporal cutoff.
    DO NOT rebuild this -- wire in the entity-level leakage tooling from the
    TOSEM pipeline directly. It already does this job."""
    def apply(self, sample: dict, corpus_index) -> dict: ...


class TranspileOperator(Protocol):
    """X4: cross-language rewrite.
    Recommended approach: LLM-based translation (better construct coverage
    than a rule-based transpiler across the language pairs you'll need),
    validated by executing the target-language test suite against both
    versions and requiring output equivalence before accepting a sample as
    a valid transpilation. Reject and redraw on validation failure rather
    than silently keeping a broken translation in the dataset -- a failed
    transpilation that gets scored as a semantic-reasoning failure will
    bias S_i(language) upward for reasons that have nothing to do with the
    model under test.
    """
    def apply(self, sample: dict, target_language: str) -> dict: ...

    def validate(self, original: dict, transpiled: dict) -> bool:
        """Must return False (and the caller must redraw) if behavioral
        equivalence cannot be confirmed via test execution."""
        ...


class SynthesizeOperator(Protocol):
    """X5: synthetic/counterfactual program generation.
    Match the real-code complexity distribution (cyclomatic complexity,
    line count, nesting depth) of the corresponding real sample so the
    synthetic condition isn't trivially easier or harder for reasons
    unrelated to reasoning -- that confound would otherwise show up folded
    into S_i(syntheticity) and be indistinguishable from a genuine
    abstract-reasoning effect.
    """
    def apply(self, reference_sample: dict) -> dict: ...


class PipelineRow(Protocol):
    """The contract each of the 16 design-matrix conditions must satisfy:
    all five operators chained on ONE underlying sample, in a fixed order
    (recommend: dedup/cutoff selection first since it operates on which
    samples enter the pool at all, then identifier/AST/language/
    syntheticity in any consistent order since those three are pure
    per-sample transforms and don't interact with sample selection)."""
    def build_condition(self, base_sample: dict, condition: dict) -> dict: ...
