"""API request/response models (06_backend_schema.md section 10)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class SourceRef(BaseModel):
    """Where a value came from in the *original* uploaded document."""

    page: int
    bbox: list[float] = Field(description="x0, y0, x1, y1 in page coordinates")
    text: str | None = None
    anchor: str | None = None


class CandidateRef(BaseModel):
    value: str
    page: int
    bbox: list[float]
    text: str | None = None
    anchor: str | None = None


class FieldOut(BaseModel):
    name: str
    label: str
    value: str | None
    value_type: str
    required: bool
    system_filled: bool = False
    confidence: float | None = None
    status: Literal["high", "review", "needs_review", "not_found"]
    validation: Literal["valid", "invalid", "not_found", "review"]
    validation_message: str | None = None
    manually_edited: bool = False
    reasons: list[str] = Field(default_factory=list)
    source: SourceRef | None = None
    candidates: list[CandidateRef] = Field(default_factory=list)


class DocumentOut(BaseModel):
    id: str
    filename: str
    file_type: str
    page_count: int
    ocr_used: bool
    preview_url: str


class ClaimOut(BaseModel):
    claim_head: str
    claim_head_label: str
    claim_reference: str
    status: str


class SummaryOut(BaseModel):
    headline: str
    detail: str
    tone: Literal["ready", "review", "issue"]
    total_fields: int
    extracted_fields: int
    high_confidence: int
    needs_review: int
    not_found: int


class ProcessingNotice(BaseModel):
    """Surfaced when the pipeline could not extract anything."""

    code: str
    message: str
    hint: str | None = None


class ResultOut(BaseModel):
    document: DocumentOut
    claim: ClaimOut
    summary: SummaryOut
    fields: list[FieldOut]
    remarks: str | None = None
    currency_note: str | None = None
    notice: ProcessingNotice | None = None


class UploadOut(BaseModel):
    document_id: str
    status: str
    claim_head: str
    claim_reference: str
    page_count: int
    ocr_used: bool


class FieldUpdate(BaseModel):
    name: str
    value: str | None = None


class ResultPatch(BaseModel):
    fields: list[FieldUpdate]
    edited_by: str = "poc-user"


class SaveOut(BaseModel):
    claim_id: str
    claim_reference: str
    status: str
    saved_at: datetime
    claim_head_label: str
    bill_date: str | None = None
    bill_amount_display: str | None = None
    manually_edited_count: int
    json_payload: dict[str, Any]


class ClaimDetailOut(BaseModel):
    claim_id: str
    claim_reference: str
    claim_head: str
    status: str
    saved_at: datetime | None
    json_payload: dict[str, Any]
