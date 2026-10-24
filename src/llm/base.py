"""LLM provider interface.

A provider does exactly two jobs, both narrow:
  1. parse(question) -> a tool call with enum-validated arguments (a dict that
     nlu.py validates into a StructuredQuery). It must NOT answer.
  2. phrase(skeleton) -> optional nicer wording of an already-built answer. It
     must NOT introduce numbers.

Keeping the surface this small is what lets us swap providers freely and keep
grounding guarantees in query.py / answer.py.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class ParseOutcome:
    ok: bool
    arguments: dict | None = None   # raw tool-call args, validated by nlu.py
    error: str | None = None        # why parsing failed (triggers rule fallback)


# The single tool we expose to the model. Arguments are strictly enumerated so
# the model can only emit things we can execute.
QUERY_TOOL_SCHEMA = {
    "name": "query_places",
    "description": "Query CDC PLACES Massachusetts county data to answer a "
                   "question about chronic-condition prevalence or access.",
    "parameters": {
        "type": "object",
        "properties": {
            "intent": {"type": "string",
                       "enum": ["ranking", "lookup", "access_gap",
                                "refuse_medical", "out_of_scope"]},
            "condition": {"type": "string",
                          "enum": ["DIABETES", "CASTHMA", "BPHIGH", "COPD",
                                   "ACCESS2", "CHECKUP"]},
            "access_measure": {"type": "string",
                               "enum": ["ACCESS2", "CHECKUP"]},
            "area_filter": {"type": "string"},
            "sort": {"type": "string", "enum": ["desc", "asc"]},
            "limit": {"type": "integer"},
        },
        "required": ["intent"],
    },
}


@dataclass
class HealthStatus:
    ok: bool
    message: str            # human-readable, safe to show in the UI


class LLMProvider(Protocol):
    name: str

    def parse(self, question: str) -> ParseOutcome:
        """Return a tool call for `question`, or ok=False to fall back."""
        ...

    def phrase(self, skeleton: str, allowed_numbers: list[float]) -> str:
        """Optionally reword `skeleton`. Must not add numbers not already in it."""
        ...

    def health(self) -> HealthStatus:
        """Report whether the provider is usable right now (startup check)."""
        ...
