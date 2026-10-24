"""Turn a StructuredQuery into a grounded, cited, hedged answer.

Pipeline: StructuredQuery -> run query.py -> build a text skeleton from the
returned rows ONLY -> assert every number in the text came from those rows
(the grounding check) -> return.

The templates contain no literal data numbers; all values are interpolated from
query results. The post-answer check is a belt-and-suspenders guarantee that
even an LLM-phrased variant cannot smuggle in an invented figure (R5.2, R5.3).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import pandas as pd

from . import config, query as Q
from .nlu import (StructuredQuery, RANKING, LOOKUP, ACCESS_GAP,
                  REFUSE_MEDICAL, OUT_OF_SCOPE, COUNTY_PROFILE, LIST_SUPPORTED,
                  UNSUPPORTED_YEAR)

RELEASE_DATA_YEAR = 2023
MODELED_NOTE = "Values are model-based estimates, not diagnosed case counts."
MEDICAL_REPLY = (
    "I can't give individual medical advice or diagnosis. For personal health "
    "questions, please talk to a clinician. I can tell you where conditions are "
    "most common across Massachusetts counties, though."
)


def _scope_reply() -> str:
    conds = ", ".join(config.MEASURES[m].label for m in config.CONDITIONS)
    access = ", ".join(config.MEASURES[m].label for m in config.ACCESS_MEASURES)
    return ("I can only answer from CDC PLACES data for Massachusetts counties. "
            f"Conditions I cover: {conds}. Access measures: {access}. "
            "Try: \"Where is diabetes highest?\" or \"high asthma and low checkup areas\".")


@dataclass
class Answer:
    text: str
    intent: str
    grounded: bool                 # did the grounding check pass?
    rows: list = None              # underlying result rows (for the UI table)
    source_line: str = ""


def _citation(data_year: int) -> str:
    return f"Source: {config.SOURCE} ({config.RELEASE_YEAR} release), data year {data_year}. {MODELED_NOTE}"


# --- Number extraction / grounding check ----------------------------------
_NUM_RE = re.compile(r"\d+\.\d+|\d+")


def extract_numbers(text: str) -> list[float]:
    """Numbers that represent data VALUES only. Strips fixed labels and prose
    that legitimately contain digits but are not estimates: the citation, the
    access-gap rule sentence, the "95% CI" level, measure labels like
    "(adults 18-64)", and rank ordinals."""
    # Drop the citation and the rule sentence (both start fixed markers).
    body = text.split("Source:")[0].split("Rule:")[0]
    # Drop fixed measure-label digits, e.g. "(adults 18-64)".
    for m in config.MEASURES.values():
        body = body.replace(m.label, "")
    # Drop the fixed "95% CI" / "95%" confidence-level label.
    body = re.sub(r"95%\s*(CI)?", "", body)
    # Collapse comma-grouped integers (e.g. "460,291") so they parse as one.
    body = re.sub(r"(\d),(?=\d{3}\b)", r"\1", body)
    # Drop leading "N." rank markers.
    body = re.sub(r"(?m)^\s*\d+\.", "", body)
    return [float(x) for x in _NUM_RE.findall(body)]


def grounding_check(text: str, allowed: list[float], tol: float = 0.05) -> bool:
    """Every data number in `text` must match a value from the query results."""
    allowed_set = allowed
    for n in extract_numbers(text):
        if not any(abs(n - a) <= tol for a in allowed_set):
            return False
    return True


# --- Builders --------------------------------------------------------------
def _hedged_lead(result: Q.QueryResult) -> str:
    top = result.rows[0]
    verb = "lowest" if result.sort == "asc" else "among the highest"
    lead = (f"{top.locationname} County is {verb} for {result.measure_label} "
            f"at {top.value:.1f}% (95% CI {top.low_ci:.1f} to {top.high_ci:.1f}).")
    if top.ci_overlaps_next and len(result.rows) > 1:
        nxt = result.rows[1]
        lead += (f" Note: this overlaps {nxt.locationname} ({nxt.value:.1f}%), "
                 "so the difference is within the margin of uncertainty.")
    return lead


def _ranking_body(result: Q.QueryResult, n: int = 5) -> str:
    lines = [f"{r.rank}. {r.locationname}: {r.value:.1f}% "
             f"(CI {r.low_ci:.1f} to {r.high_ci:.1f})" for r in result.rows[:n]]
    return "\n".join(lines)


def _county_profile(df: pd.DataFrame, county: str) -> Answer:
    """All six measures for one county, with CI and population."""
    sub = df[df["locationname"] == county]
    if sub.empty:
        return Answer(f"I don't have data for {county} County.\n\n"
                      f"{_citation(2023)}", COUNTY_PROFILE, grounded=True)
    pop = int(sub.iloc[0]["total_population"])
    lines, allowed = [], []
    for mid in config.MEASURES:
        row = sub[sub["measureid"] == mid]
        if row.empty:
            continue
        r = row.iloc[0]
        v, lo, hi = float(r["data_value"]), float(r["low_ci"]), float(r["high_ci"])
        allowed += [v, lo, hi]
        lines.append(f"- {config.MEASURES[mid].label}: {v:.1f}% "
                     f"(95% CI {lo:.1f} to {hi:.1f})")
    cite = _citation(2023)
    txt = (f"{county} County (population {pop:,}):\n" + "\n".join(lines) +
           f"\n\n{cite}")
    allowed.append(float(pop))
    return Answer(txt, COUNTY_PROFILE, grounding_check(txt, allowed),
                  rows=sub.to_dict("records"), source_line=cite)


def answer(df: pd.DataFrame, sq: StructuredQuery) -> Answer:
    # Guardrails: no query runs.
    if sq.intent == REFUSE_MEDICAL:
        return Answer(MEDICAL_REPLY, sq.intent, grounded=True)
    if sq.intent in (OUT_OF_SCOPE, LIST_SUPPORTED):
        return Answer(_scope_reply(), sq.intent, grounded=True)
    if sq.intent == UNSUPPORTED_YEAR:
        return Answer(
            f"I only have {config.SOURCE} data for {RELEASE_DATA_YEAR}. "
            "I can't show figures for other years.", sq.intent, grounded=True)
    if sq.intent == COUNTY_PROFILE and sq.area_filter:
        return _county_profile(df, sq.area_filter)
    if sq.condition is None and sq.intent != ACCESS_GAP:
        return Answer(_scope_reply(), OUT_OF_SCOPE, grounded=True)

    if sq.intent == ACCESS_GAP:
        gap = Q.run_access_gap(df, sq.condition, sq.access_measure or "CHECKUP")
        cite = _citation(config.measure_year(sq.condition))
        if not gap.rows:
            txt = (f"No Massachusetts county is both high for {gap.condition_label} "
                   f"and low for {gap.access_label}. Rule: {gap.rule}\n\n{cite}")
            return Answer(txt, sq.intent, grounded=True, rows=[], source_line=cite)
        lines = [f"- {r.locationname}: {gap.condition_label} {r.condition_value:.1f}%, "
                 f"{gap.access_label} {r.access_value:.1f}%" for r in gap.rows]
        txt = (f"Access-gap areas (high {gap.condition_label} + low "
               f"{gap.access_label}):\n" + "\n".join(lines) +
               f"\n\nRule: {gap.rule}\n\n{cite}")
        allowed = [v for r in gap.rows for v in (r.condition_value, r.access_value)]
        return Answer(txt, sq.intent, grounding_check(txt, allowed),
                      rows=gap.rows, source_line=cite)

    # ranking / lookup
    if sq.intent == LOOKUP and sq.area_filter and not sq.area_in:
        result = Q.run_lookup(df, sq.condition, sq.area_filter)
    else:
        result = Q.run_ranking(df, sq.condition, sort=sq.sort,
                               limit=sq.limit, area_filter=sq.area_filter,
                               area_in=sq.area_in)

    cite = _citation(result.data_year)
    if not result.rows:
        area = f" for \"{sq.area_filter}\"" if sq.area_filter else ""
        txt = (f"I don't have data{area} for {config.MEASURES[sq.condition].label} "
               f"in Massachusetts counties.\n\n{cite}")
        return Answer(txt, sq.intent, grounded=True, rows=[], source_line=cite)

    if sq.intent == LOOKUP and sq.area_filter and len(result.rows) == 1:
        r = result.rows[0]
        txt = (f"{r.locationname} County: {result.measure_label} "
               f"{r.value:.1f}% (95% CI {r.low_ci:.1f} to {r.high_ci:.1f}).\n\n{cite}")
    else:
        txt = (_hedged_lead(result) + "\n\nTop results:\n" +
               _ranking_body(result) + f"\n\n{cite}")

    return Answer(txt, sq.intent, grounding_check(txt, result.values()),
                  rows=result.rows, source_line=cite)
