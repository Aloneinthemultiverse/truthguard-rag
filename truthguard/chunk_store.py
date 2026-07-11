"""FR-2.1/2.2 — chunk store: quantized vector index (turbovec, numpy fallback) + BM25.

build_index(): chunks.json -> embeddings -> turbovec index (or float32 .npy)
ChunkStore.vector_search / keyword_search return (chunk_id, score) lists.
"""
import os
import re
import json

import numpy as np

from . import config

_TOK = re.compile(r"[a-zA-Z0-9_]+")


def _tokenize(text: str) -> list:
    return [t.lower() for t in _TOK.findall(text)]


class ChunkStore:
    def __init__(self, storage_dir: str = None):
        self.storage_dir = storage_dir or config.STORAGE_DIR
        cp = os.path.join(self.storage_dir, "chunks.json")
        if os.path.exists(cp):
            with open(cp, encoding="utf-8") as f:
                self.chunks = json.load(f)
        else:
            self.chunks = []    # empty workspace: valid state, downstream refuses gracefully
        self.by_id = {c["id"]: c for c in self.chunks}
        self._embedder = None
        self._vectors = None          # numpy fallback matrix
        self._tv_index = None         # turbovec index
        self._ids = [c["id"] for c in self.chunks]
        self._bm25 = None
        self._load_indices()

    # ── embedding model (local, lazy) ────────────────────────────────────────
    @property
    def embedder(self):
        if self._embedder is None:
            from sentence_transformers import SentenceTransformer
            self._embedder = SentenceTransformer(config.EMBED_MODEL)
        return self._embedder

    def _embed(self, texts: list) -> np.ndarray:
        v = self.embedder.encode(texts, normalize_embeddings=True)
        return np.asarray(v, dtype=np.float32)

    # ── index build / load ───────────────────────────────────────────────────
    def build(self):
        texts = [c["text"] for c in self.chunks]
        vecs = self._embed(texts)
        np.save(os.path.join(self.storage_dir, "vectors.npy"), vecs)
        # try turbovec quantized index on top
        engine = "numpy-float32"
        try:
            import turbovec
            idx = turbovec.TurboQuantIndex(vecs.shape[1], 4)
            idx.add(vecs)
            try:
                idx.prepare()
            except Exception:
                pass
            idx.write(os.path.join(self.storage_dir, "turbovec.idx"))
            engine = "turbovec-4bit"
        except Exception as e:
            print(f"  turbovec unavailable ({e}); using numpy float32")
        with open(os.path.join(self.storage_dir, "index_meta.json"), "w") as f:
            json.dump({"engine": engine, "count": len(texts)}, f)
        self._load_indices()
        return engine

    def _load_indices(self):
        vp = os.path.join(self.storage_dir, "vectors.npy")
        if os.path.exists(vp):
            self._vectors = np.load(vp)
        tvp = os.path.join(self.storage_dir, "turbovec.idx")
        if os.path.exists(tvp):
            try:
                import turbovec
                self._tv_index = turbovec.TurboQuantIndex.load(tvp)
            except Exception:
                self._tv_index = None
        try:
            from rank_bm25 import BM25Okapi
            self._bm25 = (BM25Okapi([_tokenize(c["text"]) for c in self.chunks])
                          if self.chunks else None)
        except ImportError:
            self._bm25 = None

    # ── search ───────────────────────────────────────────────────────────────
    def vector_search(self, query: str, k: int = 25) -> list:
        if self._vectors is None:
            return []
        q = self._embed([query])[0]
        if self._tv_index is not None:
            try:
                scores, idxs = self._tv_index.search(q.reshape(1, -1), k=min(k, len(self._ids)))
                return [(self._ids[int(i)], float(s))
                        for s, i in zip(scores[0], idxs[0])]
            except Exception:
                pass
        sims = self._vectors @ q          # vectors normalized -> cosine
        top = np.argsort(sims)[::-1][:k]
        return [(self._ids[i], float(sims[i])) for i in top]

    def keyword_search(self, query: str, k: int = 25) -> list:
        if self._bm25 is None:
            return []
        scores = self._bm25.get_scores(_tokenize(query))
        top = np.argsort(scores)[::-1][:k]
        return [(self._ids[i], float(scores[i])) for i in top if scores[i] > 0]

    def max_similarity(self, query: str) -> float:
        """Corpus-level sufficiency signal (FR-3.1)."""
        hits = self.vector_search(query, k=1)
        return hits[0][1] if hits else 0.0


def build_index(storage_dir: str = None) -> str:
    store = ChunkStore(storage_dir)
    return store.build()


if __name__ == "__main__":
    engine = build_index()
    print(f"index built: {engine}")
