"""Load the MA PLACES data into a tidy DataFrame.

Order of preference (R1): local parquet cache -> bundled snapshot CSV ->
live Socrata fetch. The bundled snapshot means the demo works offline from
minute one, so the live path is really just a refresh convenience.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone

import pandas as pd

from . import config

NUMERIC_COLS = ["data_value", "low_ci", "high_ci", "total_population"]


@dataclass
class Provenance:
    source: str
    dataset_id: str
    dataset_url: str
    release_year: int
    data_year: int
    retrieved_at: str
    origin: str  # "snapshot" | "live"


def _coerce(df: pd.DataFrame) -> pd.DataFrame:
    for c in NUMERIC_COLS:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def load_snapshot() -> tuple[pd.DataFrame, Provenance]:
    """Load the bundled offline CSV. Always available in the repo."""
    df = _coerce(pd.read_csv(config.SNAPSHOT_CSV, dtype={"locationid": str}))
    meta = {}
    if config.SNAPSHOT_META.exists():
        meta = json.loads(config.SNAPSHOT_META.read_text())
    prov = Provenance(
        source=config.SOURCE,
        dataset_id=config.DATASET_ID,
        dataset_url=config.DATASET_URL,
        release_year=meta.get("release_year", config.RELEASE_YEAR),
        data_year=meta.get("data_year", 2023),
        retrieved_at=datetime.now(timezone.utc).isoformat(),
        origin="snapshot",
    )
    return df, prov


def fetch_live(timeout: int = 20) -> tuple[pd.DataFrame, Provenance]:
    """Pull fresh data from Socrata. Raises on failure so callers can fall back."""
    import requests  # local import keeps offline runs dependency-light

    ids = ",".join(f"'{m}'" for m in config.valid_measure_ids())
    where = (
        f"stateabbr='{config.STATE}' "
        f"AND measureid in({ids}) "
        f"AND data_value_type='{config.DATA_VALUE_TYPE}'"
    )
    params = {"$where": where, "$limit": 5000}
    resp = requests.get(config.DATASET_URL, params=params, timeout=timeout)
    resp.raise_for_status()
    raw = pd.DataFrame(resp.json())

    df = pd.DataFrame({
        "locationid": raw["locationid"].astype(str),
        "locationname": raw["locationname"],
        "geo_level": "county",
        "stateabbr": raw["stateabbr"],
        "measureid": raw["measureid"],
        "measure_label": raw["measureid"].map(lambda m: config.MEASURES[m].label),
        "measure_kind": raw["measureid"].map(lambda m: config.MEASURES[m].kind),
        "data_value": raw["data_value"],
        "data_value_type": raw["data_value_type"],
        "low_ci": raw["low_confidence_limit"],
        "high_ci": raw["high_confidence_limit"],
        "total_population": raw["totalpopulation"],
        "data_year": raw["measureid"].map(config.measure_year),
        "source": config.SOURCE,
        "release_year": config.RELEASE_YEAR,
    })
    df = _coerce(df)
    prov = Provenance(
        source=config.SOURCE, dataset_id=config.DATASET_ID,
        dataset_url=config.DATASET_URL, release_year=config.RELEASE_YEAR,
        data_year=2023, retrieved_at=datetime.now(timezone.utc).isoformat(),
        origin="live",
    )
    return df, prov


def load(prefer_live: bool = False) -> tuple[pd.DataFrame, Provenance]:
    """Main entry. Snapshot by default; live only if asked and reachable."""
    if prefer_live:
        try:
            return fetch_live()
        except Exception:
            pass  # fall through to the always-present snapshot
    return load_snapshot()


def provenance_dict(prov: Provenance) -> dict:
    return asdict(prov)
