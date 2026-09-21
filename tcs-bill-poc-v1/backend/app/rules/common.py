"""Shared field definitions, normalization and parsing helpers.

New claim heads are added by declaring a schema here plus a rules module -
the pipeline, viewer and APIs stay unchanged (TRD section 16).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

# --------------------------------------------------------------------------
# Field schema
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class FieldSpec:
    """Declarative definition of one claim field."""

    name: str
    label: str
    value_type: str  # text | date | money | currency
    anchors: tuple[str, ...] = ()
    #: Anchors that must NOT be treated as the label (e.g. "date of birth").
    negative_anchors: tuple[str, ...] = ()
    required: bool = True
    #: Filled by the system rather than extracted (remarks).
    system_value: str | None = None
    order: int = 0


@dataclass(frozen=True)
class ClaimHeadSchema:
    key: str
    label: str
    fields: tuple[FieldSpec, ...] = field(default_factory=tuple)

    @property
    def extracted_fields(self) -> tuple[FieldSpec, ...]:
        return tuple(f for f in self.fields if f.system_value is None)

    def get(self, name: str) -> FieldSpec | None:
        return next((f for f in self.fields if f.name == name), None)


# --------------------------------------------------------------------------
# Currency - preserved exactly as printed on the bill (FR-07). Never forced
# to INR, never converted.
# --------------------------------------------------------------------------

CURRENCY_SYMBOLS: dict[str, str] = {
    "\u20b9": "INR",
    "rs.": "INR",
    "rs": "INR",
    "inr": "INR",
    "$": "USD",
    "us$": "USD",
    "usd": "USD",
    "\u20ac": "EUR",
    "eur": "EUR",
    "\u00a3": "GBP",
    "gbp": "GBP",
    "\u00a5": "JPY",
    "jpy": "JPY",
    "aed": "AED",
    "dhs.": "AED",
    "dhs": "AED",
    "dh": "AED",
    "sar": "SAR",
    "qar": "QAR",
    "omr": "OMR",
    "kwd": "KWD",
    "bhd": "BHD",
    "sgd": "SGD",
    "s$": "SGD",
    "aud": "AUD",
    "a$": "AUD",
    "cad": "CAD",
    "c$": "CAD",
    "chf": "CHF",
    "zar": "ZAR",
    "lkr": "LKR",
    "npr": "NPR",
    "myr": "MYR",
    "thb": "THB",
    "hkd": "HKD",
    "cny": "CNY",
    "rmb": "CNY",
}

KNOWN_CURRENCY_CODES: frozenset[str] = frozenset(CURRENCY_SYMBOLS.values())

#: Longest-first so "us$" wins over "$" and "rs." over "rs".
_CURRENCY_TOKENS = sorted(CURRENCY_SYMBOLS, key=len, reverse=True)

_AMOUNT_RE = re.compile(
    r"(?<![\w.])(\d{1,3}(?:,\d{2,3})*(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?)(?![\w])"
)


def detect_currency(text: str) -> str | None:
    """Return the ISO code for the currency printed in `text`, if recognised."""
    lowered = text.lower()
    for token in _CURRENCY_TOKENS:
        if token[0].isalpha():
            # Word boundary, so "IN" inside "INVOICE" is not read as a currency.
            if re.search(rf"(?<![a-z]){re.escape(token)}(?![a-z])", lowered):
                return CURRENCY_SYMBOLS[token]
        elif token in lowered:
            return CURRENCY_SYMBOLS[token]
    return None


def _to_decimal(raw: str) -> Decimal | None:
    try:
        return Decimal(raw.replace(",", ""))
    except InvalidOperation:
        return None


def parse_money(text: str) -> Decimal | None:
    """Parse the most plausible monetary value out of a text fragment."""
    cleaned = text.replace("\u20b9", " ").replace("\u00a0", " ")
    matches = _AMOUNT_RE.findall(cleaned)
    if not matches:
        return None
    values: list[Decimal] = []
    decimal_values: list[Decimal] = []
    for raw in matches:
        value = _to_decimal(raw)
        if value is None:
            continue
        values.append(value)
        if "." in raw:
            decimal_values.append(value)
    if not values:
        return None
    # Totals normally carry decimals; otherwise the largest number wins.
    return max(decimal_values) if decimal_values else max(values)


def format_money(value: Decimal) -> str:
    return f"{value:,.2f}"


# --------------------------------------------------------------------------
# Dates
# --------------------------------------------------------------------------

_MONTHS = (
    "january|february|march|april|june|july|august|september|october|november"
    "|december|jan|feb|mar|apr|may|jun|jul|aug|sept|sep|oct|nov|dec"
)

DATE_PATTERNS: tuple[tuple[re.Pattern[str], tuple[str, ...]], ...] = (
    # 2026-02-11
    (re.compile(r"\b(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})\b"), ("%Y/%m/%d",)),
    # 11/02/2026, 11-02-2026, 11.02.2026
    (
        re.compile(r"\b(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})\b"),
        ("%d/%m/%Y", "%d/%m/%y", "%m/%d/%Y", "%m/%d/%y"),
    ),
    # 11 Feb 2026 / 11-Feb-2026
    (
        re.compile(rf"\b(\d{{1,2}})[\s\-]*({_MONTHS})[\s\-,]*(\d{{2,4}})\b", re.I),
        ("%d/%b/%Y", "%d/%b/%y"),
    ),
    # Feb 11, 2026
    (
        re.compile(rf"\b({_MONTHS})[\s\-]+(\d{{1,2}})[\s\-,]+(\d{{2,4}})\b", re.I),
        ("%b/%d/%Y", "%b/%d/%y"),
    ),
)

_MONTH_ABBR = {
    "sept": "sep",
    "january": "jan",
    "february": "feb",
    "march": "mar",
    "april": "apr",
    "june": "jun",
    "july": "jul",
    "august": "aug",
    "september": "sep",
    "october": "oct",
    "november": "nov",
    "december": "dec",
}


def is_plausible_bill_date(value: date) -> bool:
    """A bill date should be a real, recent-ish calendar date."""
    today = date.today()
    return date(2000, 1, 1) <= value <= date(today.year + 1, 12, 31)


def parse_date(text: str) -> tuple[date, str] | None:
    """Return (date, matched_substring) for the first plausible date found."""
    for pattern, formats in DATE_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        parts = [p.strip(" -,") for p in match.groups()]
        parts = [_MONTH_ABBR.get(p.lower(), p.lower()) for p in parts]
        joined = "/".join(parts)
        for fmt in formats:
            try:
                parsed = datetime.strptime(joined, fmt).date()
            except ValueError:
                continue
            if is_plausible_bill_date(parsed):
                return parsed, match.group(0)
    return None


def format_date(value: date) -> str:
    """Display format used across the review screen."""
    return value.strftime("%d/%m/%Y")


# --------------------------------------------------------------------------
# Identifiers
# --------------------------------------------------------------------------

#: Ordered longest-form first, so a compound number is taken whole. Till
#: receipts print things like "BILL:D785I/2526/3192" - matching only the tail
#: ("2526/3192") looks plausible but is not the number the vendor would
#: recognise on a query.
_BILL_NO_RE = re.compile(
    r"\b("
    r"[A-Z0-9]{2,10}(?:[-/][A-Z0-9]{1,10}){1,4}"  # D785I/2526/3192, INV-2026-0042
    r"|[A-Z]{2,6}[-/ ]?\d{3,12}"  # FB-22104
    r"|\d{4,12}[-/]?[A-Z0-9]{0,6}"  # 22104
    r")\b"
)
_PHONE_RE = re.compile(r"\+?\d{10,13}")
_GSTIN_RE = re.compile(r"\b\d{2}[A-Z]{5}\d{4}[A-Z]\d[A-Z\d]{2}\b")


def looks_like_identifier(value: str) -> bool:
    """Plausible bill number - not a phone number, date or tax registration."""
    stripped = value.strip()
    if not 3 <= len(stripped) <= 32:
        return False
    if not any(ch.isdigit() for ch in stripped):
        return False
    if _PHONE_RE.fullmatch(stripped.replace(" ", "").replace("-", "")):
        return False
    if _GSTIN_RE.fullmatch(stripped):
        return False
    if parse_date(stripped):
        return False
    return True


def extract_identifier(text: str) -> str | None:
    match = _BILL_NO_RE.search(text.upper())
    if match and looks_like_identifier(match.group(1)):
        return match.group(1).strip()
    return None


# --------------------------------------------------------------------------
# Text helpers
# --------------------------------------------------------------------------

_LABEL_TRAIL_RE = re.compile(r"^[\s:\-\u2013\u2014.#]+")


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def strip_label(text: str, anchor: str) -> str:
    """Return the part of `text` that follows `anchor`."""
    lowered = text.lower()
    idx = lowered.find(anchor.lower())
    if idx == -1:
        return normalize_text(text)
    remainder = text[idx + len(anchor) :]
    return normalize_text(_LABEL_TRAIL_RE.sub("", remainder))


def contains_anchor(text: str, anchor: str) -> bool:
    """Whole-word anchor match, tolerant of ':' and punctuation."""
    pattern = rf"(?<![a-z0-9]){re.escape(anchor.lower())}(?![a-z0-9])"
    return re.search(pattern, text.lower()) is not None


def looks_like_place(value: str) -> bool:
    """Meaningful, address-like content (TRD section 10)."""
    cleaned = normalize_text(value)
    if not 2 <= len(cleaned) <= 120:
        return False
    letters = sum(ch.isalpha() for ch in cleaned)
    return letters >= 2 and letters / max(len(cleaned), 1) > 0.35


#: Words a bill prints about *itself* - its type, its service mode, its table
#: headings, its payment lines. None of them is ever a merchant's name, and on
#: a till receipt they are often set in the largest type on the page ("TAKE
#: AWAY"), so without this they outrank the real name.
_MERCHANT_NOISE = frozenset(
    {
        # document type
        "tax invoice", "invoice", "bill", "bill of supply", "receipt",
        "gst invoice", "gstin", "cash memo", "retail invoice", "credit note",
        "debit note", "duplicate", "original", "customer copy", "merchant copy",
        "estimate", "quotation", "proforma", "proforma invoice",
        # service mode
        "take away", "takeaway", "take", "away", "dine in", "dine-in", "delivery",
        "pickup", "pick up", "home delivery", "counter sale",
        # table headings
        "item", "items", "itm", "description", "particulars", "hsn", "sac",
        "hsn code", "rate", "qty", "quantity", "unit", "price", "value",
        "amount", "total", "sub total", "subtotal", "net amount", "gross amount",
        # payment / footer
        "paid by", "payment", "cash", "card", "upi", "credit card", "debit card",
        "thank you", "visit again", "thank you visit again", "terms and conditions",
        # menu section headings ("******** FOOD ********")
        "food", "beverage", "beverages", "drinks", "starters", "desserts",
    }
)

#: Leading/trailing decoration a till receipt wraps its headings in.
_DECORATION_RE = re.compile(r"^[\s\"'*=~_\-.:#<>\[\](){}]+|[\s\"'*=~_\-.:#<>\[\](){}]+$")


def looks_like_merchant(value: str) -> bool:
    """Meaningful merchant/hotel-like value."""
    cleaned = normalize_text(value)
    if not 3 <= len(cleaned) <= 120:
        return False
    if sum(ch.isalpha() for ch in cleaned) < 3:
        return False
    # '"TAX INVOICE"' and '***** FOOD *****' are the same heading as the bare
    # word, so the decoration comes off before the comparison.
    bare = _DECORATION_RE.sub("", cleaned).lower()
    if bare in _MERCHANT_NOISE:
        return False
    # A heading built only from noise words ("ITEM  HSN  RATE  QTY  TOTAL").
    words = [w for w in re.split(r"[\s,]+", bare) if w]
    if words and all(w in _MERCHANT_NOISE for w in words):
        return False
    return True
