"""Cache-backed embedder for the faithfulness eval.

Seeding the eval DB and embedding the gold questions must be reproducible: the
same text must always map to the same vector so a faithfulness score delta
reflects a code tweak and not embedding drift. ``CachedEmbedder`` reads vectors
from ``embeddings_cache.json`` keyed by sha256(text); on a miss it falls back to
the real ``HttpEmbedder`` once and persists the result so subsequent runs are
deterministic and offline.

The cache pins a single (model, dim) pair: the first warm-up decides which
embedding backend's vectors are stored, and retrieval at eval time uses the same
model name so ``embedding_model`` filtering in the vector/hybrid path lines up.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from app.embeddings import Embedder, HttpEmbedder

CACHE_PATH = Path(__file__).parent / "embeddings_cache.json"


def _key(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class CachedEmbedder(Embedder):
    """Embedder that serves vectors from a JSON cache, warming misses via HttpEmbedder."""

    def __init__(self, cache_path: Path | None = None, allow_live: bool = True):
        self._path = cache_path or CACHE_PATH
        self._allow_live = allow_live
        self._data = self._load()
        self._live: HttpEmbedder | None = None
        # Pin model/dim from the cache when warm; otherwise defer to the live backend.
        if self._data.get("model") and self._data.get("dim"):
            super().__init__(model=self._data["model"], dim=int(self._data["dim"]))
        else:
            probe = HttpEmbedder()
            super().__init__(model=probe.model, dim=probe.dim)

    def _load(self) -> dict:
        if self._path.exists():
            try:
                return json.loads(self._path.read_text() or "{}")
            except json.JSONDecodeError:
                pass
        return {"model": None, "dim": None, "vectors": {}}

    def _persist(self) -> None:
        self._data["model"] = self.model
        self._data["dim"] = self.dim
        self._path.write_text(json.dumps(self._data, indent=2, sort_keys=True) + "\n")

    def _live_embedder(self) -> HttpEmbedder:
        if self._live is None:
            self._live = HttpEmbedder(model=self.model, dim=self.dim)
        return self._live

    async def embed_many(self, texts: list[str]) -> list[list[float]]:
        vectors = self._data.setdefault("vectors", {})
        missing = [t for t in texts if _key(t) not in vectors]
        if missing:
            if not self._allow_live:
                raise RuntimeError(
                    f"{len(missing)} text(s) missing from embeddings cache and allow_live=False. "
                    f"Run `make eval-warm-cache` (or seed once with a backend) to populate {self._path.name}."
                )
            fresh = await self._live_embedder().embed_many(missing)
            for text, vec in zip(missing, fresh):
                vectors[_key(text)] = list(vec)
            self._persist()
        return [vectors[_key(t)] for t in texts]
