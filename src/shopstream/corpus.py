from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from shopstream.config import CORPUS_DIR, Settings

@dataclass
class Chunk:
    chunk_id: str          # stable hash - survives re-ingest if text is unchanged
    doc_path: str          # "policies/returns.md"
    doc_title: str         # "Returns Policy"
    heading_path: str      # "Returns Policy > Opened items"  - breadcrumb for the model
    text: str
    position: int          # order within the document

def _title_of(md: str, fallback: str) -> str:
    m = re.search(r"^#\s+(.+)$", md, re.MULTILINE) 
    return m.group(1).strip() if m else fallback

def _split_sections(md: str) -> list[tuple[str, str]]:
    """Split on markdown headings, keeping the heading breadcrumb with each body.""" 
    lines = md.splitlines()
    sections: list[tuple[str, str]] = []
    stack: list[str] = []
    buf: list[str] = []

    def flush() -> None:
        body = "\n".join(buf).strip()
        if body:
            sections.append((" > ".join(stack), body))

    for line in lines:
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            flush()
            buf = []
            level = len(m.group(1))
            stack = stack[: level - 1] + [m.group(2).strip()]
        else:
            buf.append(line)
    flush()
    return sections

def _pack(body: str, target: int, overlap: int) -> list[str]:
    """Pack paragraphs up to ~target chars; carry `overlap` chars into the next chunk."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    out: list[str] = []
    cur = ""
    for p in paras:
        if cur and len(cur) + len(p) + 2 > target:
            out.append(cur)
            cur = (cur[-overlap:] + "\n\n" + p) if overlap else p
        else:
            cur = f"{cur}\n\n{p}" if cur else p
    if cur:
        out.append(cur)
    return out

def load_chunks(settings: Settings, corpus_dir: Path = CORPUS_DIR) -> list[Chunk]:
    chunks: list[Chunk] = []
    for path in sorted(corpus_dir.rglob("*.md")):
        rel = path.relative_to(corpus_dir).as_posix()
        md = path.read_text(encoding="utf-8")
        title = _title_of(md, path.stem)
        position = 0
        for heading, body in _split_sections(md):
            for piece in _pack(body, settings.chunk_target_chars,
                               settings.chunk_overlap_chars):
                breadcrumb = f"{title} > {heading}" if heading else title
                # What gets embedded includes the breadcrumb: a chunk that says
                # "You have 30 days" is meaningless without "Returns Policy".
                text = f"[{breadcrumb}]\n{piece}"
                digest = hashlib.sha256(f"{rel}:{text}".encode()).hexdigest()[:16]
                chunks.append(Chunk(digest, rel, title, breadcrumb, text, position))
                position += 1
    return chunks                