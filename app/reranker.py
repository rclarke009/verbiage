from sentence_transformers import CrossEncoder
from typing import List, Dict

class Reranker:
    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        self.model = CrossEncoder(model_name)  # Loads ~100MB model
    
    def rerank(self, query: str, candidates: List[Dict], top_k: int = 8) -> List[Dict]:
        """
        candidates = list of dicts with at least 'content' and optionally 'score'
        """
        if not candidates:
            return []
        
        # Prepare pairs: (query, document)
        pairs = [(query, cand["content"]) for cand in candidates]
        
        # Get relevance scores (-1 to 1 range usually)
        scores = self.model.predict(pairs)
        
        # Attach scores and sort
        for cand, score in zip(candidates, scores):
            cand["rerank_score"] = float(score)
        
        # Sort by new score
        reranked = sorted(candidates, key=lambda x: x["rerank_score"], reverse=True)
        
        return reranked[:top_k]