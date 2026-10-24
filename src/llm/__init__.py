"""Swappable LLM providers. `get_provider` picks one from config/env.

The null provider (rule-based only) is the shipped default so the demo never
depends on a key or network.
"""
from __future__ import annotations

import os

from .base import LLMProvider, ParseOutcome, HealthStatus
from .null import NullProvider


def get_provider(name: str | None = None) -> LLMProvider:
    """Pick a provider. ANY construction failure (missing key, missing SDK,
    unknown name) falls back to NullProvider so the app never crashes on a
    misconfigured LLM: the rule-based parser still answers."""
    name = (name or os.environ.get("HOTSPOT_LLM_PROVIDER") or "null").lower()
    if name in ("null", "", "none", "rule", "rules"):
        return NullProvider()
    try:
        if name == "openai":
            from .openai_provider import OpenAIProvider
            return OpenAIProvider()
        if name == "ollama":
            from .ollama_provider import OllamaProvider
            return OllamaProvider()
    except Exception:
        return NullProvider()
    # Unknown name -> safe fallback.
    return NullProvider()


def provider_health(name: str | None = None) -> HealthStatus:
    """Startup health check for the configured provider, without requiring the
    provider to construct (so we can show a helpful message if it can't)."""
    name = (name or os.environ.get("HOTSPOT_LLM_PROVIDER") or "null").lower()
    if name in ("null", "", "none", "rule", "rules"):
        return HealthStatus(ok=True, message="Rule-based parser (no external LLM).")
    if name == "ollama":
        from .ollama_provider import ollama_health
        return ollama_health()
    # Other providers: construct and ask.
    try:
        return get_provider(name).health()
    except Exception as e:
        return HealthStatus(ok=False, message=f"{name} unavailable: {e}")


__all__ = ["LLMProvider", "ParseOutcome", "HealthStatus", "NullProvider",
           "get_provider", "provider_health"]
