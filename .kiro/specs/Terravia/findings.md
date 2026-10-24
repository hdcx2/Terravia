# Data Exploration Findings — CDC PLACES MA (read at kickoff)

Based on live queries against the confirmed dataset. These numbers drive several
design decisions; read before building the agent or the map.

## Dataset
- **`swc5-untb`** — CDC PLACES County, 2025 release, `data.cdc.gov`.
- **84 rows** = 6 measures × 14 MA counties. **Data year 2023** for all six.
- **Zero missing/suppressed values.** No suppression handling needed.
- Offline copy saved at `data/snapshot_places_ma.csv` (normalized schema).

## Value summary (crude prevalence %, 2023)

| measure | min | max | spread | mean | top county |
|---|---|---|---|---|---|
| DIABETES | 8.2 | 12.1 | 3.9 | 10.0 | Hampden (12.1%) |
| CASTHMA | 10.7 | 12.7 | **2.0** | 11.7 | Hampden (12.7%) |
| BPHIGH | 26.7 | 38.2 | 11.5 | 32.3 | Barnstable (38.2%) |
| COPD | 4.6 | 7.7 | 3.1 | 6.3 | Hampden (7.7%) |
| ACCESS2 (uninsured 18–64) | 3.6 | 8.1 | 4.5 | 5.0 | Hampden (8.1%) |
| CHECKUP | 78.5 | 85.3 | 6.8 | 81.5 | Barnstable (85.3%) |

Population spans **Nantucket 14,444 → Middlesex 1,623,952**. A high *rate* in a
tiny county is a different recruiting target than a high rate in a large one —
show population alongside prevalence.

## Finding 1 — Hampden County is the headline
Hampden (Springfield area) is **#1 for diabetes, asthma, COPD, and uninsured**,
and is the only county in the high-burden + low-checkup + high-uninsured tier for
**all four conditions**. The access-gap differentiator points at a real,
consistent place rather than a contrived overlay. Use it as the demo centerpiece.

## Finding 2 — The access gap resolves sharply
Triple-overlap (high burden AND fewest checkups AND most uninsured), tercile rule
(~5 of 14 counties per tier):

| condition | high + low-checkup | high + high-uninsured | triple |
|---|---|---|---|
| DIABETES | Hampden | Bristol, Hampden | **Hampden** |
| CASTHMA | Hampden, Hampshire | Bristol, Hampden, Worcester | **Hampden** |
| BPHIGH | Hampden | Hampden | **Hampden** |
| COPD | Hampden | Bristol, Hampden | **Hampden** |

## Finding 3 — Rankings are NOT statistically distinct (the key caveat)
Confidence intervals of the #1 county overlap the #2 county's:

| measure | #1 | #2 | overlap? |
|---|---|---|---|
| DIABETES | Hampden 12.1% [10.5–13.8] | Berkshire 10.9% [9.2–12.8] | **overlaps** |
| BPHIGH | Barnstable 38.2% [34.2–42.2] | Franklin 36.3% [32.2–40.4] | **overlaps** |
| ACCESS2 | Hampden 8.1% [6.3–9.9] | Suffolk 6.6% [5.1–8.4] | **overlaps** |

Worse for **asthma**: average CI width (2.7 pts) is **wider than the entire
14-county spread (2.0 pts)**.

**Implication (protects against the toughest judge question):**
- Chatbot says "among the highest," not "the highest."
- Top-10 table shows Low/High CI columns so overlap is visible.
- Access-gap view shows the actual values so tiers read as honest.
- Never claim one county is significantly higher than its neighbor.

→ Hardened into requirements R3.6 and R5.10.

## Finding 4 — Narrow spreads shape the map
Asthma spans only 2.0 pts and COPD 3.1 across all counties, so a naive choropleth
looks nearly uniform. Use a **tight color-scale domain (data min→max, not 0→100)**
and render values on the map. Captured in design Open Question 5.
