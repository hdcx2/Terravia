"""The query engine: the ONLY place numbers come from.

Everything the chatbot, table, map, and access-gap view show is produced here
by filtering the loaded DataFrame. The LLM never emits a value: it only chooses
the query. That is what makes answers grounded (R5.2).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import pandas as pd

from . import config


@dataclass
class ResultRow:
    rank: int
    locationname: str
    locationid: str
    measureid: str
    measure_label: str
    value: float
    low_ci: float
    high_ci: float
    population: int
    data_year: int
    ci_overlaps_next: bool = False  # R5.10: is this row distinct from the next?


@dataclass
class QueryResult:
    measureid: str
    measure_label: str
    rows: list[ResultRow]
    sort: str
    data_year: int
    source: str = config.SOURCE

    def values(self) -> list[float]:
        """Every number a grounded answer is allowed to cite."""
        out: list[float] = []
        for r in self.rows:
            out += [r.value, r.low_ci, r.high_ci]
        return out


def _rank_measure(df: pd.DataFrame, measureid: str, *, ascending: bool) -> pd.DataFrame:
    sub = df[df["measureid"] == measureid].copy()
    sub = sub.dropna(subset=["data_value"])
    sub = sub.sort_values("data_value", ascending=ascending).reset_index(drop=True)
    return sub


def run_ranking(df: pd.DataFrame, measureid: str, *, sort: str = "desc",
                limit: int = 10, area_filter: str | None = None,
                area_in: list[str] | None = None) -> QueryResult:
    ascending = sort == "asc"
    sub = _rank_measure(df, measureid, ascending=ascending)

    if area_in:  # explicit county set (e.g. "near X" resolved via geo.py)
        sub = sub[sub["locationname"].isin(area_in)].reset_index(drop=True)
    elif area_filter:
        mask = sub["locationname"].str.contains(area_filter, case=False, na=False)
        sub = sub[mask].reset_index(drop=True)

    rows: list[ResultRow] = []
    for i, r in sub.head(limit).iterrows():
        rows.append(ResultRow(
            rank=i + 1, locationname=r["locationname"], locationid=str(r["locationid"]),
            measureid=measureid, measure_label=config.MEASURES[measureid].label,
            value=float(r["data_value"]), low_ci=float(r["low_ci"]),
            high_ci=float(r["high_ci"]),
            population=int(r["total_population"]) if pd.notna(r["total_population"]) else 0,
            data_year=config.measure_year(measureid),
        ))

    # CI-overlap flag: top vs the next row (findings #3: rankings aren't distinct).
    for i in range(len(rows) - 1):
        a, b = rows[i], rows[i + 1]
        rows[i].ci_overlaps_next = a.low_ci <= b.high_ci and b.low_ci <= a.high_ci

    return QueryResult(measureid=measureid,
                       measure_label=config.MEASURES[measureid].label,
                       rows=rows, sort=sort,
                       data_year=config.measure_year(measureid))


def run_lookup(df: pd.DataFrame, measureid: str, area_filter: str) -> QueryResult:
    """Value(s) for a named area: a ranking filtered to that area, no limit cut."""
    return run_ranking(df, measureid, sort="desc", limit=50, area_filter=area_filter)


# --- Access gap ------------------------------------------------------------
@dataclass
class GapRow:
    locationname: str
    condition_value: float
    access_value: float
    population: int


@dataclass
class GapResult:
    condition: str
    condition_label: str
    access_measure: str
    access_label: str
    rule: str
    rows: list[GapRow] = field(default_factory=list)


def _top_tercile_names(df: pd.DataFrame, measureid: str, *, worst_high: bool) -> set[str]:
    sub = _rank_measure(df, measureid, ascending=not worst_high)
    k = math.ceil(len(sub) * config.TERCILE_FRACTION)
    return set(sub.head(k)["locationname"])


def run_access_gap(df: pd.DataFrame, condition: str, access: str) -> GapResult:
    """Counties that are high-burden AND low-access (findings #2)."""
    cond_hi = _top_tercile_names(df, condition, worst_high=True)
    # For CHECKUP (high is good) the "gap" tier is the LOW end; for ACCESS2 the HIGH end.
    worst_high = config.MEASURES[access].high_is_bad
    access_tier = _top_tercile_names(df, access, worst_high=worst_high)
    flagged = cond_hi & access_tier

    vals = df.set_index(["locationname", "measureid"])["data_value"].to_dict()
    pop = df.set_index("locationname")["total_population"].to_dict()
    rows = [GapRow(
        locationname=n, condition_value=float(vals[(n, condition)]),
        access_value=float(vals[(n, access)]),
        population=int(pop[n]) if pd.notna(pop[n]) else 0,
    ) for n in sorted(flagged, key=lambda x: -vals[(x, condition)])]

    tier = "highest third" if config.MEASURES[access].high_is_bad else "lowest third"
    rule = (f"High burden = top third of counties for "
            f"{config.MEASURES[condition].label}; low access = {tier} for "
            f"{config.MEASURES[access].label} (~5 of 14 counties each).")
    return GapResult(condition=condition,
                     condition_label=config.MEASURES[condition].label,
                     access_measure=access,
                     access_label=config.MEASURES[access].label,
                     rule=rule, rows=rows)


# --- UI helpers ------------------------------------------------------------
def measure_frame(df: pd.DataFrame, measureid: str) -> pd.DataFrame:
    """All counties for one measure, ranked, with display columns. For map +
    table views. Still the single source of numbers."""
    res = run_ranking(df, measureid, sort="desc", limit=1000)
    return pd.DataFrame([{
        "rank": r.rank, "County": r.locationname, "locationid": r.locationid,
        "Percent": r.value, "Low": r.low_ci, "High": r.high_ci,
        "Population": r.population,
    } for r in res.rows])
