# Terravia

A grounded AI chatbot that identifies where chronic conditions cluster across
Massachusetts counties, using public CDC PLACES data and citing every figure.

Ask in plain language ("Where is diabetes highest?", "high asthma and low
checkup areas") and get answers computed from the data, never from model memory,
with the source, data year, and a model-based-estimate caveat on every result.

- **Live site:** https://wilsonz347.github.io/Terravia/
- **API:** https://terravia-api.onrender.com

## What it covers

- **Geography:** 14 Massachusetts counties (CDC PLACES County, 2025 release, 2023 data)
- **Conditions:** diabetes, asthma, high blood pressure, COPD
- **Access measures:** uninsured (adults 18–64), routine checkup
- **Access gap:** flags counties where burden is high *and* access is thin

## Architecture

- `src/` — the agent: a rule-first router (`nlu.py`) with guardrails, a grounded
  answer builder (`answer.py`), a query engine over the data (`query.py`), and
  swappable LLM providers (`llm/`: null / OpenAI / Ollama).
- `api.py` — FastAPI backend exposing `POST /chat` and `GET /health`.
- `index.html`, `script.js`, `styles.css`, `images/` — the static website; the
  home page chat card calls the API (endpoint set in `config.js`).
- `data/` — offline CDC PLACES snapshot + county GeoJSON, so the agent runs
  without network access.
- `eval/` — regression suites (questions, guardrails, LLM router).

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
