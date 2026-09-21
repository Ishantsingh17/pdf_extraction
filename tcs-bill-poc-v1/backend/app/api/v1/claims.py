"""Saved claim retrieval."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import ClaimExtraction, ExtractionField
from app.schemas.schemas import ClaimDetailOut
from app.services import result_service

router = APIRouter(prefix="/claims", tags=["claims"])


@router.get("/{claim_id}", response_model=ClaimDetailOut)
def get_claim(claim_id: str, db: Session = Depends(get_db)) -> ClaimDetailOut:
    extraction = db.get(ClaimExtraction, claim_id)
    if extraction is None:
        extraction = db.scalar(
            select(ClaimExtraction).where(ClaimExtraction.claim_reference == claim_id)
        )
    if extraction is None:
        raise HTTPException(
            status_code=404, detail={"code": "not_found", "message": "Claim not found."}
        )

    fields = list(
        db.scalars(
            select(ExtractionField)
            .where(ExtractionField.claim_extraction_id == extraction.id)
            .order_by(ExtractionField.display_order)
        )
    )
    return ClaimDetailOut(
        claim_id=extraction.id,
        claim_reference=extraction.claim_reference,
        claim_head=extraction.claim_head,
        status=extraction.status,
        saved_at=extraction.updated_at,
        json_payload=result_service.build_claim_json(extraction, fields),
    )
