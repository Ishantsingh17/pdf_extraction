"""Claim-head targeted extraction engine (Phase 6).

Only the fields required by the selected claim head are extracted; everything
else in the document is ignored (PRD section 2).

For each field the engine walks a ladder of strategies:

  1. anchor on the same line as the value      ("Total: AED 1,069.50")
  2. anchor with the value to its right        (two-column layouts)
  3. anchor with the value directly below      (stacked labels)
  4. structure-driven fallback                 (header block, summary region)

Every candidate carries the evidence that produced it - anchor, source text,
page and bbox - so the UI can highlight the region on the original document
and the confidence engine can score observable signals rather than guesses.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from app.core.logging import get_logger
from app.rules.common import (
    ClaimHeadSchema,
    FieldSpec,
    contains_anchor,
    detect_currency,
    extract_identifier,
    format_date,
    format_money,
    looks_like_merchant,
    looks_like_place,
    normalize_text,
    parse_date,
    parse_money,
    strip_label,
)
from app.services.document_model import Block, Page, StructuredDocument

logger = get_logger(__name__)

#: Vertical tolerance (as a multiple of line height) for "same row".
_ROW_TOLERANCE = 0.75
#: How far below an anchor we still accept a stacked value.
_BELOW_TOLERANCE = 2.6
#: Fraction of page height treated as the masthead when looking for a merchant.
_HEADER_BAND = 0.25
#: How many name-shaped lines from that band are offered as candidates.
_HEADER_CANDIDATES = 3


@dataclass
class Candidate:
    """One possible value for a field, with the evidence behind it."""

    value: str
    normalized_value: str
    page_number: int
    bbox: tuple[float, float, float, float]
    source_text: str
    anchor_text: str | None = None
    strategy: str = "anchor_inline"
    signals: dict[str, Any] = field(default_factory=dict)
    score: float = 0.0

    def as_evidence(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "page": self.page_number,
            "bbox": list(self.bbox),
            "text": self.source_text,
            "anchor": self.anchor_text,
        }


@dataclass
class FieldExtraction:
    spec: FieldSpec
    candidates: list[Candidate] = field(default_factory=list)

    @property
    def best(self) -> Candidate | None:
        return self.candidates[0] if self.candidates else None

    @property
    def is_ambiguous(self) -> bool:
        """Two strong candidates that disagree - never silently auto-picked."""
        if len(self.candidates) < 2:
            return False
        first, second = self.candidates[0], self.candidates[1]
        if first.normalized_value == second.normalized_value:
            return False
        margin = first.score - second.score
        if self.spec.value_type == "money":
            # A value that is both the largest amount on the bill and sits in
            # the totals region is not in genuine conflict with a line item
            # that merely happened to sit near a weak anchor.
            decisive = first.signals.get("is_largest_amount") and not second.signals.get(
                "is_largest_amount"
            )
            if decisive:
                return margin < 0.05
        return margin < 0.12


@dataclass
class ExtractionResult:
    claim_head: ClaimHeadSchema
    fields: dict[str, FieldExtraction] = field(default_factory=dict)
    structure_model: str = ""


class ClaimExtractor:
    """Extracts the fields of one claim head from a structured document."""

    def extract(
        self, structured_document: StructuredDocument, claim_head: ClaimHeadSchema
    ) -> ExtractionResult:
        result = ExtractionResult(
            claim_head=claim_head, structure_model=structured_document.model
        )

        for spec in claim_head.fields:
            if spec.system_value is not None:
                # Auto-filled by the system (remarks) - no document evidence.
                result.fields[spec.name] = FieldExtraction(spec=spec, candidates=[])
                continue
            try:
                candidates = self._candidates_for(structured_document, spec, result)
            except Exception:  # one bad field must not sink the run (NFR)
                logger.exception("extraction failed for field=%s", spec.name)
                candidates = []
            candidates.sort(key=lambda c: c.score, reverse=True)
            result.fields[spec.name] = FieldExtraction(
                spec=spec, candidates=_dedupe(candidates)[:5]
            )

        return result

    # -- strategy dispatch --------------------------------------------------

    def _candidates_for(
        self, doc: StructuredDocument, spec: FieldSpec, result: ExtractionResult
    ) -> list[Candidate]:
        if spec.value_type == "currency":
            return self._currency_candidates(doc, spec, result)
        if spec.name == "hotel_name":
            return self._merchant_candidates(doc, spec)

        candidates: list[Candidate] = []
        for page in doc.pages:
            for block in page.blocks:
                if not _is_label_context(block.text):
                    continue
                for anchor_index, anchor in enumerate(spec.anchors):
                    if not contains_anchor(block.text, anchor):
                        continue
                    if self._is_negative(block.text, spec, anchor):
                        continue
                    anchor_weight = self._anchor_weight(anchor_index, len(spec.anchors))
                    candidates.extend(
                        self._from_anchor_block(page, block, spec, anchor, anchor_weight)
                    )

        # Ride receipts print the route as a timestamped itinerary with no
        # "From"/"To" labels at all.
        if not candidates and spec.name in ("from_location", "to_location"):
            candidates.extend(self._itinerary_candidates(doc, spec))

        if not candidates and spec.value_type in ("date", "money"):
            candidates.extend(self._unanchored_candidates(doc, spec))

        if spec.value_type == "money":
            self._apply_largest_amount_signal(candidates)
        return candidates

    @staticmethod
    def _apply_largest_amount_signal(candidates: list[Candidate]) -> None:
        """The payable total is the largest amount printed on a bill.

        Component fees, taxes and subtotals are all smaller by construction, so
        this separates a genuine total from a line item that happened to sit
        next to a weak anchor like "Amount".
        """
        if not candidates:
            return
        amounts = [Decimal(c.normalized_value) for c in candidates]
        largest = max(amounts)
        for candidate, amount in zip(candidates, amounts):
            is_largest = amount == largest
            candidate.signals["is_largest_amount"] = is_largest
            if is_largest:
                candidate.score = round(candidate.score + 0.10, 4)

    # -- strategies ---------------------------------------------------------

    def _from_anchor_block(
        self,
        page: Page,
        block: Block,
        spec: FieldSpec,
        anchor: str,
        anchor_weight: float,
    ) -> list[Candidate]:
        found: list[Candidate] = []

        # 1. value on the same line as the label
        inline = strip_label(block.text, anchor)
        candidate = self._build(
            raw=inline,
            spec=spec,
            page=page,
            block=block,
            anchor=anchor,
            strategy="anchor_inline",
            anchor_weight=anchor_weight,
            proximity=1.0,
        )
        if candidate:
            found.append(candidate)

        # 2. value in the next column, same row
        for neighbour in _blocks_right_of(page, block):
            candidate = self._build(
                raw=neighbour.text,
                spec=spec,
                page=page,
                block=neighbour,
                anchor=anchor,
                strategy="anchor_right",
                anchor_weight=anchor_weight,
                proximity=_proximity(block, neighbour, page),
            )
            if candidate:
                found.append(candidate)
                break

        # 3. value stacked underneath the label
        if not found:
            for neighbour in _blocks_below(page, block):
                candidate = self._build(
                    raw=neighbour.text,
                    spec=spec,
                    page=page,
                    block=neighbour,
                    anchor=anchor,
                    strategy="anchor_below",
                    anchor_weight=anchor_weight,
                    proximity=_proximity(block, neighbour, page) * 0.9,
                )
                if candidate:
                    found.append(candidate)
                    break

        return found

    def _itinerary_candidates(
        self, doc: StructuredDocument, spec: FieldSpec
    ) -> list[Candidate]:
        """Route from a timestamped itinerary (pickup first, drop second).

        Ride receipts print the trip as `7:59 am` followed by the pickup
        address, then `8:59 am` followed by the drop address, with no labels.
        The first stop is the origin and the last is the destination.
        """
        stops: list[tuple[Page, Block, str]] = []

        for page in doc.pages:
            blocks = sorted(page.blocks, key=lambda b: (b.y0, b.x0))
            for index, block in enumerate(blocks):
                if not _TIME_RE.match(block.text):
                    continue
                # Address lines sit under the time, in the same column.
                lines: list[Block] = []
                for following in blocks[index + 1 :]:
                    if _TIME_RE.match(following.text):
                        break
                    if abs(following.x0 - block.x0) > 12:
                        break
                    if following.y0 - (lines[-1] if lines else block).y1 > 12:
                        break
                    lines.append(following)
                    if len(lines) >= 5:
                        break
                address = normalize_text(" ".join(line.text for line in lines))
                # An address has structure: a comma or a postcode, not just words.
                if len(address) < 12 or ("," not in address and not re.search(r"\d{5,6}", address)):
                    continue
                stops.append((page, lines[0], address))

        if len(stops) < 2:
            return []

        page, block, address = stops[0] if spec.name == "from_location" else stops[-1]
        candidate = Candidate(
            value=address,
            normalized_value=address,
            page_number=page.page_number,
            bbox=block.bbox,
            source_text=address,
            anchor_text=None,
            strategy="itinerary",
            signals={
                "candidate_found": True,
                "anchor_match": False,
                "anchor_weight": 0.0,
                "format_valid": True,
                # Position in the itinerary is the evidence, and it is strong:
                # a two-stop trip has exactly one origin and one destination.
                "spatial_proximity": 0.9,
                "source_quality": _source_quality(block),
                "region": block.region_type,
                "itinerary_stops": len(stops),
            },
        )
        candidate.score = _score_candidate(candidate, spec)
        return [candidate]

    def _unanchored_candidates(
        self, doc: StructuredDocument, spec: FieldSpec
    ) -> list[Candidate]:
        """Last resort: a well-formed value with no label nearby."""
        found: list[Candidate] = []
        for page in doc.pages:
            for block in page.blocks:
                candidate = self._build(
                    raw=block.text,
                    spec=spec,
                    page=page,
                    block=block,
                    anchor=None,
                    strategy="unanchored",
                    anchor_weight=0.0,
                    proximity=0.25,
                )
                if candidate:
                    found.append(candidate)
        return found

    def _merchant_candidates(self, doc: StructuredDocument, spec: FieldSpec) -> list[Candidate]:
        """Hotel/restaurant name - anchors first, then document structure.

        Never just "the first organization-like text" (TRD section 9).
        """
        found: list[Candidate] = []
        first_page = doc.pages[0] if doc.pages else None
        max_prominence = (
            max((b.prominence for b in first_page.blocks), default=1.0) if first_page else 1.0
        )

        for page in doc.pages:
            for block in page.blocks:
                for anchor_index, anchor in enumerate(spec.anchors):
                    if not contains_anchor(block.text, anchor):
                        continue
                    weight = self._anchor_weight(anchor_index, len(spec.anchors))
                    # "Bill From: Taj" is a labelled value; "Cafe Nilgiri" and
                    # "Restaurant & Caterers" merely contain the word. Only the
                    # former is anchor evidence - the latter is judged on how
                    # prominently it is set, like any other header line.
                    is_label = _anchor_is_label(block.text, anchor)
                    value = (
                        strip_label(block.text, anchor)
                        if is_label
                        else normalize_text(block.text)
                    )
                    if not looks_like_merchant(value):
                        continue
                    found.append(
                        Candidate(
                            value=value,
                            normalized_value=value,
                            page_number=page.page_number,
                            bbox=block.bbox,
                            source_text=block.text,
                            anchor_text=anchor if is_label else None,
                            strategy="anchor_inline" if is_label else "name_token",
                            signals={
                                "candidate_found": True,
                                "anchor_match": is_label,
                                "anchor_weight": weight if is_label else 0.0,
                                "format_valid": True,
                                "spatial_proximity": 1.0 if is_label else 0.8,
                                "source_quality": _source_quality(block),
                                "region": block.region_type,
                                "prominence": round(block.prominence / max_prominence, 3),
                            },
                        )
                    )

        # Structure fallback: a merchant prints its own name first, and in the
        # largest type on the bill.
        #
        # The layout model labels a header region on letterhead-style bills,
        # but on a till receipt it labels the whole slip as body text (measured:
        # zero header regions on the KFC sample, with "TAKE AWAY" as the only
        # title). So the top band of the page is pooled with whatever the model
        # did label, and the metadata lines that share that band - the address,
        # the GSTIN, "DATE:", "BILL:" - are filtered out by shape.
        if first_page:
            band = first_page.height * _HEADER_BAND
            pool = sorted(
                (
                    b
                    for b in first_page.blocks
                    if b.region_type in ("header", "title") or b.y0 <= band
                ),
                key=lambda b: b.y0,
            )
            rank = 0
            for block in pool:
                if rank >= _HEADER_CANDIDATES:
                    break
                value = normalize_text(block.text)
                if not looks_like_merchant(value) or _is_bill_metadata(value):
                    continue
                found.append(
                    Candidate(
                        value=value,
                        normalized_value=value,
                        page_number=first_page.page_number,
                        bbox=block.bbox,
                        source_text=block.text,
                        anchor_text=None,
                        strategy="structure_header",
                        signals={
                            "candidate_found": True,
                            "anchor_match": False,
                            "anchor_weight": 0.0,
                            "format_valid": True,
                            "spatial_proximity": 0.6,
                            "source_quality": _source_quality(block),
                            "region": block.region_type,
                            "prominence": round(block.prominence / max_prominence, 3),
                            # Reading order: the first name-shaped line at the
                            # top of a bill is overwhelmingly the merchant's.
                            "header_rank": round(1.0 - rank * 0.35, 3),
                        },
                    )
                )
                rank += 1

        for candidate in found:
            candidate.score = _score_candidate(candidate, spec)
        return found

    def _currency_candidates(
        self, doc: StructuredDocument, spec: FieldSpec, result: ExtractionResult
    ) -> list[Candidate]:
        """Currency is read from the bill, exactly as printed (FR-07)."""
        found: list[Candidate] = []

        # Strongest evidence: the currency printed next to the bill amount.
        amount_field = result.fields.get("bill_amount")
        amount_best = amount_field.best if amount_field else None
        if amount_best:
            code = detect_currency(amount_best.source_text)
            if code:
                found.append(
                    Candidate(
                        value=code,
                        normalized_value=code,
                        page_number=amount_best.page_number,
                        bbox=amount_best.bbox,
                        source_text=amount_best.source_text,
                        anchor_text=amount_best.anchor_text,
                        strategy="from_amount",
                        signals={
                            "candidate_found": True,
                            "anchor_match": True,
                            "anchor_weight": 1.0,
                            "format_valid": True,
                            "spatial_proximity": 1.0,
                            "source_quality": 1.0,
                            "region": "summary",
                        },
                    )
                )

        for page in doc.pages:
            for block in page.blocks:
                code = detect_currency(block.text)
                if not code:
                    continue
                is_summary = block.region_type == "summary"
                found.append(
                    Candidate(
                        value=code,
                        normalized_value=code,
                        page_number=page.page_number,
                        bbox=block.bbox,
                        source_text=block.text,
                        anchor_text=None,
                        strategy="currency_scan",
                        signals={
                            "candidate_found": True,
                            "anchor_match": is_summary,
                            "anchor_weight": 0.8 if is_summary else 0.3,
                            "format_valid": True,
                            "spatial_proximity": 0.8 if is_summary else 0.4,
                            "source_quality": _source_quality(block),
                            "region": block.region_type,
                        },
                    )
                )

        for candidate in found:
            candidate.score = _score_candidate(candidate)
        return found

    # -- value building -----------------------------------------------------

    def _build(
        self,
        raw: str,
        spec: FieldSpec,
        page: Page,
        block: Block,
        anchor: str | None,
        strategy: str,
        anchor_weight: float,
        proximity: float,
    ) -> Candidate | None:
        raw = normalize_text(raw)
        if not raw:
            return None

        value: str | None = None
        normalized: str | None = None
        format_valid = False

        if spec.value_type == "money":
            parsed = parse_money(raw)
            if parsed is not None and parsed > 0:
                value = format_money(parsed)
                normalized = str(parsed)
                format_valid = True
        elif spec.value_type == "date":
            parsed_date = parse_date(raw)
            if parsed_date:
                value = format_date(parsed_date[0])
                normalized = parsed_date[0].isoformat()
                format_valid = True
        elif spec.name == "bill_no":
            identifier = extract_identifier(raw)
            if identifier:
                value = identifier
                normalized = identifier
                format_valid = True
        else:  # locations and other free text
            if looks_like_place(raw) and not _is_pure_number(raw):
                value = raw
                normalized = raw
                format_valid = True

        if value is None or normalized is None:
            return None

        candidate = Candidate(
            value=value,
            normalized_value=normalized,
            page_number=page.page_number,
            bbox=block.bbox,
            source_text=normalize_text(block.text),
            anchor_text=anchor,
            strategy=strategy,
            signals={
                "candidate_found": True,
                "anchor_match": anchor is not None,
                "anchor_weight": anchor_weight,
                "format_valid": format_valid,
                "spatial_proximity": round(proximity, 3),
                "source_quality": _source_quality(block),
                "region": block.region_type,
            },
        )
        candidate.score = _score_candidate(candidate, spec)
        return candidate

    # -- helpers ------------------------------------------------------------

    @staticmethod
    def _anchor_weight(index: int, total: int) -> float:
        """Earlier anchors in a spec are the more specific ones."""
        if total <= 1:
            return 1.0
        return round(1.0 - (index / total) * 0.55, 3)

    @staticmethod
    def _is_negative(text: str, spec: FieldSpec, anchor: str) -> bool:
        lowered = text.lower()
        for negative in spec.negative_anchors:
            if contains_anchor(lowered, negative) and negative != anchor:
                # "Subtotal" must not be picked up by the "total" anchor.
                if anchor in negative or negative.startswith(anchor):
                    return True
                if contains_anchor(lowered, negative) and anchor not in lowered.replace(
                    negative, ""
                ):
                    return True
        return False


# --------------------------------------------------------------------------
# Geometry helpers
# --------------------------------------------------------------------------


def _blocks_right_of(page: Page, block: Block) -> list[Block]:
    tolerance = block.height * _ROW_TOLERANCE
    center_y = block.center[1]
    neighbours = [
        b
        for b in page.blocks
        if b.id != block.id and b.x0 >= block.x1 - 2 and abs(b.center[1] - center_y) <= tolerance
    ]
    return sorted(neighbours, key=lambda b: b.x0)


def _blocks_below(page: Page, block: Block) -> list[Block]:
    max_gap = block.height * _BELOW_TOLERANCE
    neighbours = [
        b
        for b in page.blocks
        if b.id != block.id
        and b.y0 >= block.y1 - 1
        and b.y0 - block.y1 <= max_gap
        and not (b.x1 < block.x0 - 5 or b.x0 > block.x1 + 60)
    ]
    return sorted(neighbours, key=lambda b: (b.y0, b.x0))


def _proximity(anchor_block: Block, value_block: Block, page: Page) -> float:
    """1.0 = adjacent, decaying with distance from the label.

    Distance is measured anisotropically: bills routinely put a label on the
    left and its amount against the right margin, so horizontal separation on
    the same row is far weaker evidence of "unrelated" than vertical
    separation is.
    """
    gap_x = max(0.0, value_block.x0 - anchor_block.x1, anchor_block.x0 - value_block.x1)
    gap_y = abs(value_block.center[1] - anchor_block.center[1])
    width = page.width or 1.0
    height = page.height or 1.0
    return max(0.0, 1.0 - (gap_x / width) * 0.9 - (gap_y / height) * 6.0)


def _source_quality(block: Block) -> float:
    """PDF text is exact; OCR quality comes from the engine's own score."""
    if block.source == "pdf_text":
        return 1.0
    return round(min(max(block.confidence or 0.0, 0.0), 1.0), 3)


