# Terravia — How We Built It (Reference Doc)

A plain-language explanation of what Terravia is, the decisions we made, how the
AI parts work, how we kept them honest, and the problems we hit along the way.
Written so anyone on the team can use it as a reference or talking points.

---

## 1. The problem we set out to solve

Clinicians, researchers, and public health teams have limited time and budget
for outreach, screening, and clinical-trial recruitment. The data showing *where*
chronic conditions cluster already exists (the CDC collects it), but it's spread
across portals in technical formats. So teams often pick locations by habit or
guesswork instead of evidence.

**Terravia answers one question clearly:** *where in Massachusetts is a given
chronic condition most common, and where is the need high but access thin?*

**Who it's for:**
- Researchers choosing trial recruitment sites
- Clinics deciding where to hold screening events
- Public health teams targeting outreach

---

## 2. What we built (the product in one paragraph)

A website with two linked pieces: an **interactive county map** of Massachusetts
shaded by a chosen condition, and a **chatbot** you can ask in plain English
("Where is diabetes highest?"). Both read from the same public dataset, and
every answer shows its **source, data year, and a note that the numbers are
estimates**. There's also an **"access gap" view** that flags counties where a
condition is common *and* access (insurance or checkups) is weak.

Live site: the static pages are on GitHub Pages; the chatbot's brain runs as a
small API on Render.

---

## 3. The data (and why we trust it)

- **Source:** CDC PLACES, County data, 2025 release — public, no login, no patient data.
- **Scope:** 14 Massachusetts counties, data year **2023**, six measures:
  diabetes, asthma, high blood pressure, COPD (the conditions) + uninsured
  (adults 18–64) and routine checkup (the access measures).
- **Size:** 84 rows (6 measures × 14 counties). Small enough that we cache it
  locally, so the app works **offline during a demo** and loads instantly.
- **Honesty built in:** these are **model-based estimates**, not counts of
  diagnosed patients. We say so on every number. We also noticed the counties'
  confidence intervals **overlap** — so the app says "among the highest," never
  "definitively the highest," and shows the ± range.

---

## 4. How the chatbot actually works (high level)

The key idea: **the AI never makes up a number.** It only decides *what to look
up*; the actual numbers always come from the real dataset.

A question flows through three stages:

```
Your question
     │
     ▼
1. ROUTER   — figures out what you're asking (a "structured query")
     │        e.g. {intent: ranking, condition: DIABETES, sort: desc}
     ▼
2. DATA     — runs that query over the 84-row dataset (plain table lookup)
     │        returns the actual rows + numbers
     ▼
3. ANSWER   — writes a sentence using ONLY those returned numbers,
              then adds the source + year + "estimate" note
```

Because the numbers are filled in from the data at the last step, the chatbot
**can't hallucinate a statistic** even if the language model misunderstands the
question. This is the single most important design decision in the project.

### The router is "rule-first, AI-second"

We don't send every question to a language model. We go in this order:

1. **Guardrails first** (safety): if the question is personal medical advice, an
   unsupported topic (e.g. cancer), a bad year, or a bare county name, we handle
   it immediately with a fixed, correct response — no AI involved.
2. **Rules second**: a fast keyword matcher handles the common, clear questions
   ("where is diabetes highest" → ranking). Deterministic and instant.
3. **The language model only when the rules are unsure** — e.g. fuzzy phrasings
   like "near Worcester" or "asthma vs checkups." Even then, the model's output
   is **validated against a fixed list** of allowed conditions/intents before we
   trust it. If it returns something invalid, we fall back to the rule result.

This means the app works even with **no AI at all** (the rules alone answer most
things), which is why the demo can't break.

---

## 5. How we handled the language model (and made it swappable)

We treated the LLM as a **replaceable part**, not the core. There's one small
interface, and three interchangeable backends:

- **`null`** — no LLM; rules only. This is the **default**, so the demo never
  depends on a key or internet.
- **`ollama`** — a local model (we tested `qwen2.5:7b`) running on your own
  machine, free, private, no API key sent anywhere.
- **`openai`** — a hosted model, if a key is provided.

Switching is a single config/environment change; the data and answer logic don't
change at all. The LLM only ever does two narrow jobs: **turn a question into a
structured query**, and (optionally) **reword the final sentence** — never
produce a number.

### How we "calibrated" / kept it honest

We didn't tune the model's weights — we constrained and tested it:

1. **Constrained output.** The model can only choose from a fixed menu
   (enumerated intents and condition codes). Anything off-menu is rejected.
2. **A grounding check.** After the answer is written, code scans it and
   confirms **every number in the text matches a number from the query
   results** (within a small tolerance). If a number appears that isn't in the
   data, the answer is withheld. This is the safety net behind the whole thing.
