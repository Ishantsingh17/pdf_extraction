"""Claim-head schema registry."""
from __future__ import annotations

from app.rules.common import ClaimHeadSchema
from app.rules.food import FOOD_SCHEMA
from app.rules.travel import TRAVEL_SCHEMA

CLAIM_HEADS: dict[str, ClaimHeadSchema] = {
    TRAVEL_SCHEMA.key: TRAVEL_SCHEMA,
    FOOD_SCHEMA.key: FOOD_SCHEMA,
}

#: Accepts the key, the label, or a slug from the UI.
_ALIASES: dict[str, str] = {
    "travel_conveyance": TRAVEL_SCHEMA.key,
    "travel conveyance": TRAVEL_SCHEMA.key,
    "travel": TRAVEL_SCHEMA.key,
    "food": FOOD_SCHEMA.key,
}


def resolve_claim_head(value: str) -> ClaimHeadSchema | None:
    if not value:
        return None
    key = value.strip()
    if key.upper() in CLAIM_HEADS:
        return CLAIM_HEADS[key.upper()]
    alias = _ALIASES.get(key.lower())
    return CLAIM_HEADS[alias] if alias else None


__all__ = ["CLAIM_HEADS", "ClaimHeadSchema", "resolve_claim_head"]