#: A timestamp like "7:59 am" - the spine of a ride receipt's itinerary.
_TIME_RE = re.compile(r"^\s*\d{1,2}[:.]\d{2}\s*(am|pm)?\s*$", re.I)


#: Six-digit postcode - the giveaway that a line is an address, not a name.
_PIN_RE = re.compile(r"\b\d{6}\b")

#: Words that place a line in an address rather than in a merchant's name.
_ADDRESS_HINTS = (
    "opp", "near", "road", "street", "lane", "marg", "nagar", "sector",
    "floor", "block", "phase", "airport", "terminal", "state code", "pin",
    "po box", "landmark", "branch",
)


def _is_bill_metadata(value: str) -> bool:
    """True for the lines that sit around a merchant's name but are not it.

    A bill's masthead holds the name plus its address, tax registrations and
    contact details, and on a till receipt the transaction header ("DATE:",
    "BILL:", "CASHIER NAME:") is right underneath. All of those are shaped
    differently from a name.
    """
    cleaned = normalize_text(value)
    if ":" in cleaned:  # TIME:, DATE:, BILL:, GSTIN:, CASHIER NAME:
        return True
    if _PIN_RE.search(cleaned):
        return True
    if parse_date(cleaned) or _TIME_RE.match(cleaned):
        return True
    lowered = cleaned.lower()
    if any(contains_anchor(lowered, hint) for hint in _ADDRESS_HINTS):
        return True
    # A single run-together token carrying a number is a store or terminal
    # code ("NDCIN1925"), not a trading name.
    if " " not in cleaned and re.search(r"\d{3,}", cleaned):
        return True
    return False


