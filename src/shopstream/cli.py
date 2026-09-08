from __future__ import annotations

import argparse

from shopstream.config import load_settings
from shopstream.corpus import load_chunks
from shopstream.embeddings import Embedder
from shopstream.store import Store

def cmd_chunks(args: argparse.Namespace) -> None:
    settings = load_settings()
    chunks = load_chunks(settings)
    print(f"{len(chunks)} chunks from {len({c.doc_path for c in chunks})} documents\n")
    for c in chunks[: args.limit]:
        print(f"{c.chunk_id} {len(c.text):>5} chars {c.heading_path}")

def cmd_ingest(args) -> None:
    settings = load_settings()
    chunks = load_chunks(settings)
    embedder = Embedder(settings)
    print(f"embedding {len(chunks)} chunks with {settings.embed_model} ...")
    vectors = embedder.embed_documents([c.text for c in chunks])
    store = Store(settings.db_path)
    store.replace_all(chunks, vectors)
    print(f"stored {store.count()} chunks, dim={vectors.shape[1]}")

def cmd_search(args: argparse.Namespace) -> None:
    from shopstream.retrieval import Retriever

    settings = load_settings()
    retriever = Retriever(settings, Store(settings.db_path), Embedder(settings))
    for i, h in enumerate(retriever.search(args.query, top_k=args.k), start=1):
        print(f"{i}. {h.heading_path}")
        print(f" vec_rank={h.vector_rank} kw_rank={h.keyword_rank} "
              f"rerank={h.rerank_score:.3f} ({h.doc_path})")

