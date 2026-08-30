from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

CORPUS_DIR = PROJECT_ROOT / "corpus"
DATA_DIR = PROJECT_ROOT / "data"
PROMPTS_DIR = PROJECT_ROOT / "prompts"
EVALS_DIR = PROJECT_ROOT / "evals"

# USD per 1M tokens, as of August 2026. Keep this table honest — every cost
# number you publish depends on it.

PRICING = {
    "claude-opus-5":    {"input": 5.00, "output": 25.00},
    "claude-sonnet-5":  {"input": 2.00, "output": 10.00},
    "claude-haiku-4-5": {"input": 1.00, "output":  5.00},
}
CACHE_WRITE_MULTIPLIER = 1.25      # 5-minute cache write
CACHE_READ_MULTIPLIER = 0.10       # cache hit

@dataclass(frozen=True)
class Settings:
    anthropic_key: str
    voyage_key: str
    answer_model: str
    judge_model: str
    cheap_model: str
    embed_model: str
    rerank_model: str
    top_k_vector: int
    top_k_keyword: int
    top_k_final: int
    chunk_target_chars: int
    chunk_overlap_chars: int
    db_path: Path = DATA_DIR / "store.sqlite"
    traces_path: Path = DATA_DIR / "traces.jsonl"

def load_settings() -> Settings:
    missing = [k for k in ("ANTHROPIC_API_KEY", "VOYAGE_API_KEY") if not os.getenv(k)]
    if missing:
        raise SystemExit(f"Missing environment variables: {', '.join(missing)}. "
                         "Copy .env.example to .env and fill them in.")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return Settings(
        anthropic_key=os.environ["ANTHROPIC_API_KEY"],
        voyage_key=os.environ["VOYAGE_API_KEY"],
        answer_model=os.getenv("ANSWER_MODEL", "claude-sonnet-5"),
        judge_model=os.getenv("JUDGE_MODEL", "claude-sonnet-5"),
        cheap_model=os.getenv("CHEAP_MODEL", "claude-haiku-4-5"),
        embed_model=os.getenv("EMBED_MODEL", "voyage-4"),
        rerank_model=os.getenv("RERANK_MODEL", "rerank-2.5"),
        top_k_vector=int(os.getenv("TOP_K_VECTOR", "20")),
        top_k_keyword=int(os.getenv("TOP_K_KEYWORD", "20")),
        top_k_final=int(os.getenv("TOP_K_FINAL", "6")),
        chunk_target_chars=int(os.getenv("CHUNK_TARGET_CHARS", "1200")),
        chunk_overlap_chars=int(os.getenv("CHUNK_OVERLAP_CHARS", "150")),
    )