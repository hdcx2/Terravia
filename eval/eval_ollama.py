"""Run the sample questions through a REAL local Ollama model and report the
pass rate. Exercises the full two-stage router with Ollama as stage 1 and the
rule-based parser as the fallback.

Prereqs: `ollama serve` running and the model pulled. Configure via env:
  HOTSPOT_LLM_MODEL (default qwen2.5:7b), HOTSPOT_OLLAMA_MODE (tool|json).

Usage:  python -m eval.eval_ollama
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("HOTSPOT_LLM_PROVIDER", "ollama")
os.environ.setdefault("HOTSPOT_LLM_MODEL", "qwen2.5:7b")
os.environ.setdefault("HOTSPOT_LLM_TIMEOUT", "90")

from src import data_loader, nlu, answer as A           # noqa: E402
from src.llm import get_provider, provider_health        # noqa: E402
from eval.eval_questions import CASES                     # noqa: E402


def main() -> int:
    health = provider_health()
    print(f"Provider health: ok={health.ok} | {health.message}")
    if not health.ok:
        print("Cannot run live Ollama eval; fix the above and retry.")
        return 2

    mode = os.environ.get("HOTSPOT_OLLAMA_MODE", "tool")
    model = os.environ["HOTSPOT_LLM_MODEL"]
    print(f"Model={model} mode={mode}\n")

    df, _ = data_loader.load()
    provider = get_provider()

    from collections import Counter
    by_path = Counter()              # path -> count
    pass_by_path = Counter()         # path -> passes
    misses = []                      # (q, expected, got, path, grounded)
    passed = 0
    t0 = time.time()
    for q, expected in CASES:
        sq = nlu.route(q, provider=provider)
        ans = A.answer(df, sq)
        by_path[sq.parser] += 1
        ok = sq.intent == expected and ans.grounded
        passed += ok
        pass_by_path[sq.parser] += ok
        if not ok:
            misses.append((q, expected, sq.intent, sq.parser, ans.grounded))
        flag = "PASS" if ok else "FAIL"
        label = q if q else "(empty)"
        note = "" if ok else f"  <- got={sq.intent} want={expected} grounded={ans.grounded}"
        print(f"[{flag}] {label[:52]:52} intent={sq.intent:13} "
              f"parsed_by={sq.parser:9}{note}")

    total = len(CASES)
    dt = time.time() - t0
    print(f"\n{passed}/{total} passed · {dt:.0f}s total ({dt/total:.1f}s/question)")

    print("\nBy path:")
    for path in sorted(by_path):
        print(f"  {path:9} {pass_by_path[path]}/{by_path[path]} passed")

    print("\nMisses classified:")
    if not misses:
        print("  none")
    for q, expected, got, path, grounded in misses:
        # wrong-tool-plausible: a valid intent was produced and the answer was
        # still grounded. failed-parse-with-fallback: it fell to the rules.
        if grounded and got in ("ranking", "lookup", "access_gap",
                                "out_of_scope", "refuse_medical"):
            kind = ("wrong-tool, plausible answer" if path == "llm"
                    else "rule disagreement, plausible answer")
        else:
            kind = "failed parse / ungrounded"
        print(f"  [{kind}] via={path}: \"{q}\" (got {got}, want {expected})")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
