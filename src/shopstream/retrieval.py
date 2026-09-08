"""Hybrid retrieval: vector + BM25, fused with RRF, then reranked."""

from __future__ import annotations

from dataclasses import dataclass

import voyageai

from shopstream.config import Settings
from shopstream.embeddings import Embedder
from shopstream.store import Store

RRF_K = 60          # standard constant; damps the influence of low ranks

@dataclass
class Hit:
    chunk_id : str
    text: str
    doc_path: str
    doc_title: str
    heading_path: str
    score: float
    vector_rank: int | None = None
    keyword_rank: int | None = None
    rerank_score: float | None = None

def reciprocal_rank_fusion(
    ranked_lists: list[list[tuple[str, float]]], k: int = RRF_K
) -> dict[str, float]:
    """Score = sum over lists of 1/(k + rank). Rank-based, so the two searches'
    incomparable score scales never have to be calibrated against each other."""
    fused: dict[str,float] = {}
    for ranked in ranked_lists:
        for rank, (chunk_id, _score) in enumerate(ranked, start = 1):
            fused[chunk_id] = fused.get(chunk_id, 0.0) + 1.0 / (k + rank)
    return fused

class Retriever:
    def __init__(self, settings: Settings, store: Store, embedder: Embedder):
        self.s = settings
        self.store = store
        self.embedder = embedder
        self._voyage = voyageai.Client(api_key=settings.voyage_key)

    def search(self, query: str, top_k: int | None = None) -> list[Hit]:
        top_k = top_k or self.s.top_k_final

        vec_hits = self.store.vector_search(
            self.embedder.embed_query(query), self.s.top_k_vector
        )
        kw_hits = self.store.keyword_search(query, self.s.top_k_keyword) 

        vec_rank = {cid: i + 1 for i, (cid, _) in enumerate(vec_hits)}
        kw_rank = {cid: i + 1 for i, (cid, _) in enumerate(kw_hits)}
        fused = reciprocal_rank_fusion([vec_hits, kw_hits])

        if not fused:
            return[]
        # Rerank a wider candidate set than we will keep — the reranker is the
        # precision stage, so give it something to work with. 
        candidate_ids = sorted(fused, key=lambda c: -fused[c])[: max(top_k * 4, 20)]
        rows = self.store.get(candidate_ids)
        candidate_ids = [c for c in candidate_ids if c in rows]
        texts = [rows[c]["text"] for c in candidate_ids]

        reranked = self._voyage.rerank(
            query, texts, model=self.s.rerank_model, top_k=top_k
        )

        hits: list[Hit] = []
        for r in reranked.results:
            cid = candidate_ids[r.index]
            row = rows[cid]
            hits.append(Hit(
                chunk_id=cid, text=row["text"], doc_path=row["doc_path"],
                doc_title=row["doc_title"], heading_path=row["heading_path"],
                score=fused[cid], vector_rank=vec_rank.get(cid),
                keyword_rank=kw_rank.get(cid), rerank_score=r.relevance_score,
            ))
        return hits

def hits_to_search_results(hits: list[Hit]) -> list[dict]:
    """Convert hits into Anthropic `search_result` content blocks. These are what
    make API-native citations possible: the model cites blocks, not free text."""

    return [
        {
            "type": "search_result",
            "source": f"kb://{h.doc_path}#{h.chunk_id}",
            "title": h.heading_path,
            "content": [{"type": "text", "text": h.text}],
            "citations": {"enabled": True}, 
        }
        for h in hits
    ]    