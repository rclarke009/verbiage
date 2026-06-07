"""index_document / reindex_document: chunk, embed, persist (mocked DB)."""

import asyncio
from unittest.mock import MagicMock, patch

from app.indexing import index_document, reindex_document
from app.models import ChunkingOptions, IngestResponse


class FakeEmbedder:
    model = "fake-embed"
    dim = 4

    async def embed_many(self, texts):
        return [[0.1, 0.2, 0.3, 0.4] for _ in texts]


def test_index_document_chunks_embeds_and_updates_metadata():
    conn = MagicMock()
    text = "Paragraph one.\n\nParagraph two with more words here."
    opts = ChunkingOptions(chunk_size=200, chunk_overlap=20)

    with (
        patch("app.indexing.delete_chunks_for_doc") as del_chunks,
        patch("app.indexing.insert_chunk") as ins_chunk,
        patch("app.indexing.insert_embedding") as ins_emb,
        patch("app.indexing.update_document_indexing_metadata") as upd_meta,
    ):
        result = asyncio.run(
            index_document(conn, "doc-1", text, opts, embedder=FakeEmbedder())
        )

    assert isinstance(result, IngestResponse)
    assert result.doc_id == "doc-1"
    assert result.num_chunks >= 1
    assert result.embedding_model == "fake-embed"
    assert result.dim == 4
    assert result.embedding_chars_total > 0
    del_chunks.assert_called()
    assert ins_chunk.call_count == result.num_chunks
    assert ins_emb.call_count == result.num_chunks
    upd_meta.assert_called_once_with(conn, "doc-1", opts.model_dump(), "fake-embed")


def test_index_document_rolls_back_chunks_on_embed_failure():
    conn = MagicMock()
    text = "Short paragraph for embed failure test."
    opts = ChunkingOptions()

    class FailingEmbedder(FakeEmbedder):
        async def embed_many(self, texts):
            raise RuntimeError("embed down")

    with (
        patch("app.indexing.delete_chunks_for_doc") as del_chunks,
        patch("app.indexing.insert_chunk"),
    ):
        try:
            asyncio.run(
                index_document(conn, "doc-1", text, opts, embedder=FailingEmbedder())
            )
            raised = False
        except RuntimeError:
            raised = True

    assert raised
    assert del_chunks.call_count >= 2


def test_reindex_document_delegates_to_index_document():
    from unittest.mock import AsyncMock

    conn = MagicMock()
    text = "Stored full text for reindex."
    expected = IngestResponse(
        doc_id="doc-1",
        num_chunks=1,
        embedding_model="fake-embed",
        dim=4,
        embedding_chars_total=10,
        embedding_tokens_estimate=3,
    )
    mock_index = AsyncMock(return_value=expected)

    with patch("app.indexing.index_document", mock_index):
        result = asyncio.run(reindex_document(conn, "doc-1", text))

    assert result == expected
    mock_index.assert_awaited_once()
    assert mock_index.await_args.args[1] == "doc-1"
    assert mock_index.await_args.args[2] == text