3. **Automated test suites** we ran repeatedly as we changed things:
   - `eval_questions` (20 sample questions) — correct intent + grounded
   - `eval_guardrails` (38 cases) — medical refusals, unsupported topics/years,
     county profiles, with multiple paraphrases each
   - `eval_llm_router` — proves the rule→LLM fallback behaves
   - `eval_ollama` / `eval_heldout` — ran real local-model answers
   - `browser_check` — a real headless browser confirms the map renders
4. **Held-out testing.** We fed the system *new* questions it had never been
   tuned on, found real gaps (e.g. "my dad has diabetes, where should he get
   care?" wasn't being refused), fixed them **by category** (not by memorizing
   the exact phrase), then re-ran everything.

### Calibration results (what we measured)

- Sample questions: **20/20** correct, every answer grounded.
- Guardrails: **38/38** across paraphrases; zero medical-advice leaks.
- Fuzz test: **500 random/adversarial inputs → 0 crashes, 0 made-up numbers.**
- Two local models (qwen2.5 and qwen2.5-coder) both passed; the score barely
  moved when we swapped models, which proved the *architecture* (not the model)
  was doing the heavy lifting.

---

## 6. Key design choices (and the reasoning)

| Choice | Why |
|---|---|
| **County level, Massachusetts only** | Small, clean, complete data; finishes in a hackathon window; a sharp focused story beats a shallow national one. |
| **Numbers come from data, not the LLM** | Makes hallucinated statistics structurally impossible — essential for a health tool. |
| **Rule-first routing** | Fast, deterministic, works offline; the LLM is a helper for hard phrasings, not a dependency. |
| **Swappable LLM with a `null` default** | The demo can't break on a missing key or dead network; privacy option via local Ollama. |
| **Show confidence intervals + hedged wording** | The data genuinely can't distinguish the top counties; saying so builds trust and survives tough questions. |
| **Offline data snapshot** | Demo works with no Wi-Fi; instant load. |
| **D3 SVG map (no map tiles)** | No API key, no watermark, no external tile service — just the county shapes we color ourselves. |
| **Static site + small API** | Cheap/free to host, simple to reason about, easy to demo. |

---

## 7. Challenges we faced (and how we solved them)

- **"Only diabetes?" / legend on top of the dropdown.** Leftover CSS from a
  deleted second map page was absolutely-positioning the legend over the
  selector. Fix: removed the orphaned styles. Then browser **caching** kept
  showing the old version, so we added `?v=2` to force fresh files.
- **Two different maps.** A teammate's separate map page used a tile service that
  stamped **"API KEY REQUIRED"** watermarks. We removed it and kept our own
  watermark-free D3 map.
- **The LLM choosing the wrong tool on edge cases.** On held-out questions the
  model sometimes answered a personal-medical or unsupported-topic question with
  data. We added **guardrails that run before the model** and a rule that the
  model can never return a measure the user didn't name.
- **Rankings aren't statistically distinct.** The counties' confidence intervals
  overlap. Rather than overstate, we made the app hedge and show the ± range.
- **GitHub Pages can't run Python.** Pages is static-only, so the chatbot's API
  had to live elsewhere. We deployed it separately (Render) and pointed the site
  at it, with CORS locked to our site's address.
- **Browser cache hiding fixes.** Repeatedly looked "broken" when it was fixed —
  solved with cache-busting version strings and by verifying in a fresh headless
  browser instead of trusting a possibly-cached view.

---

## 8. Why we used Kiro (the AI IDE)

Kiro is an agentic AI development environment — it doesn't just autocomplete, it
plans, writes, runs, tests, and verifies work across the whole project. For a
time-boxed build with a small team, that mattered in concrete ways:

- **Spec-first.** We started by having Kiro produce a structured spec
  (requirements in testable form, a design doc, and role-tagged tasks) so the
  team could work in parallel from a shared plan instead of guessing.
- **It verified its own work.** Kiro ran the data queries against the live CDC
  API to confirm the dataset before designing around it, ran the test suites
  after every change, and even drove a **real headless browser (Playwright)** to
  prove the map rendered — catching issues a human glance would miss.
- **Grounded, honest reporting.** When something couldn't be confirmed (e.g. a
  hosted-LLM happy path without a key, or a cached browser view), it said so
  rather than claiming success — which saved us from false confidence.
- **Fast, safe iteration.** Deleting the Streamlit app, adding the API, wiring
  the map, fixing CSS, deploying — each step was made, tested, and pushed with
  the reasoning explained, so we always knew the state of the project.
- **It caught its own mistakes.** When it made a wrong path or a flaky test
  assertion, it diagnosed and corrected rather than papering over it.

In short: Kiro let a small team move like a larger one, with testing and
verification baked into every step instead of bolted on at the end.

---

## 9. One-line summary

**Terravia turns scattered public health data into a clear, map-and-chat answer
to "where is the need greatest?" — built so the AI can guide the question but
never invent the numbers, and so the whole thing keeps working even with no
internet and no API key.**
