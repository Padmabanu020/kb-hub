import hashlib
import re
import threading

import numpy as np
from django.conf import settings

_lock = threading.Lock()
_embedder = None


class HashEmbedder:
    """Deterministic bag-of-words hashing embedder. Offline fallback for tests/demos."""
    dim = 384

    def encode(self, texts):
        out = np.zeros((len(texts), self.dim), dtype="float32")
        for i, t in enumerate(texts):
            for w in re.findall(r"[a-z0-9]+", t.lower()):
                h = int(hashlib.md5(w.encode()).hexdigest(), 16)
                out[i, h % self.dim] += 1.0 if (h >> 100) & 1 else -1.0
        n = np.linalg.norm(out, axis=1, keepdims=True)
        n[n == 0] = 1
        return out / n


class STEmbedder:
    def __init__(self, name):
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer(name)
        self.dim = self.model.get_sentence_embedding_dimension()

    def encode(self, texts):
        return self.model.encode(list(texts), batch_size=32, normalize_embeddings=True,
                                 show_progress_bar=False).astype("float32")


def get_embedder():
    global _embedder
    with _lock:
        if _embedder is None:
            name = settings.EMBEDDING_MODEL
            _embedder = HashEmbedder() if name == "hash" else STEmbedder(name)
        return _embedder
