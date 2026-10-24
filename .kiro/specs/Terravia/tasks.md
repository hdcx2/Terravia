# Tasks — Condition Hotspot Finder

Ordered for a 6–8 hour build by 4 people working in parallel. Tags:
**[DS]** data scientist · **[FE]** BME 1 (front end) · **[DOM]** BME 2 (domain
validation) · **[BIZ]** business student. Checkpoints keep the four tracks in
sync. Each task references the requirement it satisfies.

> The critical path is DS 1–3 (data + query engine). FE, DOM, and BIZ can all
> work against the schema and sample data before the live fetch lands.

---

## Phase 0 — Kickoff & contracts (first 30 min, whole team)

- [ ] 0.1 **[DS]** Record the confirmed source in `config.py`: dataset
  `swc5-untb` (PLACES County 2025, data year 2023), 6 `measureid`s, column
  mapping. Dataset + measures already verified live — no further confirmation
  needed. _(Design: Confirmed data facts; R1.4)_
- [ ] 0.2 **[DS]** Lock the schema and `StructuredQuery` contract with the team.
  The bundled snapshot `data/snapshot_places_ma.csv` (84 rows, normalized schema)
  and `data/snapshot_meta.json` already exist — use them as the dev fixture so
  FE/DOM/BIZ are unblocked immediately and the app works offline from minute one.
  Read `findings.md` together. _(Design: schema, StructuredQuery; findings.md)_
- [ ] 0.3 **[FE]** Scaffold `app.py` Streamlit skeleton + one-command run; commit
  `README` run steps. _(R7.3)_
- [ ] 0.4 **[DOM]** Confirm the 4 conditions + 2 access measure IDs and the
  crude-vs-age-adjusted choice; write the modeled-estimate caveat text. _(R6; Open Q 3)_
- [ ] 0.5 **[BIZ]** Draft the 3 user personas + demo narrative and the 3 example
  questions to showcase. _(Requirements overview; R5)_

**Checkpoint A (~1.5h):** schema + fixture + skeleton merged.

---

## Phase 1 — Data & engine (DS critical path) + parallel UI shell

- [ ] 1.1 **[DS]** `data_loader.py`: Socrata fetch filtered to MA + 6 measures,
  normalize to tidy schema, cache to parquet, provenance record. _(R1.1, R1.4)_
- [ ] 1.2 **[DS]** Cache-first load + bundled snapshot fallback + "using cached
  data" notice. _(R1.2, R1.3, R1.5, R7.4)_
- [ ] 1.3 **[DS]** `query.py`: filter/sort/limit, `rank`, `tercile`, and a
  `ci_overlaps_next` flag per result row (top vs next CI). Single source of all
  numbers. Unit-tested against the snapshot. _(R3.1, R3.5, R5.2, R5.10)_
- [ ] 1.4 **[FE]** Condition selector + top-10 table bound to `query.py`, with
  Low/High CI columns shown so overlapping estimates are visible (works on
  snapshot first). _(R3.1–R3.3, R3.5)_
- [ ] 1.5 **[DOM]** Sanity-check prevalence values against the `findings.md`
  baseline (e.g. DIABETES 8–12%, Hampden top); confirm hedged-ranking + CI
  requirements (R3.5, R5.10) are reflected in table and chatbot wording.
  _(R6.2, R6.3, R3.5, R5.10; findings.md)_
- [ ] 1.6 **[BIZ]** Write always-visible source/year/modeled-estimate footer copy
  and the "what this does / who it's for" intro panel. _(R6.1, R6.2)_

**Checkpoint B (~3.5h):** live MA data flows into a working table. If fetch is
flaky, snapshot path must already pass (R1.3).

---

## Phase 2 — Map, access gap, chatbot

- [ ] 2.1 **[FE]** Choropleth map from bundled MA county GeoJSON joined on FIPS,
  colored by selected condition, legend, hover tooltip (name/value/year/source),
  "no data" styling. _(R2.1–R2.5)_
- [ ] 2.2 **[DS]** `gap.py`: tercile high-burden + low-access flagging; empty-set
  message; expose the rule text to the UI. _(R4.1–R4.4)_
- [ ] 2.3 **[FE]** Access-gap view (condition + access pickers) listing flagged
  areas with both values and the stated rule. _(R4.1–R4.3)_
- [ ] 2.4 **[DS]** `nlu.py` `RuleParser` (keyword→measure, area match, intent
  cues) → `StructuredQuery`; this is the shipped fallback. _(R5.1, R5.8)_
- [ ] 2.5 **[DS]** `answer.py`: rows → grounded text with source + data year +
  modeled-estimate note; hedged ranking ("among the highest") + CI-overlap note
  from the `query.py` flag; zero-row = "no data" (never invents). _(R5.2–R5.4, R5.10)_
- [ ] 2.6 **[DOM]** Medical-advice refusal + out-of-scope responses; review
  refusal wording for clinical appropriateness. _(R5.5, R5.6)_
- [ ] 2.7 **[FE]** Chatbot panel wired to `nlu → query → answer`. _(R5.1–R5.4)_
- [ ] 2.8 **[BIZ]** Run the 15–20 sample questions; log failures for DS/DOM;
  curate the 3 demo questions. _(Design: testing; R5)_

**Checkpoint C (~5.5h):** all 4 views work end-to-end on local data with the
rule-based chatbot. **Feature freeze here if behind** — everything below is
optional polish.

---

## Phase 3 — Polish & swappable LLM (only if ahead)

- [ ] 3.1 **[DS]** `llm/base.py` interface + one hosted provider + `null`
  (rule-based); config switch; auto-fallback on missing key/error. _(R5.7–R5.9, R5.8)_
- [ ] 3.2 **[FE]** CSV download for the top-10 table. _(R3.5)_
- [ ] 3.3 **[DOM]** Optional: surface population + CI bounds in tooltips (already
  in the dataset, no extra source needed). _(R3.2, R6)_
- [ ] 3.4 **[BIZ]** Final demo script, slide, and value framing per persona.

---

## Phase 4 — Demo hardening (last 30 min, whole team)

- [ ] 4.1 **[DS]** Verify offline run: disable network → snapshot + rule parser
  pass the 3 demo questions. _(R1.5, R7.4)_
- [ ] 4.2 **[FE]** Reset app to clean state; confirm one-command start. _(R7.3)_
- [ ] 4.3 **[DOM]** Final pass that every surfaced number shows source/year/
  modeled note and no medical advice leaks. _(R6, R5.5)_
- [ ] 4.4 **[BIZ]** Dry-run the full demo once, timed.

---

## Parallelization summary

| Time | DS | FE | DOM | BIZ |
|---|---|---|---|---|
| 0–1.5h | dataset IDs, schema, loader start | app skeleton | measure/value-type confirm | personas, demo Qs |
| 1.5–3.5h | loader, query engine, snapshot | table on fixture→live | value sanity-check | footer + intro copy |
| 3.5–5.5h | gap, nlu, answer | map, gap view, chat panel | refusal/scope wording | run sample Qs |
| 5.5–7h | swappable LLM (opt) | CSV download (opt) | tooltip pop/CI (opt) | demo script |
| last 30m | offline verify | clean start | provenance/safety audit | timed dry-run |
