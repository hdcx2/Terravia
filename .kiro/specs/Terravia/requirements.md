# Requirements — Condition Hotspot Finder

## Overview

A web app (map + ranked table + grounded chatbot) that shows where chronic
conditions cluster in Massachusetts, using public CDC PLACES data. Built for a
6–8 hour hackathon by a team of 4. Scope is deliberately small: Massachusetts
only, 4 conditions + 2 access measures, 3 MVP features + 1 differentiator.

**Primary users**
- R — Researcher choosing clinical trial recruitment sites
- C — Clinic deciding where to hold screening events
- P — Public health / health system team targeting outreach

**Conditions (measure IDs in PLACES):** diabetes (`DIABETES`), current asthma
(`CASTHMA`), high blood pressure (`BPHIGH`), COPD (`COPD`).
**Access/prevention measures:** health insurance coverage gap — adults 18–64 with
no insurance (`ACCESS2`), routine checkup in past year (`CHECKUP`).

**Confirmed data source (verified live against the API):**
- Dataset: CDC PLACES **County** data, **2025 release**, Socrata id
  **`swc5-untb`** on `data.cdc.gov`.
- Geography: **county only**, all **14 Massachusetts counties**, no missing/
  suppressed values for the six measures.
- Data year: **2023** for all six measures. (Town/tract levels are a different
  PLACES dataset and are out of scope for this build.)
- Filter by stable **`measureid`**, not the long `measure` text.
- The "card" view's columns map directly to raw PLACES columns:
  `County→locationname`, `Measure→measure`, `Percent→data_value`,
  `Low→low_confidence_limit`, `High→high_confidence_limit`,
  `Population→totalpopulation`.

> Values are **model-based estimates**, not counts of diagnosed patients. Every
> surfaced number must carry source, data year, and this caveat.

---

## Glossary

- **Burden / prevalence** — PLACES crude or age-adjusted percentage for a
  condition in a geography (we use crude `data_value`, documented in design).
- **Geography** — a Massachusetts area at the chosen level (county, place,
  census tract, or ZCTA). Final level chosen in design; see Open Questions.
- **Access gap** — an area that is simultaneously high on a condition and low on
  an access/prevention measure (high need + low access).
- **Grounded answer** — a chatbot reply derived only from rows returned by a
  query over the loaded dataset, never from model memory.

---

## Requirements

### R1 — Load and cache Massachusetts PLACES data

**User story:** As the team, we want MA PLACES data loaded once and cached
locally, so the app runs fast and works offline during the demo.

**Acceptance criteria (EARS)**
1. WHEN the app starts and no local cache exists, THE SYSTEM SHALL download the
   configured MA subset (4 conditions + 2 access measures, chosen geo level)
   from the CDC PLACES source and write it to a local cache file.
2. WHEN a local cache exists, THE SYSTEM SHALL load from cache and SHALL NOT make
   a network request.
3. IF the download fails or times out, THEN THE SYSTEM SHALL fall back to a
   bundled snapshot file committed in the repo and SHALL display a notice that
   cached/bundled data is in use.
4. THE SYSTEM SHALL record, for the loaded dataset, the source name, dataset
   identifier/URL, release year, and BRFSS data year(s), and SHALL expose these
   for display.
5. WHERE the network is unavailable, THE SYSTEM SHALL run end to end using only
   local files.

### R2 — Interactive map colored by a selected condition (MVP 1)

**User story:** As user P, I want a map of MA shaded by a condition I pick, so I
can see spatial clustering at a glance.

**Acceptance criteria (EARS)**
1. THE SYSTEM SHALL render a map of Massachusetts geographies at the chosen geo
   level.
2. WHEN the user selects a condition, THE SYSTEM SHALL color each geography by
   that condition's prevalence using a graduated color scale with a legend.
3. WHEN the user hovers or clicks a geography, THE SYSTEM SHALL show its name,
   the value, the data year, and the source.
4. IF a geography has a missing/suppressed value, THEN THE SYSTEM SHALL render it
   in a distinct "no data" style and label it as such.
5. THE SYSTEM SHALL update the map within a few seconds of a selection change.

### R3 — Ranked top-10 hotspots table (MVP 2)

**User story:** As user C, I want a ranked list of the highest-burden areas for a
condition, so I can pick screening-event locations quickly.

**Acceptance criteria (EARS)**
1. WHEN a condition is selected, THE SYSTEM SHALL display a table of the top 10
   geographies by prevalence, descending.
2. THE SYSTEM SHALL show, per row, the rank, geography name, prevalence value,
   data year, and (where available) population.
