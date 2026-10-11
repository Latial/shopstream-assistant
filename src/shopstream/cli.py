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

def cmd_ask(args: argparse.Namespace) -> None:
    import sqlite3

    #from shopstream import tracing
    from shopstream.assistant import Assistant
    from shopstream.retrieval import Retriever
    from shopstream.tools import ToolBox

    settings = load_settings()
    db = sqlite3.connect(settings.db_path)
    db.row_factory = sqlite3.Row
    retriever = Retriever(settings, Store(settings.db_path), Embedder(settings))
    assistant = Assistant(settings, ToolBox(retriever, db))

    answer = assistant.ask(args.question)
    #trace = tracing.recond(settings.traces_path, args.question, settings.answer_model, answer)

    print(answer.text)

    if answer.citations:
        print("\nSources:")
        for i, c in enumerate(answer.citations, start=1):
            print(f" [{i}] {answer.tool_calls}")
    print(f"\ntools: {answer.tool_calls}")
    #print(f"{trace.latency_s}s ${trace.c}")

#def cmd_trace report - need to finish

def main() -> None:
    p = argparse.ArgumentParser(prog="shopstream",
                                description="RAG assistant over the ShopStream corpus")
    sub = p.add_subparsers(required=True)

    c = sub.add_parser("chunks", help="show how the corpus was chunked")
    c.add_argument("--limit", type=int, default=20)
    c.set_defaults(func=cmd_chunks)

    sub.add_parser("ingest", help="embed the corpus into the store") \
       .set_defaults(func=cmd_ingest)

    s = sub.add_parser("search", help="hybrid retrieval, no model call")
    s.add_argument("query")
    s.add_argument("-k", type=int, default=6)
    s.set_defaults(func=cmd_search)

    a = sub.add_parser("ask", help="ask the assistant a question")
    a.add_argument("question")
    a.set_defaults(func=cmd_ask)

   # sub.add_parser("trace-report", help="cost, latency and citation aggregates") \
    #   .set_defaults(func=cmd_trace_report)

    args = p.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()