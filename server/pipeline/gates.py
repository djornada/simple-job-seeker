"""Language and eligibility gates: reject postings you can't be hired for.

`check_gates` runs first in `score_job`, so a rejected job never reaches
the LLM. Off unless config.toml has a `[gates]` table.

- Eligibility: an `eligibility_blockers` phrase in the posting text, or a
  `region_only` phrase in the location or title, rejects. Phrases match
  case-insensitively at a word start, so "us citizen" also catches
  "US citizens" but "us only" doesn't catch "focus only".
- Language: requirement patterns ("fluent in X", "native X", "X (C1)",
  "X is required", "X speaker", "proficient in X") over a fixed list of
  human languages, never programming ones, so "Go" or "Rust" can't trip
  it. A required language missing from `[gates].languages` rejects ("X or
  Y" passes if either is declared); a requested level above the declared
  one only flags. A mention softened nearby ("a plus", "nice to have",
  "preferred", ...) never rejects; an undeclared one is flagged.
"""
from __future__ import annotations

import re

from sources import Job

LANGUAGES = (
    "arabic", "cantonese", "chinese", "czech", "danish", "dutch", "english",
    "finnish", "french", "german", "greek", "hebrew", "hindi", "hungarian",
    "indonesian", "italian", "japanese", "korean", "mandarin", "norwegian",
    "polish", "portuguese", "romanian", "russian", "spanish", "swedish",
    "thai", "turkish", "ukrainian", "vietnamese",
)
_LANG = "|".join(LANGUAGES)

# CEFR rank; requirement cue words map onto it too ("fluent" ~ C1).
_RANK = {"a1": 1, "a2": 2, "b1": 3, "b2": 4, "c1": 5, "c2": 6, "native": 7}
_CUE_LEVEL = {"fluent": "c1", "fluency": "c1", "proficient": "b2",
              "proficiency": "b2"}

# "fluent in German", "native English", "C1-level German"
_BEFORE = re.compile(
    r"\b(native|fluent|fluency|proficient|proficiency|c1|c2|b2|b1)"
    rf"(?:[- ]level)?\s+(?:in\s+|with\s+)?({_LANG})\b")
# "German (C1)", "German: fluent", "German is required", "German speaker"
_AFTER = re.compile(
    rf"\b({_LANG})\s*(?:[(:-]\s*)?(?:level\s*)?"
    r"(native|fluent|c1|c2|b2|b1|speaker|required|mandatory"
    r"|is\s+(?:a\s+)?(?:must|required|mandatory))\b")
_OR_AFTER = re.compile(rf"\s*(?:and/or|or|/)\s*({_LANG})\b")
_OR_BEFORE = re.compile(rf"\b({_LANG})\s*(?:and/or|or|/)\s*$")
_SOFT = re.compile(
    r"\b(?:plus|nice[- ]to[- ]have|bonus|preferred|preferably|advantage"
    r"|advantageous|desirable|ideally|optional|beneficial|appreciated"
    r"|not required|not necessary|not needed)\b")


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[–—]", "-", text.lower())).strip()


def _phrase(text: str, phrases: list[str]) -> str:
    """First configured phrase found at a word start in `text`, else ""."""
    for p in phrases:
        if re.search(rf"(?<![a-z0-9]){re.escape(_norm(p))}", text):
            return p
    return ""


def _level(word: str) -> str:
    word = word.lower()
    if word in _RANK:
        return word
    return _CUE_LEVEL.get(word, "b2")  # "required", "speaker", "must"...


def _label(level: str) -> str:
    return level if level == "native" else level.upper()


def _soft(text: str, start: int, end: int) -> bool:
    """A softener in the same sentence before, or the same clause after."""
    before = re.split(r"[.;!?•]", text[max(0, start - 60):start])[-1]
    after = re.split(r"[.;,!?•]", text[end:end + 40])[0]
    return bool(_SOFT.search(before) or _SOFT.search(after))


def _requirements(text: str) -> list[tuple[list[str], str, bool]]:
    """(alternative languages, requested level, softened) per mention."""
    reqs = []
    for m in _BEFORE.finditer(text):
        alts, pos = [m.group(2)], m.end()
        while (alt := _OR_AFTER.match(text, pos)):
            alts.append(alt.group(1))
            pos = alt.end()
        reqs.append((alts, _level(m.group(1)), _soft(text, m.start(), pos)))
    for m in _AFTER.finditer(text):
        alts = [m.group(1)]
        alt = _OR_BEFORE.search(text[max(0, m.start() - 40):m.start()])
        if alt:
            alts.append(alt.group(1))
        cue = m.group(2).split()[-1]  # "is a must" -> "must"
        reqs.append((alts, _level(cue), _soft(text, m.start(), m.end())))
    return reqs


def check_gates(job: Job, cfg: dict) -> tuple[str, list[str]]:
    """Return (reject_kind, flags). reject_kind is "" when the job passes,
    else "eligibility" or "language", with the reason in flags."""
    gates = cfg.get("gates")
    if not gates:
        return "", []

    text = _norm(job.full_text or job.description)
    hit = _phrase(text, gates.get("eligibility_blockers", []))
    if hit:
        return "eligibility", [f"Not eligible: “{hit}”"]
    hit = _phrase(_norm(f"{job.location} {job.title}"),
                  gates.get("region_only", []))
    if hit:
        return "eligibility", [f"Region-locked: “{hit}”"]

    declared = {k.lower(): _level(str(v))
                for k, v in gates.get("languages", {}).items()}
    if not declared:
        return "", []
    missing: list[str] = []
    flags: list[str] = []
    for alts, level, soft in _requirements(text):
        have = [a for a in alts if a in declared]
        names = " or ".join(a.capitalize() for a in alts)
        if not have:
            if soft:
                flags.append(f"{names} nice-to-have")
            else:
                missing.append(f"Requires {names}")
            continue
        best = max(have, key=lambda a: _RANK[declared[a]])
        if not soft and _RANK[level] > _RANK[declared[best]]:
            flags.append(f"Asks for {_label(level)} {best.capitalize()}; "
                         f"you declared {_label(declared[best])}")
    if missing:
        return "language", list(dict.fromkeys(missing))
    return "", list(dict.fromkeys(flags))
