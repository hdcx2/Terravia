"""Central configuration: dataset identity, measure registry, thresholds.

Everything the rest of the app needs to know about *what* data we have lives
here. No logic: just facts and small helpers over them.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# --- Paths -----------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
SNAPSHOT_CSV = DATA_DIR / "snapshot_places_ma.csv"
SNAPSHOT_META = DATA_DIR / "snapshot_meta.json"

# --- Source identity (confirmed live; see findings.md) ---------------------
SOURCE = "CDC PLACES"
DATASET_ID = "swc5-untb"            # PLACES County, 2025 release
DATASET_URL = f"https://data.cdc.gov/resource/{DATASET_ID}.json"
RELEASE_YEAR = 2025
STATE = "MA"
DATA_VALUE_TYPE = "Crude prevalence"


@dataclass(frozen=True)
class Measure:
    measureid: str          # stable PLACES key, used for filtering
    label: str              # human display label
    aliases: tuple[str, ...]  # words a user might type
    kind: str               # "condition" | "access"
    # direction: is a HIGH value "bad" (more burden / worse access)?
    # conditions + uninsured -> True; routine checkup -> False.
    high_is_bad: bool
    data_year: int          # per-measure BRFSS year (all 2023 in this slice)


# Registry: the 6 measures in scope. Order = display order.
MEASURES: dict[str, Measure] = {
    "DIABETES": Measure("DIABETES", "Diabetes",
                        ("diabetes", "diabetic"), "condition", True, 2023),
    "CASTHMA": Measure("CASTHMA", "Current asthma",
                       ("asthma", "asthmatic"), "condition", True, 2023),
    "BPHIGH": Measure("BPHIGH", "High blood pressure",
                      ("high blood pressure", "hypertension", "blood pressure"),
                      "condition", True, 2023),
    "COPD": Measure("COPD", "COPD",
                    ("copd", "emphysema", "chronic obstructive"),
                    "condition", True, 2023),
    "ACCESS2": Measure("ACCESS2", "Uninsured (adults 18-64)",
                       ("uninsured", "insurance", "no insurance",
                        "health insurance", "coverage"),
                       "access", True, 2023),
    "CHECKUP": Measure("CHECKUP", "Routine checkup (past year)",
                       ("checkup", "check-up", "routine checkup",
                        "doctor visit", "see the doctor", "see a doctor",
                        "seeing the doctor", "skip the doctor",
                        "skipping the doctor", "visit the doctor",
                        "annual visit", "yearly visit", "preventive"),
                       "access", False, 2023),
}

CONDITIONS = tuple(m for m, v in MEASURES.items() if v.kind == "condition")
ACCESS_MEASURES = tuple(m for m, v in MEASURES.items() if v.kind == "access")

# --- Access-gap thresholds (see findings.md #2) ----------------------------
# Tercile rule: with 14 counties, top/bottom third is ~5 counties.
TERCILE_FRACTION = 1 / 3

# --- LLM provider selection ------------------------------------------------
# Name of the provider class to use; "null" = rule-based only (demo-safe default).
LLM_PROVIDER = "null"            # override via env in llm factory
LLM_MODEL = ""                   # e.g. "gpt-4o-mini"; blank with null provider


def measure_year(measureid: str) -> int:
    """Per-measure data year for citations (R6)."""
    return MEASURES[measureid].data_year


def valid_measure_ids() -> list[str]:
    return list(MEASURES.keys())
