"""Faithfulness judging: is each claim in the answer supported by the context?

Two interchangeable judges share one verdict shape:

  - NliJudge  : local sentence-transformers cross-encoder (NLI). Free, deterministic,
                no network. The every-tweak gate. A claim is supported if its max
                entailment probability over the candidate premises (whole block,
                each sentence, and each header-prefixed sentence) clears a threshold.
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

# Canonical literal the /ask path emits when there is no usable context
# (app/main.py do_ask / event_iter). Kept as the product marker; detection below
# also recognises the broader family of model-worded refusals.
REFUSAL_MARKER = "I don't have relevant context"

# Conservative refusal wordings. The model often declines in its own words ("the
# context does not contain any information about ...") rather than emitting the
# canary, which a literal-only check would miss. These patterns target explicit
# "the context can't support this" phrasings and avoid firing on grounded answers.
_REFUSAL_PATTERNS = (
    r"i do(?:es)?n'?t have relevant context",
    r"context (?:provided )?does not contain",
    r"provided does not contain",
    r"do(?:es)?(?:n'?t| not) contain (?:any |enough |relevant )*information",
    r"do(?:es)?(?:n'?t| not) provide (?:any |enough |relevant )*information",
    r"do(?:es)?(?:n'?t| not) mention",
    r"no information (?:about|on|regarding|related to)",
    r"there is no (?:relevant )?information",
    r"no source documents contain",
)
_REFUSAL_RE = re.compile("|".join(_REFUSAL_PATTERNS))


def _normalize_for_refusal(answer: str) -> str:
    """Lowercase, fold curly apostrophes, and collapse whitespace for matching."""
    text = (answer or "").lower().replace("\u2019", "'")
    return re.sub(r"\s+", " ", text)


def is_refusal(answer: str) -> bool:
    return bool(_REFUSAL_RE.search(_normalize_for_refusal(answer)))


_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences, also breaking on newlines so report headings and
    list items become their own units. Trivially short fragments are dropped."""
    if not text:
        return []
    sentences: list[str] = []
    for line in text.splitlines():
        for part in _SENTENCE_SPLIT.split(line.strip()):
            part = part.strip()
            if len(part) >= 8:
                sentences.append(part)
    return sentences


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
    """Local NLI cross-encoder. Supported = max entailment over candidate premises >= threshold."""

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

    @staticmethod
    def _candidate_premises(context_blocks: list[str]) -> list[str]:
        """Expand each context block into the premises a claim may be entailed by.

        Three candidate shapes per block, scored independently with max-pooling later:
          1. the whole block -- supports claims that synthesise across several
             sentences (e.g. "consistent with a single windstorm event"), which a
             lone sentence cannot entail;
          2. each individual sentence -- recovers a single supporting fact that a
             long, multi-topic block dilutes below threshold;
          3. each sentence prefixed with its block's header line -- bridges the
             coreference gap where the supporting sentence says "this residence"
             but the claim names the property ("412 Gulfview Drive in Naples"); the
             address lives only in the section header, so neither the bare sentence
             nor the truncated full block entails the claim on its own.
        """
        premises: list[str] = []
        seen: set[str] = set()

        def add(text: str) -> None:
            text = text.strip()
            if len(text) >= 8 and text not in seen:
                seen.add(text)
                premises.append(text)

        for block in context_blocks:
            add(block)
            sentences = _split_sentences(block)
            header = sentences[0] if sentences else ""
            for sentence in sentences:
                add(sentence)
                if header and sentence != header:
                    add(f"{header} {sentence}")
        return premises or [""]

    def judge(self, context_blocks: list[str], claims: list[str]) -> list[ClaimVerdict]:
        """Max-pool entailment of each claim over header/sentence/block premises.

        A claim is supported when its best entailment probability over all candidate
        premises (see _candidate_premises) clears the threshold. Max-pooling means the
        candidate set can only ever raise a claim's score, so adding finer-grained
        premises never regresses a claim that the whole block already entailed.
        """
        premises = self._candidate_premises(context_blocks)
        verdicts: list[ClaimVerdict] = []
        for claim in claims:
            ent = self._entailment_probs(premises, claim)
            best_idx = int(ent.argmax())
            best = float(ent[best_idx])
            verdicts.append(
                ClaimVerdict(
                    claim=claim,
                    supported=best >= self.threshold,
                    score=best,
                    evidence=premises[best_idx][:160],
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
