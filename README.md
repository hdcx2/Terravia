# Terravia

A grounded AI chatbot that identifies where chronic conditions cluster across
Massachusetts counties, using public CDC PLACES data and citing every figure.

Ask in plain language ("Where is diabetes highest?", "high asthma and low
checkup areas") and get answers computed from the data, never from model memory,
with the source, data year, and a model-based-estimate caveat on every result.

- **Live site:** https://hdcx2.github.io/Terravia/index.html
- **API:** https://terravia-api.onrender.com

## What it covers

- **Geography:** 14 Massachusetts counties (CDC PLACES County, 2025 release, 2023 data)
- **Conditions:** diabetes, asthma, high blood pressure, COPD, obesity, frequent mental distress, smoking
- **Access measures:** uninsured (adults 18 to 64), routine checkup
- **Access gap:** flags counties where burden is high *and* access is thin

## Data source (exactly where the numbers come from)

- **Provider:** CDC PLACES: *Local Data for Better Health*.
- **Dataset:** PLACES **County** Data, **2025 release**, Socrata id **`swc5-untb`**.
- **Portal page:** https://data.cdc.gov/d/swc5-untb
- **API endpoint:** https://data.cdc.gov/resource/swc5-untb.json
- **Filter we apply:** `stateabbr = 'MA'`, `data_value_type = 'Crude prevalence'`.
- **Data year:** 2023 for every measure.
- **Nature:** model-based estimates (small-area modeling of BRFSS survey data),
  **not** counts of diagnosed patients.

### Full dataset vs. what the app uses

The full `swc5-untb` dataset for Massachusetts has **40 measures × 14 counties =
560 rows**. The app deliberately uses a **9-measure subset** (clinical +
behavioral: diabetes, asthma, high blood pressure, COPD, obesity, mental
distress, smoking, uninsured, routine checkup) so the tool stays focused on
health burden + access. The other 31 measures
live in the same dataset and can be added by editing the measure list in
`src/config.py`: no new source required.

### Reproduce the pull

```sh
# The 6 measures the app uses, for MA counties:
curl "https://data.cdc.gov/resource/swc5-untb.json?stateabbr=MA&data_value_type=Crude%20prevalence&\$where=measureid%20in('DIABETES','CASTHMA','BPHIGH','COPD','OBESITY','MHLTH','CSMOKING','ACCESS2','CHECKUP')&\$limit=5000"

# The FULL set (all 40 measures) for MA counties:
curl "https://data.cdc.gov/resource/swc5-untb.json?stateabbr=MA&data_value_type=Crude%20prevalence&\$limit=5000"
```

### Data files in `data/`

| File | Contents | Rows |
|---|---|---|
| `snapshot_places_ma.csv` | the 9-measure clinical+behavioral set: **what the app loads** | 126 |
| `places_ma_full.csv` | all 40 PLACES measures for MA (the complete menu) | 560 |
| `places_ma_behavioral.csv` | alt set: smoking, mental distress, obesity, diabetes, checkup | 70 |
| `ma_counties.geojson` | county boundary shapes for the map | 14 |
| `snapshot_meta.json` | provenance record (dataset id, URL, years, measures) |: |

The app loads `snapshot_places_ma.csv` by default so it works offline. Set
`prefer_live=True` (in `data_loader.load`) to pull fresh from the Socrata API
instead.

## Architecture

- `src/`: the agent. A rule-first router (`nlu.py`) with guardrails, a grounded
  answer builder (`answer.py`), a query engine over the data (`query.py`), and
  swappable LLM providers (`llm/`: null / OpenAI / Ollama).
- `api.py`: FastAPI backend exposing `POST /chat` and `GET /health`.
- `index.html`, `script.js`, `styles.css`, `images/`: the static website; the
  home page chat card calls the API (endpoint set in `config.js`).
- `data/`: offline CDC PLACES snapshot + county GeoJSON, so the agent runs
  without network access.
- `eval/`: regression suites (questions, guardrails, LLM router).

## Run locally

```sh
python -m venv .venv && .venv/bin/pip install -r requirements.txt
# Serve the API and the site from one origin:
TERRAVIA_SERVE_SITE=1 .venv/bin/uvicorn api:app --port 8000
# open http://localhost:8000/
```

The chatbot answers with the rule-based parser by default (no API key needed).
Set `HOTSPOT_LLM_PROVIDER=openai` (with `OPENAI_API_KEY`) or `ollama`
(with `HOTSPOT_LLM_MODEL`) to enable a language-model parser; the rule-based
parser remains the fallback.

## Tests

```sh
.venv/bin/python -m eval.eval_questions      # intent + grounding over sample questions
.venv/bin/python -m eval.eval_guardrails     # medical / unsupported-topic / year / county-profile
.venv/bin/python -m eval.eval_llm_router     # two-stage router behavior
```

Data are model-based estimates from CDC PLACES, not diagnosed case counts, and
are not medical advice.
