import threading
from typing import List, Dict

class Reranker:
    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        self.model_name = model_name
        self._model = None
        self._lock = threading.Lock()

    def _get_model(self):
        # Double-checked locking: cheap fast-path once loaded, single load under contention.
        if self._model is None:
            with self._lock:
                if self._model is None:
                    from sentence_transformers import CrossEncoder
                    self._model = CrossEncoder(self.model_name)  # ~100MB, first call only
        return self._model

    def rerank(self, query: str, candidates: List[Dict], top_k: int = 8) -> List[Dict]:
        """
        candidates = list of dicts with at least 'content' and optionally 'score'
        """
        if not candidates:
            return []
        
        # Prepare pairs: (query, document)
        pairs = [(query, cand["content"]) for cand in candidates]
        
        # Get relevance scores (-1 to 1 range usually)
        scores = self._get_model().predict(pairs)
        
        # Attach scores and sort
        for cand, score in zip(candidates, scores):
            cand["rerank_score"] = float(score)
        
        # Sort by new score
        reranked = sorted(candidates, key=lambda x: x["rerank_score"], reverse=True)
        
        return reranked[:top_k]