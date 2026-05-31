"""
Pydantic request/response models for ingest, ask, and document listing.
"""

import uuid
from pydantic import BaseModel, Field, model_validator
from typing import Literal

class ChunkingOptions(BaseModel):
    strategy: Literal["paragraph", "chars", "sentences"] = "paragraph"
    chunk_size: int = Field(default=1200, description="Chunk size")
    chunk_overlap: int = Field(default=150, description="Chunk overlap")

    @model_validator(mode="after")
    def check_chunking_bounds(self)->"ChunkingOptions":
        if self.chunk_size <= 0:
            raise ValueError("chunk_size must be greater than 0")
        if self.chunk_overlap < 0:
            raise ValueError("chunk_overlap must be greater than or equal to 0")
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be less than chunk_size")
        return self

class IngestRequest (BaseModel):
    text: str = Field(..., min_length=1,description="Text to ingest")
    doc_id: str | None = None
    title: str | None = None
    source: str | None = None
    source_url: str | None = Field(default=None, description="Optional URL to the full report")
    source_filename: str | None = Field(default=None, description="Original filename if known")
    chunking_options: ChunkingOptions | None = None

    @model_validator(mode="after")
    def set_defaults(self) -> "IngestRequest":
        doc_id = self.doc_id if self.doc_id is not None else str(uuid.uuid4())
        chunking_options = self.chunking_options if self.chunking_options is not None else ChunkingOptions()
        return self.model_copy(update={"doc_id":doc_id, "chunking_options":chunking_options})

class IngestResponse(BaseModel):
    doc_id: str = Field(..., description="doc_id")
    num_chunks: int = Field(..., description="Number of chunks")
    embedding_model: str = Field(..., description="Embedding model")
    dim: int = Field(..., description="Embedding vector dimension")
    embedding_chars_total: int = Field(
        ...,
        description=(
            "Sum of chunk character lengths passed to embedding (overlap counted); "
            "compare volume to OpenAI embedding usage deltas per ingest."
        ),
    )
    embedding_tokens_estimate: int = Field(
        ...,
        description=(
            "Heuristic ingest embedding tokens: sum ceil(len(chunk)/4) per chunk; "
            "approximate checklist vs usage dashboard (~4 chars/token English)."
        ),
    )


class AskRequest(BaseModel):
    question: str = Field(..., description="Question from user")
    top_k: int = Field(default=5, description="Will pull the top __ matches")
    doc_id: str | None = Field(default=None, description="If set, restrict search to this document")
    use_rag: bool = True
    retrieval_mode: Literal["vector", "lexical", "hybrid", "auto"] = Field(
        default="hybrid",
        description=(
            "vector = pgvector cosine; lexical = full-text ts_rank; hybrid = RRF fusion of both; "
            "auto = adaptive routing per query (lexical for short exact-term lookups, hybrid otherwise)"
        ),
    )

class RetrievedChunk(BaseModel):
    chunk_id: str = Field(..., description="chunk_id")
    doc_id: str = Field(..., description="doc_id")
    score: float = Field(..., description="score")
    content_snippet: str = Field(..., description="content_snippet")
    document_title: str | None = Field(default=None, description="Ingested document title")
    source: str | None = Field(default=None, description="Ingested source label")
    source_url: str | None = Field(
        default=None,
        description="Resolved URL to open the full report (stored or derived for Google Drive)",
    )
    section_label: str | None = Field(default=None, description="Detected report section heading")

class AskResponse(BaseModel):
    answer: str = Field(...,description="Answer from system")
    top_chunks: list[RetrievedChunk] = Field(..., description="top _ chunks")
    prompt_tokens_estimate: int | None = Field(default=None, description="Prompt tokens estimate (optional)")


