"""Question -> StructuredQuery, via a two-stage router.

Router order (rule-first, LLM as a fallback for hard cases):
  0. Guardrails: blank input -> out_of_scope; medical cues -> refuse_medical.
     These run FIRST and never reach the rule parser or the LLM.
  1. Rule parser: deterministic keyword/area parse. Fast and offline.
  2. LLM (if configured): only invoked when the rules are UNCERTAIN, i.e. they
     returned out_of_scope OR left meaningful words unparsed (near, around, vs,
     compared to). The LLM output is enum-validated; if it fails validation we
     keep the rule result.

"near X" is resolved in code via geo.ADJACENCY, so geography never depends on
the LLM knowing MA counties.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from . import config, geo, knowledge
from .llm import LLMProvider, get_provider

# Intents
RANKING, LOOKUP, ACCESS_GAP, REFUSE_MEDICAL, OUT_OF_SCOPE = (
    "ranking", "lookup", "access_gap", "refuse_medical", "out_of_scope")
COUNTY_PROFILE = "county_profile"   # a county named with no measure -> all six
LIST_SUPPORTED = "list_supported"   # unsupported condition -> show capabilities
UNSUPPORTED_YEAR = "unsupported_year"  # a year other than the data year
DATASET_INFO = "dataset_info"       # questions ABOUT the data (counties, years, coverage)
EXPLAIN = "explain"                 # conceptual question -> RAG over our own docs
VALID_INTENTS = {RANKING, LOOKUP, ACCESS_GAP, REFUSE_MEDICAL, OUT_OF_SCOPE,
                 COUNTY_PROFILE, LIST_SUPPORTED, UNSUPPORTED_YEAR, DATASET_INFO,
                 EXPLAIN}


@dataclass
class StructuredQuery:
    intent: str
    condition: str | None = None
    conditions: list[str] | None = None  # >1 condition named -> answer each
    access_measure: str | None = None
    area_filter: str | None = None
    area_in: list[str] | None = None   # resolved county set for "near X"
    snippet_ids: list[str] | None = None  # retrieved KB snippets for EXPLAIN
    sort: str = "desc"
    limit: int = 10
    parser: str = "rule"          # "guardrail" | "rule" | "llm" (the path taken)


# --- Guardrail cues --------------------------------------------------------
# Personal-health / medical-advice guardrail works by INTENT, not phrase:
#   a specific person's health (first OR third person)  +  a health concern
#   (risk, diagnosis, symptoms, treatment, or where THEY get care)  -> refuse.
# Direct first-person patterns that always refuse on their own:
_MEDICAL_PATTERNS = [
    r"\bdo i have\b", r"\bshould i (take|stop|use|see|worry|be worried)\b",
    r"\bam i\b", r"\bdiagnos", r"\bcure\b",
    r"\bmy (symptoms?|meds|medication|risk|chances?|condition|health)\b",
    r"\bwhat (medicine|drug|dose)\b", r"\bis it safe for me\b",
    r"\b(at|my) risk\b", r"\bam i at risk\b", r"\bchances? of (getting|having)\b",
    r"\bshould i be worried\b", r"\bworried (that|i|about my)\b",
    r"\bi('?m| am) (worried|concerned|afraid)\b",
]
# Clinical/educational questions about the NATURE of a disease (causes,
# symptoms, prevention, transmission): not where it's common. We don't answer
# these from county data; redirect to what we DO offer.
_CLINICAL_INFO_PATTERNS = [
    r"\bwhat causes?\b", r"\bwhat('?s| is) the cause\b", r"\bwhy do (people|you)\b",
    r"\bhow (do|can) (you|i|people|someone) (prevent|avoid|get|catch|develop|cure|treat)\b",
    r"\bhow to (prevent|avoid|treat|cure|manage)\b",
    r"\bis\b.*\b(genetic|hereditary|contagious|curable|preventable|dangerous)\b",
    r"\bsymptoms? of\b", r"\bsigns? of\b", r"\bwhat (is|are)\b.*\b(symptoms?|causes?)\b",
    r"\bhow (serious|bad|deadly) is\b",
]
# A specific person (first or third person). NOT "patients"/"people"/"adults"
# in aggregate, which are population phrasings used in legitimate queries.
_PERSON_CUES = [
    r"\bi\b", r"\bme\b", r"\bmy\b", r"\bmyself\b",
    r"\bmy (dad|mom|mother|father|son|daughter|wife|husband|partner|kid|child|"
    r"parent|brother|sister|friend|grandmother|grandfather|grandma|grandpa)\b",
    r"\bhe\b", r"\bshe\b", r"\bhis\b", r"\bher\b", r"\bthey have\b",
]
# A personal health concern: risk, diagnosis, symptoms, treatment, or seeking
# care for someone ("where should he get care/treatment/seen").
_HEALTH_CONCERN = [
    r"\brisk\b", r"\bdiagnos", r"\bsymptoms?\b", r"\btreat(ment|ed|ing)?\b",
    r"\bcure\b", r"\bmedication\b", r"\bmeds\b", r"\bhas (diabetes|asthma|copd|"
    r"high blood pressure|hypertension)\b", r"\bget (care|treated|seen|help)\b",
    r"\bwhere (should|can) (he|she|they|i|we) (get|go|be)\b",
    r"\bshould (he|she|they) (see|get)\b",
]
# Legitimate planning/research phrasings that must NEVER be refused.
_PLANNING_ALLOW = [
    r"\brecruit", r"\btrial\b", r"\bstudy\b", r"\bscreening (event|program|site)\b",
    r"\boutreach\b", r"\bevent\b",
]
# Conditions/metrics that are real health topics but OUT OF SCOPE for this app.
# Naming any of these means the user wants something we do not serve.
_UNSUPPORTED_TOPICS = [
    r"\bcancer\b", r"\bheart disease\b", r"\bheart attack\b", r"\bstroke\b",
    r"\bdepression\b", r"\bmental (health|distress)\b", r"\banxiety\b",
    r"\bobesity\b", r"\boverweight\b", r"\bsmoking\b", r"\bcigarette\b",
    r"\bsleep\b", r"\balcohol\b", r"\bdrinking\b", r"\bkidney\b", r"\bcholesterol\b",
    r"\bflu\b", r"\bcovid\b", r"\bhiv\b", r"\bdementia\b", r"\barthritis\b",
    r"\bcardiology\b", r"\bcardiac\b", r"\bcardiovascular\b",
]
_ASC_CUES = [r"\blowest\b", r"\bleast\b", r"\bfewest\b", r"\bbest\b"]

# The data is a single year (2023). Any other 4-digit year is unsupported.
DATA_YEAR = 2023

# Words that look like an area but are NOT a county filter.
_NON_AREA = {"massachusetts", "ma", "mass", "the", "state", "statewide",
             "areas", "area", "county", "counties"}


def _match_measure(text: str) -> str | None:
    text = text.lower()
    for mid, m in config.MEASURES.items():
        for alias in m.aliases:
            if alias in text:
                return mid
    return None


# Words that signal a query the rules handle poorly -> let the LLM try.
_UNCERTAIN_CUES = [r"\bnear\b", r"\baround\b", r"\bvs\.?\b", r"\bversus\b",
                   r"\bcompared to\b", r"\bcompare\b"]


def _match_area(text: str) -> tuple[str | None, bool]:
    """Return (area_token, is_near). `is_near` is True for near/around phrasing
    so the caller resolves it to a county set via geo.py."""
    m = re.search(r"\b(near|around)\s+([A-Z][a-zA-Z ]+?)(?:\?|$|,| for | with )",
                  text)
    if m and m.group(2).strip().lower() not in _NON_AREA:
        return m.group(2).strip(), True
    for m in re.finditer(r"\b(?:in|by)\s+([A-Z][a-zA-Z]+)", text):
        cand = m.group(1)
        if cand.lower() not in _NON_AREA:
            return cand, False
    return None, False


def _looks_medical(text: str) -> bool:
    """Refuse when the intent is personal/clinical: either a direct first-person
    medical pattern, OR a specific person (1st/3rd) combined with a health
    concern (risk/diagnosis/symptoms/treatment/where-to-get-care). Legitimate
    planning/research phrasings (recruit, trial, screening event) are exempt."""
    t = text.lower()
    if any(re.search(p, t) for p in _PLANNING_ALLOW):
        # Planning/research question: only refuse on a very explicit first-person
        # clinical ask, not on incidental "I" in "where should I recruit".
        return any(re.search(p, t) for p in _MEDICAL_PATTERNS[:5])
    if any(re.search(p, t) for p in _MEDICAL_PATTERNS):
        return True
    has_person = any(re.search(p, t) for p in _PERSON_CUES)
    has_concern = any(re.search(p, t) for p in _HEALTH_CONCERN)
    return has_person and has_concern


def _names_unsupported_topic(text: str) -> bool:
    """True if the question names a health topic we do NOT serve (cancer, etc.).
    Independent of prompt-injection wording: we key off the topic, not phrasing."""
    t = text.lower()
    return any(re.search(p, t) for p in _UNSUPPORTED_TOPICS)


def _asks_clinical_info(text: str) -> bool:
    """True for 'what causes/symptoms/how to prevent X': clinical/educational
    questions about a disease's nature that we don't answer from county data."""
    t = text.lower()
    return any(re.search(p, t) for p in _CLINICAL_INFO_PATTERNS)


def _names_unsupported_year(text: str) -> int | None:
    """Return a 4-digit year mentioned that is NOT our data year, else None."""
    for m in re.finditer(r"\b(19|20)\d{2}\b", text):
        y = int(m.group(0))
        if y != DATA_YEAR:
            return y
    return None


# Questions ABOUT the dataset itself (its coverage), not about a measure's value.
# "what/which counties", "what conditions/measures", "what years", "how many
# counties", "what data do you have", "where does the data come from", "coverage".
_DATASET_INFO_PATTERNS = [
    r"\bwhat (counties|conditions|measures|diseases|data|years?|sources?)\b",
    r"\bwhich (counties|conditions|measures|diseases)\b",
    r"\bhow many (counties|conditions|measures)\b",
    r"\bwhat (can|do) you (cover|answer|know|have|support)\b",
    r"\bwhat('?s| is) (covered|included|in the data|the data)\b",
    r"\bwhere (does|is) (the|your) data (come from|from)\b",
    r"\b(list|show)( me)? (the )?(counties|conditions|measures)\b",
    r"\byour (coverage|data|dataset|sources?)\b",
    r"\bdata (source|sources|coverage|year)\b",
]


def _is_dataset_info(text: str) -> bool:
    """True if the question asks about the dataset's coverage, and does NOT name
    a specific measure (a measure means they want values, not metadata)."""
    if _match_measure(text) is not None:
        return False
    t = text.lower()
    return any(re.search(p, t) for p in _DATASET_INFO_PATTERNS)


def _bare_county(text: str) -> str | None:
    """A county named with NO measure -> county profile. Returns the county."""
    if _match_measure(text) is not None:
        return None
    for c in geo.COUNTIES:
        if re.search(rf"\b{re.escape(c.lower())}\b", text.lower()):
            return c
    return None


def _is_uncertain(question: str, sq: StructuredQuery) -> bool:
    """Should we ask the LLM? Yes if the rules gave up (out_of_scope) or the
    question contains meaningful words the rules don't model."""
    if sq.intent == OUT_OF_SCOPE:
        return True
    ql = question.lower()
    return any(re.search(c, ql) for c in _UNCERTAIN_CUES)


