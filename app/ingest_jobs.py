"""Pydantic models for async ingest batches and jobs."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

IngestBatchStatus = Literal["pending", "running", "completed", "failed"]


class IngestBatchEnqueueResponse(BaseModel):
    batch_id: str = Field(..., description="Batch UUID for polling status")
    total: int = Field(..., description="Number of jobs enqueued")
    job_ids: list[str] = Field(default_factory=list, description="Job UUIDs in enqueue order")


class IngestBatchStatusResponse(BaseModel):
    batch_id: str
    kind: str
    status: IngestBatchStatus
    total: int
    pending: int
    running: int
    succeeded: int
    failed: int
    skipped: int
    errors: list[str] = Field(default_factory=list, description="Recent failed job messages")
    created_at: datetime | None = None
    updated_at: datetime | None = None
