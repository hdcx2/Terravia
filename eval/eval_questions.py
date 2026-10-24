"""Run the sample questions end-to-end and print pass/fail.

For each question we assert the EXPECTED INTENT, and for answerable ones that the
grounding check passed (no invented numbers). Uses the offline snapshot, so this
runs with no network and no LLM key (NullProvider -> rule parser).

Usage:  python -m eval.eval_questions
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import data_loader, nlu, answer as A  # noqa: E402

# (question, expected_intent)
CASES = [
    ("Where is diabetes prevalence highest in Massachusetts?", "ranking"),
    ("Top 10 counties for high blood pressure.", "ranking"),
    ("Which areas have the most asthma?", "ranking"),
    ("Show COPD rates ranked.", "ranking"),
    ("What's the diabetes rate in Worcester?", "lookup"),
    ("Lowest asthma areas in MA.", "ranking"),
    ("Where should we recruit for a hypertension study near Worcester?", "ranking"),  # "near" = area set -> ranking
    ("List the highest COPD areas near Berkshire.", "ranking"),  # list cue -> ranking, area-filtered
    ("Which towns have high asthma rates and low health insurance coverage?", "access_gap"),
    ("Where is diabetes high but routine checkups low?", "access_gap"),
    ("Find high blood pressure areas with poor insurance coverage.", "access_gap"),
    ("Access gaps for COPD and checkup.", "access_gap"),
    ("Do I have diabetes?", "refuse_medical"),
    ("What should I take for high blood pressure?", "refuse_medical"),
    ("Where is cancer highest in MA?", "list_supported"),   # unsupported condition
    ("Show cholesterol rates in MA.", "list_supported"),    # unsupported condition
    ("What's the weather in Boston?", "out_of_scope"),
    ("Diabetes in Narnia.", "lookup"),          # valid measure, unknown area -> no-data answer
    ("Tell me about diabetes.", "ranking"),     # vague -> default MA ranking
    ("Highest rates of diabetes and asthma.", "ranking"),  # multi-condition
    ("Top counties for COPD and high blood pressure.", "ranking"),  # multi-condition
    ("", "out_of_scope"),
]

# Questions that name multiple conditions -> the answer must address ALL of them.
MULTI = [
    ("Highest rates of diabetes and asthma.", ["Diabetes", "Current asthma"]),
    ("Top counties for COPD and high blood pressure.", ["COPD", "High blood pressure"]),
]


def main() -> int:
    df, prov = data_loader.load()
    print(f"Loaded {len(df)} rows from {prov.origin} "
          f"({prov.source} {prov.release_year}, data year {prov.data_year})\n")

    passed = 0
    for q, expected in CASES:
        sq = nlu.route(q)
        ans = A.answer(df, sq)
        intent_ok = sq.intent == expected
        grounded_ok = ans.grounded
        ok = intent_ok and grounded_ok
        passed += ok
        flag = "PASS" if ok else "FAIL"
        detail = "" if ok else (
            f"  <- intent got={sq.intent} want={expected} grounded={grounded_ok}")
        label = q if q else "(empty)"
        print(f"[{flag}] {label[:60]:60} intent={sq.intent:13} "
              f"grounded={grounded_ok}{detail}")

    total = len(CASES)
    print(f"\n{passed}/{total} passed")

    # Multi-condition: the answer must mention every named condition's label.
    multi_pass = 0
    print("\n-- multi-condition coverage --")
    for q, labels in MULTI:
        ans = A.answer(df, nlu.route(q))
        covered = all(lbl in ans.text for lbl in labels)
        multi_pass += covered
        print(f"[{'PASS' if covered else 'FAIL'}] {q[:50]:50} covers {labels}")
    ok_multi = multi_pass == len(MULTI)
    print(f"{multi_pass}/{len(MULTI)} multi-condition answers covered all conditions")

    return 0 if (passed == total and ok_multi) else 1


if __name__ == "__main__":
    raise SystemExit(main())