def _maybe_explain(question: str, sq: StructuredQuery) -> StructuredQuery:
    """If the structured path gave up (out_of_scope), try RAG over our own
    knowledge base. If relevant snippets exist, answer conceptually (EXPLAIN)
    instead of the generic capability message. Statistics are never produced
    here: only authored project/data facts."""
    if sq.intent != OUT_OF_SCOPE:
        return sq
    hits = knowledge.retrieve(question)
    if hits:
        return StructuredQuery(EXPLAIN, snippet_ids=[h.id for h in hits],
                               parser=sq.parser if sq.parser != "rule" else "rule")
    return sq


# --- Stage 2: rule-based parser -------------------------------------------
def rule_parse(question: str) -> StructuredQuery:
    q = question.strip()
    if not q:
        return StructuredQuery(OUT_OF_SCOPE, parser="rule")

    if _looks_medical(q):
        return StructuredQuery(REFUSE_MEDICAL, parser="rule")

    measures_found = [mid for mid in config.MEASURES
                      if any(a in q.lower() for a in config.MEASURES[mid].aliases)]
    conditions = [m for m in measures_found
                  if config.MEASURES[m].kind == "condition"]
    access = next((m for m in measures_found
                   if config.MEASURES[m].kind == "access"), None)
    condition = conditions[0] if conditions else None

    # access-gap: a condition AND an access word together
    if condition and access:
        return StructuredQuery(ACCESS_GAP, condition=condition,
                               access_measure=access, parser="rule")

    primary = condition or access
    if primary is None:
        return StructuredQuery(OUT_OF_SCOPE, parser="rule")

    area, is_near = _match_area(q)
    ql = q.lower()
    sort = "asc" if any(re.search(c, ql) for c in _ASC_CUES) else "desc"
    area_in = geo.resolve_near(area) if (is_near and area) else None
    # Lookup only for a specific area with no list-y cue; otherwise rank.
    list_cue = any(w in ql for w in ("rank", "top", "highest", "most",
                                     "lowest", "least", "fewest", "areas",
                                     "counties", "list"))
    intent = LOOKUP if (area and not list_cue and not is_near) else RANKING
    # If the user named more than one condition, answer each of them.
    multi = conditions if len(conditions) > 1 else None
    return StructuredQuery(intent, condition=primary, conditions=multi,
                           area_filter=None if area_in else area,
                           area_in=area_in, sort=sort, parser="rule")


