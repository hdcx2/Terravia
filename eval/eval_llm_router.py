"""Verify the two-stage router (LLM tool-call -> rule fallback) and guardrails.

We can't assume a real API key in CI, so we drive `nlu.route` with FAKE
providers that emit the same shape a real tool-caller would. This proves the
routing/validation/fallback logic independently of any network.

A separate live check (run manually with OPENAI_API_KEY set) exercises the real
OpenAIProvider; see `live_check` at the bottom.

Usage:  python -m eval.eval_llm_router
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import nlu                                   # noqa: E402
from src.llm.base import ParseOutcome                 # noqa: E402


class FakeProvider:
    """Returns a scripted ParseOutcome, like a real tool-caller would."""
    name = "fake"

    def __init__(self, outcome: ParseOutcome):
        self._outcome = outcome

    def parse(self, question: str) -> ParseOutcome:
        return self._outcome

    def phrase(self, skeleton: str, allowed_numbers):
        return skeleton


def _case(desc, provider, question, expect_intent, expect_parser):
    sq = nlu.route(question, provider=provider)
    ok = sq.intent == expect_intent and sq.parser == expect_parser
    flag = "PASS" if ok else "FAIL"
    detail = "" if ok else (f"  <- got intent={sq.intent} parser={sq.parser}; "
                            f"want intent={expect_intent} parser={expect_parser}")
    print(f"[{flag}] {desc:52} intent={sq.intent:13} parser={sq.parser}{detail}")
    return ok


def main() -> int:
    results = []

    # 1. Valid LLM tool call used when rules are UNCERTAIN (here: "near" cue).
    #    Rule-first router escalates to the LLM only on uncertainty.
    good = FakeProvider(ParseOutcome(ok=True, arguments={
        "intent": "ranking", "condition": "DIABETES", "sort": "desc", "limit": 10}))
    results.append(_case("valid LLM args used on uncertainty", good,
                         "diabetes near Boston", "ranking", "llm"))

    # 2. Valid LLM access_gap call, escalated via a "vs"/uncertain phrasing.
    gap = FakeProvider(ParseOutcome(ok=True, arguments={
        "intent": "access_gap", "condition": "CASTHMA", "access_measure": "ACCESS2"}))
    results.append(_case("valid LLM access_gap on uncertainty", gap,
                         "asthma vs uninsured around here", "access_gap", "llm"))

    # 3. LLM returns an INVALID condition -> validation fails -> keep rule result.
    #    Uncertain phrasing ("near") escalates, then validation rejects the bad
    #    enum and the rule parse (ranking on diabetes) stands.
    bad_enum = FakeProvider(ParseOutcome(ok=True, arguments={
        "intent": "ranking", "condition": "CANCER"}))
    results.append(_case("invalid enum -> keep rule result", bad_enum,
                         "diabetes near Boston", "ranking", "rule"))

    # 4. LLM returns malformed args (missing required) -> keep rule result.
    missing = FakeProvider(ParseOutcome(ok=True, arguments={"sort": "desc"}))
    results.append(_case("missing intent -> keep rule result", missing,
                         "copd around Pittsfield", "ranking", "rule"))

    # 5. Provider fails entirely -> keep rule result.
    failed = FakeProvider(ParseOutcome(ok=False, error="timeout"))
    results.append(_case("provider error -> keep rule result", failed,
                         "diabetes near Worcester", "ranking", "rule"))

    # 6. Medical guardrail fires BEFORE the provider, even if LLM would answer.
    tries_medical = FakeProvider(ParseOutcome(ok=True, arguments={
        "intent": "ranking", "condition": "DIABETES"}))
    results.append(_case("medical guardrail precedes provider", tries_medical,
                         "do I have diabetes?", "refuse_medical", "guardrail"))

    # 7. LLM itself flags out_of_scope -> honored.
    oos = FakeProvider(ParseOutcome(ok=True, arguments={"intent": "out_of_scope"}))
    results.append(_case("LLM out_of_scope honored", oos,
                         "weather in Boston", "out_of_scope", "llm"))

    passed = sum(results)
    print(f"\n{passed}/{len(results)} passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
