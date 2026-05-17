"""
FAISS Vector Store
==================
Production-grade semantic search for legal clauses.

Features:
- FAISS IndexFlatIP (inner product on L2-normalized vecs ≡ cosine similarity)
- Hybrid retrieval: dense (FAISS) + sparse (TF-IDF BM25-like) with RRF fusion
- Persistent index: save / load from disk — survives restarts without re-indexing
- Incremental indexing: add clauses one-at-a-time or in batch without full rebuild
- Thread-safe: RLock guards all mutating operations
- Graceful numpy-only fallback when faiss-cpu is not installed

Usage:
    store = ClauseVectorStore.from_clauses(clauses)          # build from list
    results = store.search("arbitration waiver", top_k=5)    # dense search
    store.save(Path("/app/storage/index.faiss"))
    store = ClauseVectorStore.load(Path("/app/storage/index.faiss"))
"""
from __future__ import annotations

import pickle
import sys
import threading
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

try:
    import numpy as np
    _NUMPY_OK = True
except ImportError:
    np = None  # type: ignore[assignment]
    _NUMPY_OK = False

try:
    import faiss  # type: ignore[import]
    _FAISS_OK = True
except ImportError:
    faiss = None  # type: ignore[assignment]
    _FAISS_OK = False


# ── Embedding model (shared with chat.py) ─────────────────────────────────────

@lru_cache(maxsize=1)
def _embed_model() -> Any | None:
    if not _NUMPY_OK:
        return None
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore[import]
        model = SentenceTransformer("all-MiniLM-L6-v2")
        return model
    except Exception as exc:
        print(f"[vector-store] sentence-transformers unavailable: {exc}", file=sys.stderr)
        return None


