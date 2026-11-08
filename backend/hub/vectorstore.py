"""Thin persistent wrapper around a FAISS inner-product index keyed by Chunk.pk."""
import threading

import faiss
import numpy as np
from django.conf import settings

_lock = threading.RLock()
_store = None


class FaissStore:
    def __init__(self, dim):
        self.dim = dim
        self.path = settings.FAISS_DIR / "index.faiss"
        settings.FAISS_DIR.mkdir(parents=True, exist_ok=True)
        self.index = self._load()

    def _new(self):
        return faiss.IndexIDMap2(faiss.IndexFlatIP(self.dim))

    def _load(self):
        if self.path.exists():
            idx = faiss.read_index(str(self.path))
            if idx.d == self.dim:
                return idx
        return self._new()

    def add(self, ids, vectors):
        with _lock:
            self.index.add_with_ids(np.ascontiguousarray(vectors, dtype="float32"),
                                    np.asarray(ids, dtype="int64"))
            self.save()

    def remove(self, ids):
        if not len(ids):
            return
        with _lock:
            self.index.remove_ids(np.asarray(ids, dtype="int64"))
            self.save()

    def search(self, vector, k):
        with _lock:
            if self.index.ntotal == 0:
                return []
            scores, ids = self.index.search(np.ascontiguousarray(vector, dtype="float32"), k)
        return [(int(i), float(s)) for i, s in zip(ids[0], scores[0]) if i != -1]

    def reset(self):
        with _lock:
            self.index = self._new()
            self.save()

    def save(self):
        faiss.write_index(self.index, str(self.path))

    @property
    def count(self):
        return self.index.ntotal


def get_store():
    global _store
    from .embeddings import get_embedder
    with _lock:
        if _store is None:
            _store = FaissStore(get_embedder().dim)
        return _store


def reset_singletons():
    global _store
    _store = None
