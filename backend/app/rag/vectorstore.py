import json
import os
from datetime import datetime, timezone
from functools import lru_cache

import faiss
import numpy as np
from openai import OpenAI
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import Chunk
from app.rag.config_store import DEFAULT_CONFIG, EMBEDDING_MODELS, REINDEX_KEYS

settings = get_settings()
_openai_client: OpenAI | None = None


def _client() -> OpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = OpenAI(api_key=settings.openai_api_key)
    return _openai_client


def embed_texts(texts: list[str], model: str | None = None) -> np.ndarray:
    """Embed a batch of texts with an OpenAI embedding model, L2-normalized for cosine similarity via
    inner product. `model` defaults to the env-configured one; the vector store always passes the
    model its INDEX was built with, so queries and indexed chunks can never be embedded differently."""
    model = model or settings.openai_embedding_model
    if not texts:
        return np.zeros((0, EMBEDDING_MODELS.get(model, 3072)), dtype="float32")
    resp = _client().embeddings.create(model=model, input=texts)
    vecs = np.array([d.embedding for d in resp.data], dtype="float32")
    faiss.normalize_L2(vecs)
    return vecs


class VectorStore:
    """FAISS flat inner-product index over ALL chunks in the corpus, plus parallel metadata
    arrays (chunk_id, product_id) in row order. Always rebuilt fully from the SQLite Chunk table
    (the source of truth) rather than mutated incrementally - simplest correct approach at this
    corpus scale (single-digit MB). Retrieval filters by product_id after the similarity search,
    which is fine because ntotal is small.

    `self.meta` records how the index was built (embedding model, chunking settings, when). Queries
    are embedded with meta["embedding_model"], never with the live admin config, so changing the
    configured embedding model can't corrupt retrieval before a re-index has actually rebuilt it."""

    def __init__(self) -> None:
        self.index: faiss.Index | None = None
        self.chunk_ids: list[str] = []
        self.product_ids: list[str] = []
        self.meta: dict = self._legacy_meta()
        self._index_path = os.path.join(settings.vector_index_dir, "index.faiss")
        self._meta_path = os.path.join(settings.vector_index_dir, "meta.json")
        self._load_from_disk()

    @staticmethod
    def _legacy_meta() -> dict:
        """Indexes built before build info was recorded were all made with the env-configured model
        and the default chunking settings - that's what they're assumed to be."""
        return {
            "embedding_model": settings.openai_embedding_model,
            "chunking_strategy": DEFAULT_CONFIG["chunking_strategy"],
            "chunk_size_chars": DEFAULT_CONFIG["chunk_size_chars"],
            "chunk_overlap_chars": DEFAULT_CONFIG["chunk_overlap_chars"],
            "built_at": None,
        }

    @property
    def embedding_model(self) -> str:
        return self.meta["embedding_model"]

    def _load_from_disk(self) -> None:
        if os.path.exists(self._index_path) and os.path.exists(self._meta_path):
            self.index = faiss.read_index(self._index_path)
            with open(self._meta_path) as f:
                meta = json.load(f)
            self.chunk_ids = meta["chunk_ids"]
            self.product_ids = meta["product_ids"]
            self.meta = {**self._legacy_meta(), **meta.get("index", {})}

    def _save_to_disk(self) -> None:
        """Write both files to temp names then rename, so a crash mid-save can't leave an index file
        that doesn't match its metadata."""
        os.makedirs(settings.vector_index_dir, exist_ok=True)
        faiss.write_index(self.index, self._index_path + ".tmp")
        with open(self._meta_path + ".tmp", "w") as f:
            json.dump({"chunk_ids": self.chunk_ids, "product_ids": self.product_ids, "index": self.meta}, f)
        os.replace(self._index_path + ".tmp", self._index_path)
        os.replace(self._meta_path + ".tmp", self._meta_path)

    def matches_config(self, cfg: dict) -> bool:
        """True when the index was built with the same chunking/embedding settings as `cfg`."""
        return all(self.meta.get(k) == cfg[k] for k in REINDEX_KEYS)

    def build_arrays(self, rows: list[tuple[str, str, str]], embedding_model: str):
        """Embed (chunk_id, product_id, text) rows with `embedding_model` and return a NEW index plus
        its metadata arrays WITHOUT touching the live index - lets a re-index do the failure-prone
        network call first and only swap once it has fully succeeded."""
        texts = [r[2] for r in rows]
        if texts:
            vecs = embed_texts(texts, embedding_model)
            index = faiss.IndexFlatIP(vecs.shape[1])
            index.add(vecs)
        else:
            index = faiss.IndexFlatIP(EMBEDDING_MODELS.get(embedding_model, 3072))
        return index, [r[0] for r in rows], [r[1] for r in rows]

    def install(self, index, chunk_ids: list[str], product_ids: list[str], cfg: dict) -> None:
        self.index = index
        self.chunk_ids = chunk_ids
        self.product_ids = product_ids
        self.meta = {
            "embedding_model": cfg["embedding_model"],
            "chunking_strategy": cfg["chunking_strategy"],
            "chunk_size_chars": cfg["chunk_size_chars"],
            "chunk_overlap_chars": cfg["chunk_overlap_chars"],
            "built_at": datetime.now(timezone.utc).isoformat(),
            "chunk_count": len(chunk_ids),
        }
        self._save_to_disk()

    def rebuild(self, db: Session, cfg: dict) -> None:
        """Rebuild the index from whatever chunks are currently in the DB, using cfg's embedding
        model. Callers that change HOW chunks are made must go through ingest.reindex_all instead."""
        chunks = db.query(Chunk).order_by(Chunk.document_id, Chunk.chunk_index).all()
        rows = [(c.id, c.product_id, c.text) for c in chunks]
        index, chunk_ids, product_ids = self.build_arrays(rows, cfg["embedding_model"])
        self.install(index, chunk_ids, product_ids, cfg)

    def search(self, query_text: str, product_id: str, top_k: int) -> list[tuple[str, float]]:
        """Returns [(chunk_id, cosine_score), ...] restricted to product_id, best first."""
        if self.index is None or self.index.ntotal == 0:
            return []
        qvec = embed_texts([query_text], self.embedding_model)
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