# --- Validation of LLM-proposed arguments ---------------------------------
def validate(args: dict) -> StructuredQuery | None:
    """Turn raw tool-call args into a StructuredQuery, or None if invalid."""
    if not isinstance(args, dict):
        return None
    intent = args.get("intent")
    if intent not in VALID_INTENTS:
        return None

    if intent in (REFUSE_MEDICAL, OUT_OF_SCOPE, LIST_SUPPORTED, DATASET_INFO,
                  UNSUPPORTED_YEAR):
        return StructuredQuery(intent, parser="llm")

    if intent == COUNTY_PROFILE:
        af = args.get("area_filter")
        canon = geo.canonical_county(af) if af else None
        if canon is None:
            return None
        return StructuredQuery(COUNTY_PROFILE, area_filter=canon, parser="llm")

    cond = args.get("condition")
    access = args.get("access_measure")
    if cond is not None and cond not in config.MEASURES:
        return None
    if access is not None and access not in config.ACCESS_MEASURES:
        return None

    if intent == ACCESS_GAP:
        if cond is None or access is None:
            return None
        if config.MEASURES[cond].kind != "condition":
            return None
    if intent in (RANKING, LOOKUP) and cond is None:
        return None

    sort = args.get("sort", "desc")
    if sort not in ("desc", "asc"):
        sort = "desc"
    limit = args.get("limit", 10)
    if not isinstance(limit, int) or not (1 <= limit <= 50):
        limit = 10

    # Resolve the LLM's area_filter through geo so a county name becomes a valid
    # filter and an unknown place resolves to nothing (handled as no-data).
    area_filter = args.get("area_filter")
    area_in = None
    if area_filter:
        canon = geo.canonical_county(area_filter)
        if canon:
            area_filter = canon

    return StructuredQuery(intent=intent, condition=cond, access_measure=access,
                           area_filter=area_filter, area_in=area_in, sort=sort,
                           limit=limit, parser="llm")


