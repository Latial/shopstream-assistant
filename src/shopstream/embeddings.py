from __future__ import annotations

import numpy as np
import voyageai

from shopstream.config import Settings

class Embedder:
    """Wraps Voyage AI. The interface is deliberately two methods wide:
    anything that can embed documents and queries can replace this."""  

    def __init__(self, settings: Settings):
        self._client = voyageai.Client(api_key=settings.voyage_key)
        self._model = settings.embed_model
        self.dim: int | None = None         #discovered on first call

    def _embed(self, texts: list[str], input_type: str) -> np.ndarray:
        vectors: list[list[float]] = []
        for i in range(0, len(texts), 64):
            batch = texts[i : i + 64]
            result = self._client.embed(batch, model=self._model,
                                        input_type=input_type)
            vectors.extend(result.embeddings)
        arr = np.array(vectors, dtype=np.float32)
        # Normalise once here, so cosine similarity is a plain dot product later.
        arr /= np.linalg.norm(arr, axis=1, keepdims=True)
        self.dim = arr.shape[1]
        return arr

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        return self._embed(texts, "document")

    def embed_query(self, text:str) -> np.ndarray:
        return self._embed([text], "query")[0]        