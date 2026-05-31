"""Faithfulness judging: is each claim in the answer supported by the context?

Two interchangeable judges share one verdict shape:

  - NliJudge  : local sentence-transformers cross-encoder (NLI). Free, deterministic,
                no network. The every-tweak gate. A claim is supported if its max
                entailment probability across the context blocks clears a threshold.
  - LlmJudge  : OpenAI LLM-as-judge returning per-claim {supported, evidence} JSON.
                More accurate, costs tokens, nondeterministic. The nightly/deep gate.

Both judge the answer's *claims* against the exact context the model saw. Refusals
("I don't have relevant context ...") are detected separately and never counted as
unsupported claims.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

# Must match the literal the /ask path emits when there is no usable context
# (app/main.py do_ask / event_iter).
REFUSAL_MARKER = "I don't have relevant context"


def is_refusal(answer: str) -> bool:
    return REFUSAL_MARKER.lower() in (answer or "").lower()


_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def split_claims(answer: str) -> list[str]:
    """Decompose an answer into atomic claims (sentence-level, v1)."""
    if not answer:
        return []
    parts = [s.strip() for s in _SENTENCE_SPLIT.split(answer.strip()) if s.strip()]
    # Drop trivially short fragments (e.g. a stray "Sure." / bullet markers).
    return [p for p in parts if len(p) >= 8]


@dataclass
class ClaimVerdict:
    claim: str
    supported: bool
    score: float | None = None  # entailment prob (NLI) or 1/0 (LLM); None if n/a
    evidence: str = ""


@dataclass
class FaithfulnessResult:
    question_id: str
    category: str
    answer: str
    refused: bool
    context_relevant: bool  # did retrieval surface the must_mention terms
    verdicts: list[ClaimVerdict] = field(default_factory=list)

    @property
    def n_claims(self) -> int:
        return len(self.verdicts)

    @property
    def n_supported(self) -> int:
        return sum(1 for v in self.verdicts if v.supported)

    @property
    def unsupported(self) -> list[ClaimVerdict]:
        return [v for v in self.verdicts if not v.supported]

    @property
    def faithfulness(self) -> float:
        """Supported / total. A refusal has no claims to verify -> treated as 1.0."""
        if self.refused or self.n_claims == 0:
            return 1.0
        return self.n_supported / self.n_claims


class NliJudge:
    """Local NLI cross-encoder. Supported = max entailment over context blocks >= threshold."""

    # label order for cross-encoder/nli-deberta-v3-base: [contradiction, entailment, neutral]
    _ENTAILMENT_IDX = 1

    def __init__(self, model_name: str = "cross-encoder/nli-deberta-v3-base", threshold: float = 0.5):
        self.model_name = model_name
        self.threshold = threshold
        self._model = None

    def _load(self):
        if self._model is None:
            from sentence_transformers import CrossEncoder

            self._model = CrossEncoder(self.model_name)
        return self._model

    def _entailment_probs(self, premises: list[str], hypothesis: str):
        import numpy as np

        model = self._load()
        logits = model.predict([(p, hypothesis) for p in premises])
        logits = np.asarray(logits, dtype="float64")
        if logits.ndim == 1:  # single pair -> shape (3,)
            logits = logits[None, :]
        exp = np.exp(logits - logits.max(axis=1, keepdims=True))
        probs = exp / exp.sum(axis=1, keepdims=True)
        return probs[:, self._ENTAILMENT_IDX]

    def judge(self, context_blocks: list[str], claims: list[str]) -> list[ClaimVerdict]:
        verdicts: list[ClaimVerdict] = []
        blocks = [b for b in context_blocks if b.strip()] or [""]
        for claim in claims:
            ent = self._entailment_probs(blocks, claim)
            best = float(ent.max())
            best_block = blocks[int(ent.argmax())]
            verdicts.append(
                ClaimVerdict(
                    claim=claim,
                    supported=best >= self.threshold,
                    score=best,
                    evidence=best_block[:160],
                )
            )
        return verdicts


class LlmJudge:
    """OpenAI LLM-as-judge. Returns per-claim supported/evidence verdicts."""

    def __init__(self, model: str | None = None):
        from app.config import LLM_OPENAI_MODEL

        self.model = model or LLM_OPENAI_MODEL

    def _prompt(self, context: str, claims: list[str]) -> str:
        numbered = "\n".join(f"{i + 1}. {c}" for i, c in enumerate(claims))
        return (
            "You are a strict grounding judge. Decide whether each CLAIM is directly "
            "supported by the CONTEXT. A claim is supported ONLY if the context states "
            "it; do not use outside knowledge or inference beyond what the text says.\n\n"
            f"CONTEXT:\n{context}\n\n"
            f"CLAIMS:\n{numbered}\n\n"
            'Respond with JSON only: {"verdicts": [{"index": <1-based>, '
            '"supported": <true|false>, "evidence": "<quoted span or empty>"}]}'
        )

    async def judge(self, context: str, claims: list[str]) -> list[ClaimVerdict]:
        if not claims:
            return []
        import httpx

        from app.config import OPENAI_API_KEY
        from app.llm_client import OPENAI_CHAT_URL

        if not OPENAI_API_KEY:
            raise RuntimeError("LlmJudge requires OPENAI_API_KEY")

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": self._prompt(context, claims)}],
            "stream": False,
            "response_format": {"type": "json_object"},
        }
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                OPENAI_CHAT_URL,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {OPENAI_API_KEY}",
                },
                json=payload,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]

        data = json.loads(content)
        by_index = {int(v["index"]): v for v in data.get("verdicts", [])}
        verdicts: list[ClaimVerdict] = []
        for i, claim in enumerate(claims, start=1):
            v = by_index.get(i, {})
            verdicts.append(
                ClaimVerdict(
                    claim=claim,
                    supported=bool(v.get("supported", False)),
                    score=1.0 if v.get("supported") else 0.0,
                    evidence=str(v.get("evidence", ""))[:160],
                )
            )
        return verdicts