3. THE SYSTEM SHALL keep the table and the map on the same selected condition.
4. WHERE fewer than 10 geographies have data, THE SYSTEM SHALL show all available
   rows and note the reduced count.
5. THE SYSTEM SHALL display the 95% confidence interval (low–high) for each row's
   value, so overlapping estimates are visible and the ranking is not read as
   exact. *(See findings: #1 and #2 counties' CIs overlap for most measures.)*
6. THE SYSTEM SHALL let the user copy or download the table as CSV. *(Should —
   cut first if time-constrained; see tasks.)*

### R4 — Access-gap view (differentiator)

**User story:** As user P, I want to see areas that are both high-burden and
low-access, so I can target outreach where need is greatest and care is thinnest.

**Acceptance criteria (EARS)**
1. WHEN the user enables the access-gap view and picks one condition and one
   access measure, THE SYSTEM SHALL flag geographies that are in the high tier
   for the condition AND the low-access tier for the measure.
2. THE SYSTEM SHALL state the exact rule used to define "high" and "low" (e.g.,
   top/bottom tercile or a stated percentile), visible in the UI.
3. THE SYSTEM SHALL list the flagged areas with both values shown.
4. WHERE no area meets both conditions, THE SYSTEM SHALL say so explicitly rather
   than showing an empty view.

### R5 — Grounded, data-citing chatbot (MVP 3)

**User story:** As user R, I want to ask in plain English where to recruit, and
get an answer computed from the data with its source, so I can trust and cite it.

**Acceptance criteria (EARS)**
1. WHEN the user submits a question, THE SYSTEM SHALL translate it into a
   structured query (condition, geography/area filter, sort, limit, optional
   access filter) BEFORE producing any answer.
2. THE SYSTEM SHALL run that structured query against the loaded dataset and
   SHALL compose its answer only from the returned rows.
3. THE SYSTEM SHALL NOT answer chronic-condition prevalence questions from model
   memory; IF a query returns no rows, THEN THE SYSTEM SHALL say it has no data
   for that request rather than estimating.
4. THE SYSTEM SHALL include in every data answer the source name, the data year,
   and a note that values are modeled estimates.
5. IF the question requests individual medical advice, diagnosis, or treatment,
   THEN THE SYSTEM SHALL decline and redirect to a clinician, without providing
   such advice.
6. IF the question references a condition, geography, or metric outside the
   supported scope, THEN THE SYSTEM SHALL say what IS supported (the 4 conditions,
   2 access measures, MA at the chosen geo level).
7. WHERE an external LLM is configured, THE SYSTEM SHALL use it only to parse the
   question into the structured query and to phrase the summary of returned rows.
8. IF no LLM provider is configured or the provider call fails, THEN THE SYSTEM
   SHALL fall back to a rule-based parser so the chatbot still answers.
9. THE SYSTEM SHALL support swapping the LLM provider via configuration without
   code changes to the query or data layers.
10. WHEN the chatbot reports a ranking, THE SYSTEM SHALL use hedged language
    (e.g. "among the highest") rather than asserting one area is definitively the
    highest, AND WHERE the top result's confidence interval overlaps the next
    result's, THE SYSTEM SHALL be able to note that the difference is within the
    margin of uncertainty. *(Values are modeled estimates with overlapping CIs;
    see findings #3.)*

### R6 — Transparent sourcing and modeled-estimate disclosure

**User story:** As any user, I want every number to carry its provenance, so I
can judge and cite it responsibly.

**Acceptance criteria (EARS)**
1. THE SYSTEM SHALL display the data source, dataset release year, and BRFSS data
   year somewhere always visible (e.g., footer or sidebar).
2. THE SYSTEM SHALL label condition and access values as model-based estimates
   wherever they are shown as a primary result (map tooltip, table, chat answer).
3. THE SYSTEM SHALL NOT present estimates as diagnosed case counts.

### R7 — Scope, privacy, and demo-readiness constraints

**User story:** As the team, we want the app to stay in scope and demo reliably,
so we finish on time and present cleanly.

**Acceptance criteria (EARS)**
1. THE SYSTEM SHALL use only public data and SHALL NOT handle patient-level data
   or require authentication.
2. THE SYSTEM SHALL be limited to Massachusetts, the 4 named conditions, and the
   2 named access measures.
3. THE SYSTEM SHALL run as a single Streamlit app startable with one command.
4. WHERE any external dependency (network, LLM) is unavailable at demo time, THE
   SYSTEM SHALL still demonstrate map, table, access-gap, and chatbot using local
   data and the rule-based fallback.
