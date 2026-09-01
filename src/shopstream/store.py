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