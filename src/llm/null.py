"""Null provider: no external LLM.

`parse` always declines (ok=False) so nlu.py uses its rule-based parser.
`phrase` returns the skeleton unchanged. This is the demo-safe default.
"""
from __future__ import annotations

from .base import LLMProvider, ParseOutcome, HealthStatus


class NullProvider:
    name = "null"

    def parse(self, question: str) -> ParseOutcome:
        return ParseOutcome(ok=False, error="null provider: use rule-based parser")

    def phrase(self, skeleton: str, allowed_numbers: list[float]) -> str:
        return skeleton

    def health(self) -> HealthStatus:
        return HealthStatus(ok=True, message="Rule-based parser (no external LLM).")
