"""ORM models - see 06_backend_schema.md.

documents -< processing_runs
          -< claim_extractions -< extraction_fields -< manual_edits
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    original_filename: Mapped[str] = mapped_column(String(255))
    stored_filename: Mapped[str] = mapped_column(String(255))
    file_type: Mapped[str] = mapped_column(String(16))
    mime_type: Mapped[str] = mapped_column(String(64))
    file_size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    page_count: Mapped[int] = mapped_column(Integer, default=1)
    has_text_layer: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_ocr: Mapped[bool] = mapped_column(Boolean, default=False)
    preview_path: Mapped[str] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    runs: Mapped[list["ProcessingRun"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    extractions: Mapped[list["ClaimExtraction"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class ProcessingRun(Base):
    __tablename__ = "processing_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"))
    claim_head: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), default="queued")
    text_source: Mapped[str | None] = mapped_column(String(16), nullable=True)
    ocr_used: Mapped[bool] = mapped_column(Boolean, default=False)
    structure_model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    document: Mapped[Document] = relationship(back_populates="runs")


class ClaimExtraction(Base):
    __tablename__ = "claim_extractions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"))
    processing_run_id: Mapped[str] = mapped_column(ForeignKey("processing_runs.id"))
    claim_reference: Mapped[str] = mapped_column(String(32), index=True)
    claim_head: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), default="extracted")
    overall_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    document: Mapped[Document] = relationship(back_populates="extractions")
    fields: Mapped[list["ExtractionField"]] = relationship(
        back_populates="extraction",
        cascade="all, delete-orphan",
        order_by="ExtractionField.display_order",
    )


class ExtractionField(Base):
    __tablename__ = "extraction_fields"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    claim_extraction_id: Mapped[str] = mapped_column(ForeignKey("claim_extractions.id"))
    field_name: Mapped[str] = mapped_column(String(64))
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    extracted_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    normalized_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    value_type: Mapped[str] = mapped_column(String(16), default="text")
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence_status: Mapped[str] = mapped_column(String(16), default="not_found")
    validation_status: Mapped[str] = mapped_column(String(16), default="not_found")
    validation_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_bbox: Mapped[list | None] = mapped_column(JSON, nullable=True)
    source_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    anchor_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    candidate_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    candidates: Mapped[list | None] = mapped_column(JSON, nullable=True)
    signals: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    was_manually_edited: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    extraction: Mapped[ClaimExtraction] = relationship(back_populates="fields")
    edits: Mapped[list["ManualEdit"]] = relationship(
        back_populates="field", cascade="all, delete-orphan"
    )


class ManualEdit(Base):
    __tablename__ = "manual_edits"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    extraction_field_id: Mapped[str] = mapped_column(ForeignKey("extraction_fields.id"))
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    edited_by: Mapped[str] = mapped_column(String(128), default="poc-user")
    edited_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    field: Mapped[ExtractionField] = relationship(back_populates="edits")