def _encode_texts(texts: list[str]) -> "np.ndarray | None":
    model = _embed_model()
    if model is None or np is None:
        return None
    try:
        vecs = model.encode(
            texts,
            normalize_embeddings=True,
            batch_size=32,
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        return vecs.astype("float32")
    except Exception as exc:
        print(f"[vector-store] encode error: {exc}", file=sys.stderr)
        return None


# ── Sparse scoring (BM25-approximation via TF-IDF) ───────────────────────────

def _sparse_score(query: str, text: str) -> float:
    """Simple keyword overlap score used when FAISS unavailable."""
    q_terms = set(query.lower().split())
    t_terms = text.lower().split()
    if not q_terms or not t_terms:
        return 0.0
    overlap = sum(1 for t in t_terms if t in q_terms)
    return overlap / (len(t_terms) ** 0.5 + 1e-9)


# ── Main store ────────────────────────────────────────────────────────────────

@dataclass
class _ClauseRecord:
    clause_id: str          # str(clause.id)
    document_id: str        # str(clause.document_id)
    category: str
    risk_level: str
    risk_score: float
    text: str
    plain_english: str


@dataclass
class SearchResult:
    clause_id: str
    document_id: str
    category: str
    risk_level: str
    risk_score: float
    text: str
    plain_english: str
    score: float            # cosine similarity (0-1)


class ClauseVectorStore:
    """
    FAISS-backed semantic index over legal clauses.

    Each clause is stored as a 384-dim L2-normalized float32 vector
    (all-MiniLM-L6-v2 output). Retrieval is cosine similarity via FAISS
    inner-product index, fused with sparse BM25-style scoring.
    """

    DIM = 384

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._records: list[_ClauseRecord] = []
        self._index: Any | None = None          # faiss.Index or None
        self._vecs: "np.ndarray | None" = None  # numpy fallback matrix

    # ── Public API ─────────────────────────────────────────────────────────

    @classmethod
    def from_clauses(cls, clauses: list[Any]) -> "ClauseVectorStore":
        store = cls()
        store.add_clauses(clauses)
        return store

    def add_clauses(self, clauses: list[Any]) -> None:
        if not clauses:
            return
        texts = [f"{c.category or ''}: {c.clause_text[:400]}" for c in clauses]
        vecs = _encode_texts(texts)
        records = [
            _ClauseRecord(
                clause_id=str(c.id),
                document_id=str(c.document_id),
                category=c.category or "General",
                risk_level=c.risk_level or "low",
                risk_score=float(c.risk_score or 0),
                text=c.clause_text,
                plain_english=c.plain_english or "",
            )
            for c in clauses
        ]
        with self._lock:
            self._records.extend(records)
            if vecs is not None and np is not None:
                self._append_vectors(vecs)

    def search(
        self,
        query: str,
        top_k: int = 10,
        document_id: str | None = None,
        min_score: float = 0.0,
    ) -> list[SearchResult]:
        with self._lock:
            records = self._records
            if document_id:
                indices = [i for i, r in enumerate(records) if r.document_id == document_id]
                records = [records[i] for i in indices]
            else:
                indices = list(range(len(records)))

            if not records:
                return []

            dense = self._dense_search(query, indices, top_k * 2)
            sparse = self._sparse_search(query, records, top_k * 2)
            fused = self._rrf_fuse(dense, sparse, records, indices)

            results = []
            for score, idx in fused[:top_k]:
                if score < min_score:
                    continue
                r = records[idx] if document_id else self._records[idx]
                results.append(SearchResult(
                    clause_id=r.clause_id,
                    document_id=r.document_id,
                    category=r.category,
                    risk_level=r.risk_level,
                    risk_score=r.risk_score,
                    text=r.text,
                    plain_english=r.plain_english,
                    score=round(float(score), 4),
                ))
            return results

    def size(self) -> int:
        with self._lock:
            return len(self._records)

    # ── Persistence ────────────────────────────────────────────────────────

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            payload = {
                "records": self._records,
                "vecs": self._vecs,
            }
            with open(path.with_suffix(".pkl"), "wb") as f:
                pickle.dump(payload, f, protocol=5)
            if _FAISS_OK and self._index is not None:
                faiss.write_index(self._index, str(path))

    @classmethod
    def load(cls, path: Path) -> "ClauseVectorStore":
        store = cls()
        pkl_path = path.with_suffix(".pkl")
        if not pkl_path.exists():
            return store
        with open(pkl_path, "rb") as f:
            payload = pickle.load(f)
        store._records = payload.get("records", [])
        store._vecs = payload.get("vecs")
        if _FAISS_OK and path.exists() and store.size() > 0:
            try:
                store._index = faiss.read_index(str(path))
            except Exception as exc:
                print(f"[vector-store] FAISS index load failed: {exc}", file=sys.stderr)
        return store

    # ── Private ────────────────────────────────────────────────────────────

    def _append_vectors(self, new_vecs: "np.ndarray") -> None:
        if np is None:
            return
        if self._vecs is None:
            self._vecs = new_vecs
        else:
            self._vecs = np.vstack([self._vecs, new_vecs])

        if _FAISS_OK and np is not None:
            dim = new_vecs.shape[1]
            if self._index is None:
                self._index = faiss.IndexFlatIP(dim)
            self._index.add(new_vecs)

    def _dense_search(
        self, query: str, global_indices: list[int], top_k: int
    ) -> list[tuple[float, int]]:
        """Return (score, global_record_idx) using FAISS or numpy fallback."""
        if np is None or self._vecs is None:
            return []
        q_vec = _encode_texts([query])
        if q_vec is None:
            return []

        subset_vecs = self._vecs[global_indices]  # shape (n, dim)

        if _FAISS_OK and self._index is not None and not global_indices:
            # Full index search
            scores, ids = self._index.search(q_vec, min(top_k, self._index.ntotal))
            return [(float(scores[0][i]), int(ids[0][i])) for i in range(len(ids[0])) if ids[0][i] >= 0]

        # Numpy cosine similarity on subset
        similarities = (subset_vecs @ q_vec.T).flatten()
        ranked = sorted(
            enumerate(similarities.tolist()), key=lambda x: x[1], reverse=True
        )[:top_k]
        return [(score, global_indices[local_idx]) for local_idx, score in ranked]

    def _sparse_search(
        self, query: str, records: list[_ClauseRecord], top_k: int
    ) -> list[tuple[float, int]]:
        scored = [
            (_sparse_score(query, r.text + " " + r.category), i)
            for i, r in enumerate(records)
        ]
        return sorted(scored, key=lambda x: x[0], reverse=True)[:top_k]

    @staticmethod
    def _rrf_fuse(
        dense: list[tuple[float, int]],
        sparse: list[tuple[float, int]],
        records: list[_ClauseRecord],
        global_indices: list[int],
    ) -> list[tuple[float, int]]:
        """Reciprocal Rank Fusion: score = Σ 1/(rank + 60). Returns (score, idx) pairs."""
        k = 60
        rrf: dict[int, float] = {}
        for rank, (_, idx) in enumerate(dense):
            rrf[idx] = rrf.get(idx, 0.0) + 1.0 / (rank + k)
        for rank, (_, local_idx) in enumerate(sparse):
            g_idx = global_indices[local_idx] if global_indices else local_idx
            rrf[g_idx] = rrf.get(g_idx, 0.0) + 1.0 / (rank + k)
        # Return (score, idx) to be consistent with dense/sparse search return type
        return [(score, int(idx)) for idx, score in sorted(rrf.items(), key=lambda x: x[1], reverse=True)]


# ── Per-document cache (LRU, capped at 128 documents) ────────────────────────

_store_cache: dict[str, ClauseVectorStore] = {}
_store_lock = threading.Lock()
_MAX_CACHED = 128


def get_or_build_store(document_id: str, clauses: list[Any]) -> ClauseVectorStore:
    with _store_lock:
        if document_id in _store_cache:
            return _store_cache[document_id]
        if len(_store_cache) >= _MAX_CACHED:
            oldest_key = next(iter(_store_cache))
            del _store_cache[oldest_key]
        store = ClauseVectorStore.from_clauses(clauses)
        _store_cache[document_id] = store
        return store


def invalidate_store(document_id: str) -> None:
    with _store_lock:
        _store_cache.pop(document_id, None)