# --- Router: guardrails -> rules -> LLM-on-uncertainty --------------------
def route(question: str, provider: LLMProvider | None = None) -> StructuredQuery:
    """Rule-first. The LLM is consulted only when the rules are uncertain, and
    even then its output must pass enum validation or we keep the rule result.
    Guardrails always win and never reach the LLM."""
    # 0. Guardrails first, in priority order. All run BEFORE rules and the LLM.
    if not question or not question.strip():
        return StructuredQuery(OUT_OF_SCOPE, parser="guardrail")
    # Personal-health/risk questions refuse, even if they name a condition.
    if _looks_medical(question):
        return StructuredQuery(REFUSE_MEDICAL, parser="guardrail")
    # Unsupported health topic (cancer, obesity, ...) -> list what IS supported,
    # before any parsing, so we never show a ranking for an unnamed measure.
    if _names_unsupported_topic(question):
        return StructuredQuery(LIST_SUPPORTED, parser="guardrail")
    # Clinical/educational "what causes / symptoms / how to prevent X" -> we
    # don't answer disease-nature questions from county data; redirect.
    if _asks_clinical_info(question):
        return StructuredQuery(LIST_SUPPORTED, parser="guardrail")
    # A year other than the data year -> say we only have 2023, before the LLM.
    if _names_unsupported_year(question) is not None:
        return StructuredQuery(UNSUPPORTED_YEAR, parser="guardrail")
    # A county named with no measure -> full profile of that county.
    bare = _bare_county(question)
    if bare is not None:
        return StructuredQuery(COUNTY_PROFILE, area_filter=bare, parser="guardrail")
    # Questions about the dataset itself (which counties, years, coverage) ->
    # answer from the real data rather than the generic capability message.
    if _is_dataset_info(question):
        return StructuredQuery(DATASET_INFO, parser="guardrail")

    # 1. Deterministic rule parse.
    rule_sq = rule_parse(question)

    # 2. Only escalate to the LLM when the rules are uncertain.
    if not _is_uncertain(question, rule_sq):
        return _maybe_explain(question, rule_sq)

    provider = provider or get_provider(config.LLM_PROVIDER)
    outcome = provider.parse(question)
    if outcome.ok and outcome.arguments is not None:
        llm_sq = validate(outcome.arguments)
        if llm_sq is not None:
            # The LLM cannot INVENT a medical refusal: the guardrail already ran
            # and declined to refuse, so a non-medical question stays non-medical.
            # Drop such an LLM answer and keep the rule result.
            if llm_sq.intent == REFUSE_MEDICAL:
                return rule_sq
            # Safety: never show a ranking/lookup/gap for a measure the user
            # did not name. If the LLM invented a condition, drop to the rule
            # result (which is out_of_scope when no measure was mentioned).
            if llm_sq.intent in (RANKING, LOOKUP, ACCESS_GAP):
                named = {_match_measure(question)}
                for mid in config.MEASURES:
                    if any(a in question.lower()
                           for a in config.MEASURES[mid].aliases):
                        named.add(mid)
                if llm_sq.condition is not None and llm_sq.condition not in named:
                    return rule_sq
            # Prefer the LLM's area resolution via geo for "near X".
            if llm_sq.area_filter and not llm_sq.area_in:
                near = geo.resolve_near(llm_sq.area_filter)
                if near and re.search(r"\b(near|around)\b", question.lower()):
                    llm_sq.area_in = near
                    llm_sq.area_filter = None
            return llm_sq
    # LLM declined or produced invalid args -> keep the rule result (with RAG
    # fallback for conceptual questions).
    return _maybe_explain(question, rule_sq)
