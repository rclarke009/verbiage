"""Run the real /ask pipeline for each gold question and capture what the judge needs.

This deliberately reuses the production code paths so a retrieval/chunking/prompt
tweak is reflected in the eval:
    embed (cached) -> _retrieve_for_ask (real auto routing/RRF)
    -> _ask_prompt_from_chunks (exact 8000-char-truncated context)
    -> llm_client.answer_with_context (the generation under test)
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from app import llm_client
from app.main import _ask_prompt_from_chunks, _retrieve_for_ask
from app.models import AskRequest, RetrievedChunk

try:
    from .embedding_cache import CachedEmbedder
except ImportError:  # pragma: no cover - top-level import under pytest
    from embedding_cache import CachedEmbedder

GOLD_PATH = Path(__file__).parent / "gold_questions.yaml"

# Mirror of app.main._ask_prompt_from_chunks so we can recover exactly which chunks
# survived truncation -- the judge must score against the context the model saw.
_MAX_CONTEXT_CHARS = 8000


def load_gold_questions() -> list[dict]:
    data = yaml.safe_load(GOLD_PATH.read_text())
    return data["questions"]


def _included_blocks(top_chunks: list[RetrievedChunk]) -> list[str]:
    """Content of the chunks that fit under the prompt's char budget, in prompt order.

    Each block is prefixed with its document title because the model sees that title
    in the block header (see app.main._ask_prompt_from_chunks) and legitimately uses
    it to ground claims. The title typically carries the property address ("412
    Gulfview Drive"), which the body refers to only as "this residence". Keeping the
    title as the block's first line lets NliJudge's header-prefix premises bridge that
    coreference gap; otherwise an address-bearing claim is unentailed by any premise.
    """
    blocks: list[str] = []
    total = 0
    for c in top_chunks:
        title = (c.document_title or "").strip() or c.doc_id
        link = (c.source_url or "").strip()
        link_line = f"Link: {link}\n" if link else ""
        block = (
            f"[doc_id={c.doc_id} title={title!r} chunk_id={c.chunk_id}]\n"
            f"{link_line}{c.content_snippet}\n"
        )
        if total + len(block) > _MAX_CONTEXT_CHARS:
            break
        blocks.append(f"{title}\n{c.content_snippet}")
        total += len(block)
    return blocks


@dataclass
class QAResult:
    question_id: str
    question: str
    category: str
    must_mention: list[str]
    answer: str
    prompt_context: str  # exact context string fed to the LLM ("" on refusal)
    context_blocks: list[str] = field(default_factory=list)
    refused: bool = False

    @property
    def context_relevant(self) -> bool:
        """Did retrieval surface every must_mention term (case-insensitive)?"""
        if not self.must_mention:
            return True
        blob = " ".join(self.context_blocks).lower()
        return all(term.lower() in blob for term in self.must_mention)


async def run_question(conn, q: dict, embedder: CachedEmbedder | None = None) -> QAResult:
    embedder = embedder or CachedEmbedder()
    question = q["question"]
    vec = (await embedder.embed_many([question]))[0]

    req = AskRequest(question=question)  # retrieval_mode defaults to "auto"
    # reranker=None: the faithfulness gate scores the un-reranked pipeline (pool_k == top_k,
    # exactly the current retrieval) so the eval stays reproducible and never loads the
    # ~100MB cross-encoder. Pass a Reranker() here instead to measure rerank impact.
    top_chunks = await _retrieve_for_ask(conn, req, vec, embedder.model, "eval", None)

    prompt = _ask_prompt_from_chunks(question, top_chunks)
    if prompt is None:
        return QAResult(
            question_id=q["id"],
            question=question,
            category=q["category"],
            must_mention=q.get("must_mention", []),
            answer="I don't have relevant context to answer that question.",
            prompt_context="",
            context_blocks=[],
            refused=True,
        )

    # temperature=0: the faithfulness gate must score a reproducible generation, not a
    # different sample each run (default sampling makes the gate flaky on phrasing).
    answer = await llm_client.answer_with_context(prompt, temperature=0.0)
    # Recover the context that actually reached the model for faithful judging.
    blocks = _included_blocks(top_chunks)
    # The portion of the prompt after "Context:" up to the question is the context.
    context_str = prompt.split("Context:\n", 1)[-1].rsplit("\n\nQuestion:", 1)[0]
    from judges import is_refusal

    return QAResult(
        question_id=q["id"],
        question=question,
        category=q["category"],
        must_mention=q.get("must_mention", []),
        answer=answer,
        prompt_context=context_str,
        context_blocks=blocks,
        refused=is_refusal(answer),
    )


def run_question_sync(conn, q: dict, embedder: CachedEmbedder | None = None) -> QAResult:
    return asyncio.run(run_question(conn, q, embedder))
