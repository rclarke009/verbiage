"""Faithfulness eval: every claim in an answer must be supported by the retrieved context.

Run after every tweak (fast, local NLI judge):
    docker compose -f docker-compose.eval.yml up -d --wait
    VERBIAGE_EVAL=1 EVAL_DATABASE_URL=postgresql://postgres:postgres@localhost:5433/verbiage_eval \
      pytest -m eval_fast tests/eval -s
    docker compose -f docker-compose.eval.yml down -v
  (or simply: `make eval`)

Deeper run (OpenAI LLM judge):
    VERBIAGE_EVAL=1 ... pytest -m eval_full tests/eval -s   (or `make eval-full`)

Generation always needs an LLM backend (OPENAI_API_KEY or a running Ollama) and an
embedding backend (or a warm embeddings_cache.json).
"""

from __future__ import annotations

import asyncio

import pytest

from embedding_cache import CachedEmbedder
from judges import FaithfulnessResult, LlmJudge, NliJudge, split_claims
from runner import load_gold_questions, run_question_sync

GOLD = load_gold_questions()
IDS = [q["id"] for q in GOLD]

# The bar for the every-tweak gate. 1.0 = no unsupported claims allowed. Lower this
# (e.g. 0.8) if sentence-level NLI proves too strict on legitimately-grounded paraphrase.
FAST_MIN_FAITHFULNESS = 1.0

# (question_id, judge, status, faithfulness, n_unsupported, context_relevant)
_SCORE_ROWS: list[tuple] = []


@pytest.fixture(scope="session")
def qa_results(eval_conn):
    """Run the full /ask pipeline once per gold question; shared across judges."""
    embedder = CachedEmbedder()
    return {q["id"]: run_question_sync(eval_conn, q, embedder) for q in GOLD}


@pytest.fixture(scope="session")
def nli_judge():
    return NliJudge()


@pytest.fixture(scope="session", autouse=True)
def _scoreboard():
    yield
    if not _SCORE_ROWS:
        return
    print("\n\nMYDEBUG -> faithfulness scoreboard")
    print(f"{'question_id':28} {'judge':5} {'status':8} {'faith':6} {'unsup':5} {'ctx_ok':6}")
    for qid, judge, status, faith, n_unsup, ctx_ok in _SCORE_ROWS:
        print(f"{qid:28} {judge:5} {status:8} {faith:6.2f} {n_unsup:<5} {str(ctx_ok):6}")


def _record(res, judge_name: str, verdicts) -> FaithfulnessResult:
    fr = FaithfulnessResult(
        question_id=res.question_id,
        category=res.category,
        answer=res.answer,
        refused=res.refused,
        context_relevant=res.context_relevant,
        verdicts=verdicts,
    )
    status = "refused" if fr.refused else ("ok" if fr.faithfulness >= FAST_MIN_FAITHFULNESS else "FAIL")
    _SCORE_ROWS.append(
        (res.question_id, judge_name, status, fr.faithfulness, len(fr.unsupported), res.context_relevant)
    )
    return fr


@pytest.mark.eval_fast
@pytest.mark.parametrize("q", GOLD, ids=IDS)
def test_faithfulness_fast(q, qa_results, nli_judge):
    res = qa_results[q["id"]]

    if q["category"] == "unanswerable":
        _SCORE_ROWS.append((q["id"], "nli", "refused" if res.refused else "FAIL", 1.0 if res.refused else 0.0, 0, True))
        assert res.refused, (
            f"{q['id']}: corpus has no relevant context, expected a refusal but got: {res.answer!r}"
        )
        return

    claims = split_claims(res.answer)
    premises = res.context_blocks + ([res.prompt_context] if res.prompt_context else [])
    verdicts = nli_judge.judge(premises, claims)
    fr = _record(res, "nli", verdicts)

    assert res.context_relevant, (
        f"{q['id']}: retrieval did not surface expected terms {q.get('must_mention')} "
        f"-- this is a RETRIEVER miss, not a generator faithfulness failure"
    )
    assert fr.faithfulness >= FAST_MIN_FAITHFULNESS, (
        f"{q['id']}: faithfulness {fr.faithfulness:.2f} < {FAST_MIN_FAITHFULNESS}; unsupported claims:\n"
        + "\n".join(f"  - (ent={v.score:.2f}) {v.claim}" for v in fr.unsupported)
    )


@pytest.mark.eval_full
@pytest.mark.parametrize("q", GOLD, ids=IDS)
def test_faithfulness_full(q, qa_results):
    res = qa_results[q["id"]]

    if q["category"] == "unanswerable":
        _SCORE_ROWS.append((q["id"], "llm", "refused" if res.refused else "FAIL", 1.0 if res.refused else 0.0, 0, True))
        assert res.refused, (
            f"{q['id']}: corpus has no relevant context, expected a refusal but got: {res.answer!r}"
        )
        return

    claims = split_claims(res.answer)
    judge = LlmJudge()
    verdicts = asyncio.run(judge.judge(res.prompt_context, claims))
    fr = _record(res, "llm", verdicts)

    assert not fr.unsupported, (
        f"{q['id']}: LLM judge flagged unsupported claims:\n"
        + "\n".join(f"  - {v.claim}" for v in fr.unsupported)
    )
