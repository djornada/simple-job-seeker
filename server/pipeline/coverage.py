"""Résumé keyword coverage: which of a posting's keywords the profile has.

`extract_keywords` is one JSON-mode LLM call over the archived posting,
returning its required and preferred keywords as short terms. `match` is
deterministic, with no LLM, so the same keyword list always gives the same
result: a term found as a whole word in the profile is `covered`, one
found only under another spelling from `[keywords].aliases` is `synonym`,
anything else `missing`. A term the posting doesn't contain under any
spelling is dropped, so the model can't invent requirements (a substring
check: archived board text can run words together). Run on demand from
the web UI, never in builds.
"""
from __future__ import annotations

import re

import llm

from .fit import parse_json_object
from .keywords import alias_map, clean

KINDS = ("required", "preferred")
STATUSES = ("missing", "synonym", "covered")  # display order
MAX_TERMS = 15     # per kind
MAX_WIDTH = 40     # chars per term
MAX_CHARS = 8000   # posting text sent; keeps the prompt in a small context


def extract_keywords(text: str, cfg: dict) -> dict | None:
    """{"required": [...], "preferred": [...]} from the posting text; {} if
    the reply has no usable terms, None if the LLM backend is unreachable."""
    text = text[:MAX_CHARS]
    prompt = (
        "List the skills a résumé would need to match this job posting, "
        "named the way a résumé's skills section would: languages, "
        "frameworks, databases, tools, practices and domains. Split them "
        "into required and preferred; preferred is only what the posting "
        "marks as optional (nice to have, a plus, bonus, preferred), so "
        "leave it empty if nothing is. Only terms that appear in the "
        "posting, each the bare skill name (\"Jest\", not \"Jest testing\"; "
        "\"GraphQL\", not \"GraphQL APIs\"), one to three words, no "
        f"duplicates, at most {MAX_TERMS} per list. Leave out the job title, "
        "years of experience, degrees, soft skills such as communication, "
        "benefits, location, and anything describing the company, its "
        "product or its customers.\n\n"
        f"POSTING:\n{text}\n\n"
        'Reply as JSON only: {"required": ["<term>"], "preferred": ["<term>"]}'
    )
    raw = llm.generate(cfg, prompt, fmt="json", options={"temperature": 0})
    if raw is None:
        return None
    data = parse_json_object(llm.strip_think(raw)) or {}
    posting, aliases = clean(text), alias_map(cfg)
    seen: set[str] = set()
    keywords = {kind: _terms(data.get(kind), seen, posting, aliases)
                for kind in KINDS}
    return keywords if any(keywords.values()) else {}


def _terms(value: object, seen: set[str], posting: str,
           aliases: dict[str, str]) -> list[str]:
    """Up to MAX_TERMS distinct terms the (cleaned) posting contains under
    some spelling; `seen` dedupes across kinds, so a term listed as both
    required and preferred stays required."""
    out: list[str] = []
    for v in value if isinstance(value, list) else []:
        if not isinstance(v, str):
            continue
        term = re.sub(r"\s+", " ", v).strip()[:MAX_WIDTH]
        key = clean(term)
        if (term and key not in seen and len(out) < MAX_TERMS
                and any(s in posting for s in _spellings(key, aliases))):
            seen.add(key)
            out.append(term)
    return out


def _spellings(key: str, aliases: dict[str, str]) -> set[str]:
    """A cleaned term plus every spelling `[keywords].aliases` maps to the
    same canonical form (including the canonical itself)."""
    canon = aliases.get(key, key)
    return {key, canon} | {k for k, v in aliases.items() if v == canon}


def _found(term: str, text: str) -> bool:
    """`term` as a whole word in `text` (both cleaned). `+` and `#` count
    as word characters, so "c" doesn't match "c++" or "c#"."""
    pattern = rf"(?<![\w+#]){re.escape(term)}(?![\w+#])"
    return re.search(pattern, text) is not None


def match(terms: list[str], profile_text: str,
          aliases: dict[str, str]) -> dict[str, str]:
    """term → covered | synonym | missing against the profile text."""
    text = clean(profile_text)
    out: dict[str, str] = {}
    for term in terms:
        key = clean(term)
        if _found(key, text):
            out[term] = "covered"
        elif any(_found(s, text) for s in _spellings(key, aliases) - {key}):
            out[term] = "synonym"
        else:
            out[term] = "missing"
    return out


def check_coverage(posting_text: str, profile_text: str,
                   cfg: dict) -> dict | None:
    """What `queue_items.coverage_json` stores: {"terms": [{"term", "kind",
    "status"}]}, missing-required first. {} if the reply has no usable
    terms, None if the LLM backend is unreachable."""
    keywords = extract_keywords(posting_text, cfg)
    if not keywords:
        return keywords
    aliases = alias_map(cfg)
    rows = []
    for kind in KINDS:
        status = match(keywords[kind], profile_text, aliases)
        rows += [{"term": t, "kind": kind, "status": status[t]}
                 for t in keywords[kind]]
    rows.sort(key=lambda r: (KINDS.index(r["kind"]),
                             STATUSES.index(r["status"])))
    return {"terms": rows}