def _is_label_context(text: str) -> bool:
    """True when a block could carry a field label rather than prose.

    "To" and "From" are ordinary English words: without this, a sentence like
    "Want to review your trip history?" is read as a To Location label and the
    user is shown a confident-looking nonsense value.
    """
    cleaned = normalize_text(text)
    if ":" in cleaned:
        return True
    return len(cleaned.split()) < 5


def _anchor_is_label(text: str, anchor: str) -> bool:
    """True when the anchor introduces a value ("Hotel: X"), rather than being
    part of the value itself ("Hotel Sunrise")."""
    return bool(re.match(rf"^\s*{re.escape(anchor)}\s*[:\-–—#]", text, re.I))


def _is_pure_number(value: str) -> bool:
    stripped = value.replace(",", "").replace(".", "").replace(" ", "")
    return stripped.isdigit()


def _score_candidate(candidate: Candidate, spec: FieldSpec | None = None) -> float:
    """Rank candidates on observable evidence (Phase 8 signals)."""
    signals = candidate.signals
    score = 0.0
    score += 0.30 if signals.get("anchor_match") else 0.0
    score += 0.20 * float(signals.get("anchor_weight", 0.0))
    score += 0.15 if signals.get("format_valid") else 0.0
    score += 0.20 * float(signals.get("spatial_proximity", 0.0))
    score += 0.15 * float(signals.get("source_quality", 0.0))

    if signals.get("region") == "summary" and spec and spec.value_type == "money":
        score += 0.08
    if spec and spec.name == "hotel_name":
        # The merchant's own name is the most prominent line on the bill, and
        # the first name-shaped one on it.
        score += 0.35 * float(signals.get("prominence", 0.0))
        score += 0.20 * float(signals.get("header_rank", 0.0))
    if candidate.strategy == "unanchored":
        score -= 0.12
    return round(max(score, 0.0), 4)


def _dedupe(candidates: list[Candidate]) -> list[Candidate]:
    seen: set[tuple[str, int]] = set()
    unique: list[Candidate] = []
    for candidate in candidates:
        key = (candidate.normalized_value, candidate.page_number)
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
    return unique


claim_extractor = ClaimExtractor()