class DocumentSummary(BaseModel):
    doc_id: str = Field(..., description="Document id")
    title: str | None = Field(default=None, description="Title")
    source: str | None = Field(default=None, description="Source")
    source_url: str | None = Field(
        default=None,
        description="Resolved URL to open the full report, if any",
    )
    source_filename: str | None = Field(default=None, description="Original upload or Drive filename")
    embedding_model: str | None = Field(default=None, description="Embedding model used for this document")
    chunking_config: dict | None = Field(default=None, description="Chunking options used at last index")
    created_at: int = Field(..., description="Unix timestamp (ingest time)")
    source_modified_at: int | None = Field(
        default=None,
        description="Unix seconds when source file was last modified, if known",
    )
    num_chunks: int = Field(..., description="Number of chunks")
    snippet: str | None = Field(default=None, description="First ~250 chars of first chunk")


class ReindexRequest(BaseModel):
    chunking_options: ChunkingOptions | None = None


class DocumentsListResponse(BaseModel):
    documents: list[DocumentSummary] = Field(..., description="List of ingested documents")


class IngestGoogleDriveRequest(BaseModel):
    """Request to ingest documents from Google Drive (read-only)."""

    folder_id: str | None = Field(default=None, description="Limit to files in this folder")
    file_ids: list[str] | None = Field(default=None, description="If set, only these file IDs (folder_id ignored)")
    collapse_versions: bool = Field(
        default=True,
        description="When listing a folder, ingest only the newest version per report name (e.g. v10 over v9). Ignored when file_ids is set.",
    )


class IngestGoogleDriveResponse(BaseModel):
    """Result of Google Drive sync."""

    ingested: int = Field(..., description="Number of documents ingested")
    skipped: int = Field(default=0, description="Number skipped (e.g. duplicate doc_id)")
    errors: list[str] = Field(default_factory=list, description="Error messages for failed docs")
    doc_ids: list[str] = Field(default_factory=list, description="doc_ids that were ingested")


class DriveFileMeta(BaseModel):
    """Metadata for an ingestable Drive file (list only, no content)."""

    id: str = Field(..., description="Drive file id")
    name: str | None = Field(default=None, description="File name")
    mimeType: str | None = Field(default=None, description="MIME type")
    modifiedTime: str | None = Field(default=None, description="Last modified (RFC3339)")
    index_status: Literal["not_indexed", "indexed", "stale"] = Field(
        default="not_indexed",
        description="Whether this Drive file is in the document index",
    )
    num_chunks: int | None = Field(default=None, description="Chunk count when indexed or stale")


class DriveFileListSummary(BaseModel):
    """Counts by index status for a Drive file listing."""

    total: int = Field(..., description="Total ingestable Drive files in listing")
    indexed: int = Field(..., description="Already indexed and up to date")
    not_indexed: int = Field(..., description="Not yet in the index")
    stale: int = Field(..., description="Indexed but Drive doc changed since last ingest")


class DriveFolderContext(BaseModel):
    """Resolved folder location for Drive list/ingest UI."""

    id: str = Field(..., description="Drive folder id")
    name: str | None = Field(default=None, description="Folder name from Drive")
    path: str | None = Field(default=None, description="Parent breadcrumb from Drive API")
    is_default: bool = Field(default=False, description="True when folder is the team inbox default")
    display_path: str = Field(..., description="Human-readable path for UI")


class DriveFileListResponse(BaseModel):
    """Response from listing Drive files (metadata only)."""

    files: list[DriveFileMeta] = Field(..., description="List of ingestable Drive file metadata")
    summary: DriveFileListSummary = Field(..., description="Index status counts")
    folder: DriveFolderContext | None = Field(
        default=None,
        description="Folder context when listing by folder_id",
    )


class SimilarTitleMatch(BaseModel):
    doc_id: str
    title: str | None = None
    score: float = Field(..., description="Similarity ratio 0..1")


class SimilarTitlesResponse(BaseModel):
    matches: list[SimilarTitleMatch] = Field(default_factory=list)


class SignupRequest(BaseModel):
    email: str = Field(..., min_length=3)
    password: str = Field(..., min_length=6)
    invite_code: str | None = None


class SignupResponse(BaseModel):
    ok: bool = True
