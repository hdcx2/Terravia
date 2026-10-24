"""Render the live Terravia site in a real headless browser and report what the
map actually does: console errors, failed network requests, the caption text,
and how many county <path> elements got drawn.

Usage:  python -m eval.browser_check [url]
"""
from __future__ import annotations

import sys

from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "https://wilsonz347.github.io/Terravia/"


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        console, failures = [], []
        page.on("console", lambda m: console.append(f"{m.type}: {m.text}"))
        page.on("pageerror", lambda e: console.append(f"pageerror: {e}"))
        page.on("requestfailed",
                lambda r: failures.append(f"{r.url} :: {r.failure}"))

        print(f"Loading {URL}")
        page.goto(URL, wait_until="load", timeout=60000)
        # Give the map's fetches + render time (Render cold start can be slow).
        page.wait_for_timeout(8000)

        caption = page.text_content("#map-caption") or "(no caption element)"
        paths = page.eval_on_selector_all("#map-svg path.county", "els => els.length")
        options = page.eval_on_selector_all("#map-measure option", "els => els.length")
        svg_box = page.eval_on_selector(
            "#map-svg", "el => { const b = el.getBoundingClientRect(); return [Math.round(b.width), Math.round(b.height)]; }")
        d3_loaded = page.evaluate("typeof window.d3 !== 'undefined'")
        api = page.evaluate("window.TERRAVIA_API")

        print(f"\nAPI base:        {api}")
        print(f"d3 loaded:       {d3_loaded}")
        print(f"selector options:{options}")
        print(f"county paths:    {paths}")
        print(f"svg size (px):   {svg_box}")
        print(f"caption:         {caption!r}")

        print("\n--- console ---")
        for c in console:
            print(" ", c)
        print("--- failed requests ---")
        for f in failures:
            print(" ", f)
        if not failures:
            print("  (none)")

        # Confirm the paths are actually filled (not invisible), and that
        # switching the condition recolors the map.
        first_fill = page.eval_on_selector("#map-svg path.county", "el => el.getAttribute('fill')")
        page.select_option("#map-measure", "BPHIGH")
        page.wait_for_timeout(2500)
        after_fill = page.eval_on_selector("#map-svg path.county", "el => el.getAttribute('fill')")
        after_caption = page.text_content("#map-caption")
        print(f"\nfill (Diabetes):  {first_fill}")
        print(f"fill (BPHIGH):    {after_fill}")
        print(f"recolored:        {first_fill != after_fill}")
        print(f"caption after:    {after_caption!r}")

        page.screenshot(path="/tmp/terravia_map.png", full_page=True)
        print("screenshot -> /tmp/terravia_map.png")

        browser.close()
        # A filled path serializes as rgb(...) or #hex; either is "colored".
        filled = bool(first_fill) and first_fill.strip().lower() not in ("none", "")
        recolored = first_fill != after_fill
        ok = paths and paths >= 14 and filled and recolored
        print(f"\nMAP {'OK' if ok else 'BROKEN'} "
              f"(paths={paths}, filled={filled}, recolor={recolored})")
        return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
