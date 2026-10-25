"""Curated knowledge base for RAG over Terravia's OWN content.

These snippets describe the project, the data, and the methodology. They let the
agent answer conceptual questions ("what is the access gap?", "how recent is the
data?", "what can you do?") helpfully, instead of refusing.

Scope rules that keep this safe:
  - Snippets are only about THIS project and THIS dataset. No general medical or
    world knowledge lives here.
  - Numbers in answers still come from the structured query path, never from an
    LLM. These snippets carry only facts we authored (definitions, scope, years).

Retrieval is deterministic keyword overlap (no vector DB): small corpus, works
offline, easy to reason about.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Snippet:
    id: str
    title: str
    keywords: tuple[str, ...]   # terms that should route a question here
    text: str


KB: list[Snippet] = [
    Snippet(
        id="what_is_terravia",
        title="What Terravia is",
        keywords=("terravia", "purpose", "help me", "help with", "what can you",
                  "what do you do", "what is this", "who is this for"),
        text=("Terravia helps clinicians, researchers, and public health teams "
              "see where chronic conditions cluster across Massachusetts "
              "counties, so outreach, screening, and trial recruitment can be "
              "aimed by evidence instead of guesswork. Ask about a condition "
              "(e.g. \"where is diabetes highest?\"), compare burden with "
              "access (\"high asthma and low checkup areas\"), or get a county "
              "profile (\"tell me about Hampden\")."),
    ),
    Snippet(
        id="data_source",
        title="Where the data comes from",
        keywords=("data", "source", "where", "come from", "cdc", "places",
                  "dataset", "recent", "year", "how old", "updated", "reliable"),
        text=("The data is CDC PLACES, County Data, 2025 release (dataset "
              "swc5-untb on data.cdc.gov), filtered to Massachusetts. All "
              "measures are data year 2023. It covers 14 counties and nine "
              "measures. These are model-based estimates, not counts of "
              "diagnosed patients."),
    ),
    Snippet(
        id="measures",
        title="What conditions and measures are covered",
        keywords=("conditions", "measures", "diseases", "cover", "supported",
                  "diabetes", "asthma", "copd", "blood pressure", "uninsured",
                  "checkup", "access", "which", "obesity", "smoking",
                  "mental distress"),
        text=("Seven health measures: diabetes, current asthma, high blood "
              "pressure, COPD, obesity, frequent mental distress, and current "
              "smoking. Two access/prevention measures: lack of health "
              "insurance among adults 18-64, and a routine checkup in the past "
              "year. Each is reported as a crude prevalence percentage per "
              "county."),
    ),
    Snippet(
        id="access_gap",
        title="What the access gap means",
        keywords=("access", "gap", "mean", "definition", "high burden",
                  "low access", "thin", "need", "overlap", "tercile",
                  "how do you define", "what is the access"),
        text=("The access gap flags counties where a condition is common AND "
              "access is weak at the same time: in the top third of counties "
              "for the condition, and either the top third for uninsured rate "
              "or the bottom third for routine checkups. It points to places "
              "where need is high but care is thin, the strongest case for "
              "targeted outreach."),
    ),
    Snippet(
        id="estimates_ci",
        title="Why values are estimates with confidence intervals",
        keywords=("estimate", "model", "confidence", "interval", "ci",
                  "accurate", "margin", "uncertainty", "exact", "reliable",
                  "trust", "why", "significant"),
        text=("PLACES values are model-based estimates with 95% confidence "
              "intervals, not exact case counts. Across Massachusetts counties "
              "the intervals often overlap, so the app says a county is \"among "
              "the highest\" rather than definitively the highest, and shows "
              "the interval so differences can be read honestly."),
    ),
    Snippet(
        id="scope_geo",
        title="Geographic scope",
        keywords=("town", "town level", "city", "zip", "tract", "census",
                  "granular", "nationwide", "other states", "level",
                  "geographic", "smaller area"),
        text=("Coverage is Massachusetts at the county level only, 14 counties. "
              "PLACES also publishes town, census-tract, and ZIP-code data and "
              "other states, but this app is scoped to MA counties to stay "
              "focused and fast."),
    ),
    Snippet(
        id="not_medical",
        title="Not medical advice",
        keywords=("medical", "advice", "diagnosis", "doctor", "treatment",
                  "should i", "safe", "personal", "my health"),
        text=("Terravia reports population-level estimates for places, not "
              "guidance for individuals. It does not give medical advice or "
              "diagnosis. For personal health questions, talk to a clinician."),
    ),
]


_STOP = {"the", "a", "an", "is", "are", "of", "in", "to", "for", "and", "or",
         "do", "does", "what", "how", "me", "you", "your", "i", "it", "this",
         "that", "with", "on", "about", "can", "tell", "show", "give"}


def _tokens(text: str) -> set[str]:
    return {w.strip("?.,!\"'()").lower() for w in text.split()} - _STOP


def retrieve(question: str, k: int = 2, min_score: int = 1) -> list[Snippet]:
    """Return the top-k snippets by keyword overlap. Deterministic, offline.

    Returns [] when nothing scores above the threshold, so the caller can fall
    back to the generic capability message rather than forcing an answer."""
    q = _tokens(question)
    scored: list[tuple[int, Snippet]] = []
    for s in KB:
        score = sum(1 for kw in s.keywords if kw in question.lower())
        score += len(q & _tokens(s.title))
        if score >= min_score:
            scored.append((score, s))
    scored.sort(key=lambda x: -x[0])
    return [s for _, s in scored[:k]]
