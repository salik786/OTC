import json
import os
from functools import lru_cache

import faiss
import numpy as np
from openai import OpenAI
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import Chunk

settings = get_settings()
_openai_client: OpenAI | None = None


def _client() -> OpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = OpenAI(api_key=settings.openai_api_key)
    return _openai_client


def embed_texts(texts: list[str]) -> np.ndarray:
    """Embed a batch of texts with the configured OpenAI model, L2-normalized for cosine
    similarity via inner product."""
    if not texts:
        return np.zeros((0, 3072), dtype="float32")
    resp = _client().embeddings.create(model=settings.openai_embedding_model, input=texts)
    vecs = np.array([d.embedding for d in resp.data], dtype="float32")
    faiss.normalize_L2(vecs)
    return vecs


class VectorStore:
    """FAISS flat inner-product index over ALL chunks in the corpus, plus parallel metadata
    arrays (chunk_id, product_id) in row order. Always rebuilt fully from the SQLite Chunk table
    (the source of truth) rather than mutated incrementally - simplest correct approach at this
    corpus scale (single-digit MB). Retrieval filters by product_id after the similarity search,
    which is fine because ntotal is small."""

    def __init__(self) -> None:
        self.index: faiss.Index | None = None
        self.chunk_ids: list[str] = []
        self.product_ids: list[str] = []
        self._index_path = os.path.join(settings.vector_index_dir, "index.faiss")
        self._meta_path = os.path.join(settings.vector_index_dir, "meta.json")
        self._load_from_disk()

    def _load_from_disk(self) -> None:
        if os.path.exists(self._index_path) and os.path.exists(self._meta_path):
            self.index = faiss.read_index(self._index_path)
            with open(self._meta_path) as f:
                meta = json.load(f)
            self.chunk_ids = meta["chunk_ids"]
            self.product_ids = meta["product_ids"]

    def _save_to_disk(self) -> None:
        os.makedirs(settings.vector_index_dir, exist_ok=True)
        faiss.write_index(self.index, self._index_path)
        with open(self._meta_path, "w") as f:
            json.dump({"chunk_ids": self.chunk_ids, "product_ids": self.product_ids}, f)

    def rebuild(self, db: Session) -> None:
        chunks = db.query(Chunk).order_by(Chunk.document_id, Chunk.chunk_index).all()
        if not chunks:
            self.index = faiss.IndexFlatIP(3072)
            self.chunk_ids = []
            self.product_ids = []
            self._save_to_disk()
            return

        texts = [c.text for c in chunks]
        vecs = embed_texts(texts)
        dim = vecs.shape[1]
        index = faiss.IndexFlatIP(dim)
        index.add(vecs)

        self.index = index
        self.chunk_ids = [c.id for c in chunks]
        self.product_ids = [c.product_id for c in chunks]
        self._save_to_disk()

    def search(self, query_text: str, product_id: str, top_k: int) -> list[tuple[str, float]]:
        """Returns [(chunk_id, cosine_score), ...] restricted to product_id, best first."""
        if self.index is None or self.index.ntotal == 0:
            return []
        qvec = embed_texts([query_text])
        k = self.index.ntotal  # search everything, filter by product below
        scores, idxs = self.index.search(qvec, k)
        results: list[tuple[str, float]] = []
        for score, idx in zip(scores[0], idxs[0]):
            if idx == -1:
                continue
            if self.product_ids[idx] != product_id:
                continue
            results.append((self.chunk_ids[idx], float(score)))
            if len(results) >= top_k:
                break
        return results


@lru_cache
def get_vectorstore() -> VectorStore:
    return VectorStore()
