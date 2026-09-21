"""Heuristic confidence scoring - POC V1 (Phase 8 / TRD section 11).

No LLM and no ML model. The score is a transparent weighted sum of signals we
can actually observe, and every signal is reported back so the UI can explain
the number in plain language ("Clear field label found", "Value format is
valid", ...). The weights are configuration, not magic - POC V2 replaces this
with a model trained on the evidence V1 collects.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.core.config import settings
from app.rules.common import FieldSpec
from app.services.extraction_service import ExtractionResult, FieldExtraction
from app.services.validation_service import (
    INVALID,
    NOT_FOUND,
    REVIEW,
    VALID,
    ValidationResult,
)

# Status vocabulary shown to users.
HIGH = "high"
NEEDS_REVIEW = "needs_review"

#: Signal -> weight. Must sum to 1.0.
WEIGHTS: dict[str, float] = {
    "candidate_found": 0.20,
    "anchor_match": 0.22,
    "format_valid": 0.18,
    "spatial_proximity": 0.15,
    "unique_candidate": 0.15,
    "source_quality": 0.10,
}

#: User-facing wording for each signal, used by the "Why NN%?" popover.
SIGNAL_LABELS: dict[str, str] = {
    "anchor_match": "Clear field label found",
    "format_valid": "Value format is valid",
    "spatial_proximity": "Value is close to the label",
    "unique_candidate": "Only one strong candidate found",
    "source_quality": "Read directly from the document text",
}


@dataclass
class FieldConfidence:
    field_name: str
    confidence: float | None
    status: str
    signals: dict[str, float] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)


@dataclass
class ConfidenceResult:
    fields: dict[str, FieldConfidence] = field(default_factory=dict)
    overall: float | None = None


class ConfidenceService:
    def score(
        self, extraction_result: ExtractionResult, validation_result: ValidationResult
    ) -> ConfidenceResult:
        result = ConfidenceResult()
        scored: list[float] = []

        for name, extraction in extraction_result.fields.items():
            entry = self._score_field(name, extraction, validation_result)
            result.fields[name] = entry
            if entry.confidence is not None:
                scored.append(entry.confidence)

        result.overall = round(sum(scored) / len(scored), 4) if scored else None
        return result

    def _score_field(
        self, name: str, extraction: FieldExtraction, validation: ValidationResult
    ) -> FieldConfidence:
        spec: FieldSpec = extraction.spec
        validation_status = validation.status_for(name)

        # System-filled values (remarks) are certain by construction.
        if spec.system_value is not None:
            return FieldConfidence(
                name, 1.0, HIGH, {"system_filled": 1.0}, ["Filled automatically from the claim head"]
            )

        best = extraction.best
        if best is None or validation_status == NOT_FOUND:
            return FieldConfidence(name, None, NOT_FOUND, {}, [])

        raw = best.signals

        # A field is "located" either by its printed label or by the document's
        # own structure - a merchant name set in the largest type in the header
        # is evidence of the same order as a label, and is scored as such.
        label_evidence = float(raw.get("anchor_weight", 0.0)) if raw.get("anchor_match") else 0.0
        structural_evidence = (
            float(raw.get("prominence", 0.0)) * 0.95
            if best.strategy in ("structure_header", "name_token")
            else 0.0
        )

        signals: dict[str, float] = {
            "candidate_found": 1.0,
            "anchor_match": max(label_evidence, structural_evidence),
            "format_valid": 1.0 if raw.get("format_valid") else 0.0,
            "spatial_proximity": float(raw.get("spatial_proximity", 0.0)),
            "unique_candidate": 0.0 if extraction.is_ambiguous else 1.0,
            "source_quality": float(raw.get("source_quality", 0.0)),
        }

        confidence = sum(WEIGHTS[key] * value for key, value in signals.items())

        # Validation outcome caps the score - a value that failed its checks can
        # never read as high confidence.
        if validation_status == INVALID:
            confidence = min(confidence, 0.45)
        elif validation_status == REVIEW:
            confidence = min(confidence, 0.85)

        confidence = round(max(0.0, min(confidence, 1.0)), 4)
        status = self._status_for(confidence)

        return FieldConfidence(
            field_name=name,
            confidence=confidence,
            status=status,
            signals={k: round(v, 3) for k, v in signals.items()},
            reasons=self._reasons(signals, structural_evidence > label_evidence),
        )

    @staticmethod
    def _status_for(confidence: float) -> str:
        if confidence >= settings.confidence_high:
            return HIGH
        if confidence >= settings.confidence_review:
            return REVIEW
        return NEEDS_REVIEW

    @staticmethod
    def _reasons(signals: dict[str, float], from_structure: bool = False) -> list[str]:
        """Plain-language evidence - never the weights themselves."""
        reasons: list[str] = []
        for key, label in SIGNAL_LABELS.items():
            if signals.get(key, 0.0) < 0.6:
                continue
            if key == "anchor_match" and from_structure:
                label = "Found in the bill header"
            reasons.append(label)
        return reasons


confidence_service = ConfidenceService()
