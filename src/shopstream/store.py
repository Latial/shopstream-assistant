"""SQLite store: chunks, their FTS5 keyword index, and their embedding blobs."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np

from shopstream.corpus import Chunk

SCHEMA = """
CREATE TABLE IF NOT EXISTS chunks (
    chunk_id      TEXT PRIMARY KEY,
    doc_path      TEXT NOT NULL,
    doc_title     TEXT NOT NULL,
    heading_path  TEXT NOT NULL,
    position      INTEGER NOT NULL,
    text          TEXT NOT NULL,
    embedding     BLOB                       -- float32 vector, normalised
);

CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    text,
    chunk_id UNINDEXED,
    tokenize = 'porter unicode61'
);
"""

class Store:
    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(db_path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)
        self._matrix: np.ndarray | None = None      # lazily build vector index

    # ---- writing ---------------------------------------------------------
    def replace_all(self, chunks: list[Chunk], vectors: np.ndarray) -> None:
        """Full re-ingest: the corpus is the source of truth, the store is a cache."""
        with self.db:
            self.db.execute("DELETE FROM chunks")
            self.db.execute("DELETE FROM chunks_fts")
            self.db.executemany(
                "INSERT INTO chunks (chunk_id, doc_path, doc_title, heading_path,"
                " position, text, embedding) VALUES (?, ?, ?, ?, ?, ?, ?)",
                [(c.chunk_id, c.doc_path, c.doc_title, c.heading_path, c.position,
                  c.text, vectors[i].tobytes())
                  for i, c in enumerate(chunks)],
            )            
            self.db.executemany(
                "INSERT INTO chunks_fts (text, chunk_id) VALUES (?, ?)",
                [(c.text, c.chunk_id) for c in chunks]
            )
        self._matrix = None

    # ---- reading ---------------------------------------------------------
    def _load_matrix(self) -> None:
        rows = self.db.execute(
            "SELECT chunk_id, embedding FROM chunks ORDER BY rowid").fetchall()
        self._ids = [r["chunk_id"] for r in rows]
        self._matrix = np.vstack(
            [np.frombuffer(r["embedding"], dtype=np.float32) for r in rows]
        ) if rows else np.empty((0,0), dtype=np.float32)

    def vector_search(self, query_vec: np.ndarray, k: int) -> list[tuple[str, float]]:
        if self._matrix is None:
            self._load_matrix()
        if self._matrix.size == 0:
            return []
        scores = self._matrix @ query_vec          # unit vectors → cosine similarity
        top = np.argsort(-scores)[:k]
        return [(self._ids[i], float(scores[i])) for i in top]

    def keyword_search(self, query: str, k: int) -> list[tuple[str, float]]:
        """BM25 via FTS5. Lower bm25() is better, so negate it for a 'higher is
        better' score. Quote the query so user punctuation can't be FTS syntax."""
        safe = '"' + query.replace('"', " ") + '"'
        rows = self.db.execute(
            "SELECT chunk_id, bm25(chunks_fts) AS score FROM chunks_fts "
            "WHERE chunks_fts MATCH ? ORDER BY score LIMIT ?", (safe, k)).fetchall()
        return [(r["chunk_id"], -float(r["score"])) for r in rows]   

    def get(self, chunk_ids: list[str]) -> dict[str, sqlite3.Row]:
        if not chunk_ids:
            return {}
        marks = ",".join("?" * len(chunk_ids))
        rows =  self.db.execute(
            f"SELECT * FROM chunks WHERE chunk_id in ({marks})", chunk_ids
        ).fetchall()
        return {r["chunk_ids"]: r for r in rows}

    def count(self) -> int:
        return self.db.execute("SELECT COUNT(*) AS n FROM chunks").fetchone()["n"]       

    