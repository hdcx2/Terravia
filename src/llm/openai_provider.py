"""Example hosted provider (OpenAI tool-calling).

Shown as the swap target. It only ever returns the query tool's arguments: never an answer, never a number. If the SDK or key is missing, construction
raises and the factory falls back to NullProvider.

This file is a scaffold: wire real SDK calls where marked. Keep the contract
(returns ParseOutcome with enum-valid args) identical to NullProvider.
"""
from __future__ import annotations

import json
import os

from .base import LLMProvider, ParseOutcome, HealthStatus, QUERY_TOOL_SCHEMA
from .. import config

SYSTEM = (
    "You translate questions into a single call to the query_places tool for "
    "CDC PLACES Massachusetts COUNTY data. You never answer directly and never "
    "produce numbers. Supported conditions: diabetes, asthma, high blood "
    "pressure, COPD. Access measures: uninsured (ACCESS2), routine checkup "
    "(CHECKUP). If the question asks for individual medical advice or diagnosis, "
    "set intent='refuse_medical'. If it is outside MA/these measures, set "
    "intent='out_of_scope'. Otherwise pick ranking, lookup, or access_gap."
)


class OpenAIProvider:
    name = "openai"

    def __init__(self) -> None:
        key = os.environ.get("OPENAI_API_KEY")
        if not key:
            raise RuntimeError("OPENAI_API_KEY not set")
        try:
            from openai import OpenAI
        except ImportError as e:
            raise RuntimeError("openai SDK not installed") from e
        self._model = os.environ.get("HOTSPOT_LLM_MODEL") or config.LLM_MODEL or "gpt-4o-mini"
        self._timeout = float(os.environ.get("HOTSPOT_LLM_TIMEOUT", "15"))
        # Build the client once; reuse across calls.
        self._client = OpenAI(timeout=self._timeout)

    def parse(self, question: str) -> ParseOutcome:
        try:
            resp = self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "system", "content": SYSTEM},
                          {"role": "user", "content": question}],
                tools=[{"type": "function", "function": QUERY_TOOL_SCHEMA}],
                tool_choice={"type": "function",
                             "function": {"name": "query_places"}},
                temperature=0,
            )
            msg = resp.choices[0].message
            calls = getattr(msg, "tool_calls", None)
            if not calls:
                return ParseOutcome(ok=False, error="no tool call returned")
            args = json.loads(calls[0].function.arguments)
            if not isinstance(args, dict):
                return ParseOutcome(ok=False, error="tool args not an object")
            return ParseOutcome(ok=True, arguments=args)
        except Exception as e:  # any failure -> rule fallback
            return ParseOutcome(ok=False, error=f"openai parse failed: {e}")

    def phrase(self, skeleton: str, allowed_numbers: list[float]) -> str:
        # For the demo, phrasing via LLM is optional; return skeleton to stay
        # safe. A real impl would reword but must not add numbers.
        return skeleton

    def health(self) -> HealthStatus:
        try:
            self._client.models.list()
            return HealthStatus(ok=True, message=f"OpenAI reachable ({self._model}).")
        except Exception as e:
            return HealthStatus(ok=False, message=f"OpenAI not reachable: {e}")
