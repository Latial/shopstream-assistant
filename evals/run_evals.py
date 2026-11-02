"""evals/run_evals.py — the harness. Run it before and after every change."""

from __future__ import annotations

import argparse
import json
import sqlite3
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

import anthropic

from shopstream.assistant import Assistant
from shopstream.config import DATA_DIR, EVALS_DIR, load_settings
from shopstream.embeddings import Embedder
from shopstream.retrieval import Retriever
from shopstream.store import Store
from shopstream.tools import ToolBox
from shopstream.tracing import cost_usd


THRESHOLDS = {
    "retrival_recall": 0.90,
    "citation_rate": 0.85,
    "keyword_accuracy": 0.90,
    "judge_score": 4.0,
}

def retrival_recall(case: dict, answer) -> float | None:
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

DETERMINISTIC = {
    "retrival_recall": retrival_recall,
    "citation_rate": citation_rate,
    "keyword_accuracy" : keyword_accuracy,
}
# Fail at startup, not silently, if a metric and its threshold drift apart.
assert set(DETERMINISTIC) | {"judge_score"} == set(THRESHOLDS), \
    "metric names and THRESHOLDS keys differ"

def load_cases(path: Path) -> list[dict]:
    """One JSON object per line; blank lines and // comments are skipped."""
    cases = []
    for n, line in enumerate(path.read_text(encoding='utf-8').splitlines(), start=1):
        line = line.strip()
        if not line or line.startswith("//"):
           continue
        try:
           cases.append(json.loads(line))
        except json.JSONDecodeError as e:
           raise SystemExit(f"{path.name} line {n}: invalid JSON ({e})")
    return cases 

def build_assistant(settings) -> Assistant:
    """The same wiring as `shopstream ask`, so the eval tests what users get.""" 
    db = sqlite3.connect(settings.db_path)
    db.row_factory = sqlite3.Row
    retriever = Retriever(settings, Store(settings.db_path), Embedder(settings))
    return Assistant(settings, ToolBox(retriever, db))

def judge(client, settings, case: dict, answer) -> dict:
    """LLM-as-judge, graded against the reference answer at temperature 0."""
    template = (EVALS_DIR / "judge.md").read_text(encoding="utf-8")
    sources = "; ".join(c.title or c.source for c in answer.citations) or "(none)"
    prompt = template.format(
        question=case["question"],
        expected=case.get("expected_answer", ""),
        actual=answer.text,
        sources=sources
    )
    response = client.messages.create(
        model=settings.judge_model,
        max_tokens=200,
        temperature=0,
        messages=[{"role": "user", "content":prompt}],
    )
    raw= "".join(b.text for b in response.content if b.type == "text")
    usage = (response.usage.input_tokens, response.usage.output_tokens)
    try:
        parsed = json.loads(raw[raw.index("{"): raw.rindex("}") + 1])
        return {"score": float(parsed["score"]),
                "reason": parsed.get("reason", ""), "usage":usage}
    except (ValueError, KeyError, TypeError):
        return {"score": 1.0, "reason": f"judge output unparseable: {raw[:120]!r}", "usage": usage}