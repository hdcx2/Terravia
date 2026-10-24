"""Massachusetts county geography helpers.

ADJACENCY was computed from the bundled county GeoJSON (counties sharing a
border). It lets us resolve "near X" / "around X" to a county set in code,
rather than relying on the LLM to know MA geography.
"""
from __future__ import annotations

# county -> list of bordering counties (land borders; islands have none).
ADJACENCY: dict[str, list[str]] = {
    "Barnstable": ["Dukes", "Plymouth"],
    "Berkshire": ["Franklin", "Hampden", "Hampshire"],
    "Bristol": ["Norfolk", "Plymouth"],
    "Dukes": ["Barnstable"],
    "Essex": ["Middlesex", "Suffolk"],
    "Franklin": ["Berkshire", "Hampshire", "Worcester"],
    "Hampden": ["Berkshire", "Hampshire", "Worcester"],
    "Hampshire": ["Berkshire", "Franklin", "Hampden", "Worcester"],
    "Middlesex": ["Essex", "Norfolk", "Suffolk", "Worcester"],
    "Nantucket": [],
    "Norfolk": ["Bristol", "Middlesex", "Plymouth", "Suffolk", "Worcester"],
    "Plymouth": ["Barnstable", "Bristol", "Norfolk"],
    "Suffolk": ["Essex", "Middlesex", "Norfolk"],
    "Worcester": ["Franklin", "Hampden", "Hampshire", "Middlesex", "Norfolk"],
}

COUNTIES = tuple(ADJACENCY.keys())

# A few common city -> county hints so "near Springfield" resolves sensibly.
CITY_TO_COUNTY = {
    "springfield": "Hampden", "worcester": "Worcester", "boston": "Suffolk",
    "cambridge": "Middlesex", "lowell": "Middlesex", "pittsfield": "Berkshire",
    "brockton": "Plymouth", "quincy": "Norfolk", "lynn": "Essex",
    "fall river": "Bristol", "new bedford": "Bristol", "framingham": "Middlesex",
}


def canonical_county(name: str) -> str | None:
    """Match a user token to a county (exact, prefix, or known city)."""
    if not name:
        return None
    n = name.strip().lower()
    for c in COUNTIES:
        if c.lower() == n or c.lower().startswith(n) or n.startswith(c.lower()):
            return c
    return CITY_TO_COUNTY.get(n)


def resolve_near(name: str) -> list[str]:
    """Return the county plus its neighbors, for a 'near X' filter.

    Returns an empty list if the name doesn't resolve to an MA county, so the
    caller can fall back to a plain name filter (or report no data)."""
    county = canonical_county(name)
    if county is None:
        return []
    return [county] + ADJACENCY.get(county, [])
