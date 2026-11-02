"""evals/run_evals.py — the harness. Run it before and after every change."""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

from shopstream.config import EVALS_DIR, load_settings


THRESHOLDS = {
    "retrieval_recall": 0.90,
    "citation_rate": 0.85,
    "keyword_accuracy": 0.90,
    "judge_score": 4.0,
}

def retrieval_recall(case: dict, answer) -> float | None:
    """Did retrieval surface at least one chunk from each expected source doc?
    Measured on retrieval alone — independent of how well the model wrote."""
    expected = case.get("expected_sources")
    if not expected:
        return None
    got = {cid.split("#")[0] for cid in answer.retrieved_doc_paths}
    return sum(1 for e in expected if e in got) / len(expected)

def citation_rate(case: dict, answer) -> float | None:
    """Fraction of answers that are actually grounded: a factual answer with no
    citations means the model spoke from memory.""" 

    if case.get("expect_refusal"):
        return None
    return 1.0 if answer.citations else 0.0

def keyword_accuracy(case: dict, answer) -> float | None:
    """Cheap, deterministic substring checks. Catches the wrong-number failures
    that an LLM judge is surprisingly willing to forgive."""

    text = answer.text.lower()
    checks: list[bool] = []
    for s in case.get("must_contain", []):
        checks.append(s.lower() in text)
    for s in case.get("must_not_contain", []):
        checks.append(s.lower() not in text)
    return (sum(checks) / len(checks)) if checks else None