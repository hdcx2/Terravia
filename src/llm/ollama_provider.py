"""Local Ollama provider via the OpenAI-compatible endpoint.

Talks to Ollama at http://localhost:11434/v1 using the `openai` SDK (Ollama
mirrors that API). Two parsing modes, selectable by config/env:

  - "tool"  : native OpenAI-style tool calling (model returns a tool call).
  - "json"  : the model returns a JSON object {"tool": "...", "arguments": {...}},
              which we parse and validate against the same enums. Useful for
              local models whose tool-calling support is weak.

Either way the output is enum-validated downstream in nlu.py, and the
rule-based parser remains the fallback. Config:

  HOTSPOT_LLM_PROVIDER=ollama
  HOTSPOT_LLM_MODEL=qwen2.5:7b          # required model name
  HOTSPOT_OLLAMA_MODE=tool|json         # default: tool
  HOTSPOT_OLLAMA_URL=http://localhost:11434/v1
  HOTSPOT_LLM_TIMEOUT=60                # seconds; local models are slower
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from .base import LLMProvider, ParseOutcome, HealthStatus, QUERY_TOOL_SCHEMA
from .. import config

DEFAULT_URL = "http://localhost:11434/v1"

# Few-shot examples. Phrasings chosen to be DISTINCT from the eval set, to teach
# two patterns the small model gets wrong: access_gap (a condition + an access
# word together) and "near X" (a county with surrounding-area intent).
FEWSHOT = (
    "Examples:\n"
    "Q: Counties where emphysema is common but few adults see a doctor yearly\n"
    "A: intent=access_gap, condition=COPD, access_measure=CHECKUP\n"
    "Q: Spots with lots of hypertension and many people lacking coverage\n"
    "A: intent=access_gap, condition=BPHIGH, access_measure=ACCESS2\n"
    "Q: Diabetes burden in the area surrounding Springfield\n"
    "A: intent=ranking, condition=DIABETES, area_filter=Springfield\n"
    "Q: Asthma around Pittsfield and its neighbors\n"
    "A: intent=ranking, condition=CASTHMA, area_filter=Pittsfield\n"
    "Q: How does cancer vary across the state?\n"
    "A: intent=out_of_scope  (cancer is not a supported measure)\n"
    "Q: Give me the rundown for Essex\n"
    "A: intent=county_profile, area_filter=Essex  (county named, no measure)\n"
)

SYSTEM_TOOL = (
    "You translate questions into a single call to the query_places tool for "
    "CDC PLACES Massachusetts COUNTY data. You never answer directly and never "
    "produce numbers. Supported conditions: diabetes (DIABETES), asthma "
    "(CASTHMA), high blood pressure (BPHIGH), COPD. Access measures: uninsured "
    "(ACCESS2), routine checkup (CHECKUP). When a question mentions BOTH a "
    "condition AND access or checkups/coverage, use intent='access_gap'. For a "
    "place with 'near' or 'around', set area_filter to the place name. If the "
    "question asks for individual medical advice or diagnosis, use "
    "intent='refuse_medical'. If it is outside Massachusetts or these measures, "
    "use intent='out_of_scope'. Otherwise pick ranking, lookup, or access_gap.\n\n"
    + FEWSHOT
)

# JSON mode: describe the exact object we want back, with the enums inline.
SYSTEM_JSON = SYSTEM_TOOL + (
    "\n\nRespond with ONLY a JSON object, no prose, of the form:\n"
    '{"tool": "query_places", "arguments": {"intent": "...", "condition": "...", '
    '"access_measure": "...", "area_filter": "...", "sort": "desc|asc", '
    '"limit": 10}}\n'
    "intent is required and one of: ranking, lookup, access_gap, refuse_medical, "
    "out_of_scope. condition is one of DIABETES, CASTHMA, BPHIGH, COPD, ACCESS2, "
    "CHECKUP. access_measure is ACCESS2 or CHECKUP. Omit fields you don't need."
)


def _base_url() -> str:
    return os.environ.get("HOTSPOT_OLLAMA_URL", DEFAULT_URL).rstrip("/")


def _model() -> str:
    return os.environ.get("HOTSPOT_LLM_MODEL") or config.LLM_MODEL or ""


def _mode() -> str:
    return os.environ.get("HOTSPOT_OLLAMA_MODE", "tool").lower()


def _server_root() -> str:
    # The /v1 endpoint is OpenAI-compatible; the native API (for /api/tags) is
    # one level up.
    return _base_url()[:-3] if _base_url().endswith("/v1") else _base_url()


def ollama_health(model: str | None = None) -> HealthStatus:
    """Startup check: is the server up, and is the model pulled? Standalone so
    the app can call it without constructing the provider."""
    model = model or _model()
    root = _server_root()
    if not model:
        return HealthStatus(ok=False,
                            message="No model set. Set HOTSPOT_LLM_MODEL "
                                    "(e.g. qwen2.5:7b).")
    try:
        with urllib.request.urlopen(f"{root}/api/tags", timeout=4) as r:
            tags = json.loads(r.read().decode())
    except (urllib.error.URLError, OSError, ValueError):
        return HealthStatus(ok=False,
                            message=f"Ollama not reachable at {root}. Start it "
                                    "with `ollama serve`.")
    installed = [m.get("name", "") for m in tags.get("models", [])]
    # Accept exact or base-name match (e.g. "qwen2.5:7b" vs "qwen2.5").
    if not any(model == n or n.startswith(model.split(":")[0]) for n in installed):
        shown = ", ".join(installed) or "none"
        return HealthStatus(ok=False,
                            message=f"Model '{model}' not pulled. Run "
                                    f"`ollama pull {model}`. Installed: {shown}.")
    return HealthStatus(ok=True,
                        message=f"Ollama ready ({model}, mode={_mode()}).")


class OllamaProvider:
    name = "ollama"

    def __init__(self) -> None:
        try:
            from openai import OpenAI
        except ImportError as e:
            raise RuntimeError("openai SDK not installed") from e
        self._model = _model()
        if not self._model:
            raise RuntimeError("HOTSPOT_LLM_MODEL not set for Ollama")
        self._mode = _mode()
        self._timeout = float(os.environ.get("HOTSPOT_LLM_TIMEOUT", "60"))
        # Ollama ignores the key but the SDK requires a non-empty one.
        self._client = OpenAI(base_url=_base_url(), api_key="ollama",
                              timeout=self._timeout)

    # --- parsing modes ----------------------------------------------------
    def _parse_tool(self, question: str) -> ParseOutcome:
        resp = self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "system", "content": SYSTEM_TOOL},
                      {"role": "user", "content": question}],
            tools=[{"type": "function", "function": QUERY_TOOL_SCHEMA}],
            tool_choice="auto",
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

    def _parse_json(self, question: str) -> ParseOutcome:
        resp = self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "system", "content": SYSTEM_JSON},
                      {"role": "user", "content": question}],
            response_format={"type": "json_object"},
            temperature=0,
        )
        content = resp.choices[0].message.content or ""
        obj = json.loads(content)
        if not isinstance(obj, dict):
            return ParseOutcome(ok=False, error="json content not an object")
        # Accept either {"tool","arguments"} or a bare arguments object.
        args = obj.get("arguments", obj)
        if not isinstance(args, dict):
            return ParseOutcome(ok=False, error="arguments not an object")
        return ParseOutcome(ok=True, arguments=args)

    def parse(self, question: str) -> ParseOutcome:
        try:
            if self._mode == "json":
                return self._parse_json(question)
            return self._parse_tool(question)
        except Exception as e:  # any failure -> rule fallback
            return ParseOutcome(ok=False, error=f"ollama parse failed: {e}")

    def phrase(self, skeleton: str, allowed_numbers: list[float]) -> str:
        return skeleton

    def health(self) -> HealthStatus:
        return ollama_health(self._model)
