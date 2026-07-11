"""Deterministic extraction of a Kiwi Job Summary from a raw job description.

No LLM, no external API — regex, keyword matching, and section detection
only. Missing values stay empty; nothing here is ever invented. See
docs/ROADMAP.md Phase 7.6.
"""
import re
from collections import defaultdict

from backend.job_summary.models import JobSummary

_OVERVIEW_TRUNCATE_LIMIT = 600

# Heading phrases are matched against a whole (cleaned) line via fullmatch,
# so "3+ years of experience in a similar role" can never be mistaken for
# the heading "Experience" — only a line that IS (near enough) just the
# heading phrase counts.
_SECTION_PHRASES: dict[str, list[str]] = {
    "overview": [
        "about the role", "about this role", "about the job", "about the position",
        "overview", "role overview", "job overview", "the opportunity", "about us",
    ],
    "responsibilities": [
        "responsibilities", "key responsibilities", "main responsibilities",
        "your responsibilities", "what you'll do", "what you will do", "duties",
        "day to day", "day-to-day", "day-to-day duties",
    ],
    "requirements_required": [
        "requirements", "key requirements", "qualifications", "skills and experience",
        "skills & experience", "required skills", "essential criteria", "essential skills",
        "what you'll need", "what you need", "what you will need", "about you",
        "experience required", "who we're looking for", "what we're looking for",
        "skills", "experience",
    ],
    "requirements_preferred": [
        "preferred", "preferred skills", "preferred qualifications", "desirable",
        "desired skills", "nice to have", "nice to haves", "bonus points",
        "advantageous", "would be an advantage",
    ],
    "benefits": [
        "benefits", "what we offer", "perks", "why join us", "why work with us",
        "what's in it for you", "whats in it for you",
    ],
    "work_environment": [
        "working conditions", "work environment", "about the team", "culture",
        "about our team",
    ],
    "salary": [
        "salary", "pay", "hourly rate", "remuneration", "compensation", "salary package",
    ],
}

_SECTION_PATTERNS: dict[str, re.Pattern] = {
    key: re.compile("|".join(re.escape(p) for p in phrases), re.IGNORECASE)
    for key, phrases in _SECTION_PHRASES.items()
}

_BULLET_PREFIX_RE = re.compile(r"^[\-\*•▪‣⁃]\s+|^\d+[\.\)]\s+")
_HEADING_STRIP_RE = re.compile(r"^[#\*\-\s]+")

_SALARY_RE = re.compile(
    r"\$\s?\d[\d,]*(?:\.\d{1,2})?"
    r"(?:\s?(?:[-–]|to)\s?\$?\s?\d[\d,]*(?:\.\d{1,2})?)?"
    r"(?:\s?(?:per\s+hour|/\s?hr|p\.?h\.?|an\s+hour|per\s+annum|p\.?a\.?|"
    r"/\s?yr|per\s+year|per\s+week|/\s?wk))?",
    re.IGNORECASE,
)

_VISA_KEYWORDS_RE = re.compile(
    r"\bvisa\b|work\s+rights|sponsorship|\beligib|\bcitizen|residency|work\s+permit",
    re.IGNORECASE,
)
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")


def _match_heading(line: str) -> str | None:
    cleaned = _HEADING_STRIP_RE.sub("", line.strip()).rstrip(":").strip()
    if not cleaned or len(cleaned) > 60:
        return None
    for key, pattern in _SECTION_PATTERNS.items():
        if pattern.fullmatch(cleaned):
            return key
    return None


def _split_bullets(lines: list[str]) -> list[str]:
    items: list[str] = []
    for line in lines:
        cleaned = _BULLET_PREFIX_RE.sub("", line).strip()
        if cleaned:
            items.append(cleaned)
    return items


def _truncate(text: str, limit: int = _OVERVIEW_TRUNCATE_LIMIT) -> str:
    collapsed = " ".join(text.split())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[:limit].rstrip() + "…"


def _extract_salary_mention(text: str) -> str:
    match = _SALARY_RE.search(text)
    return match.group(0).strip() if match else ""


def _extract_visa_notes(text: str, max_sentences: int = 2) -> str:
    sentences = [_BULLET_PREFIX_RE.sub("", s.strip()).strip() for s in _SENTENCE_SPLIT_RE.split(text)]
    sentences = [s for s in sentences if s and _match_heading(s) is None]
    matches = [s for s in sentences if _VISA_KEYWORDS_RE.search(s)]
    return " ".join(matches[:max_sentences])


def generate_job_summary(description: str | None, salary_text: str | None = None) -> JobSummary:
    """Extract a Kiwi Job Summary from raw description text. `salary_text`
    (e.g. a scraper's separately-parsed salary field) is used only as a
    last-resort fallback when no salary can be found in the description
    itself — never invented."""
    summary = JobSummary()
    text = (description or "").strip()

    if not text:
        summary.warnings.append("No job description available — summary could not be generated.")
        if salary_text and salary_text.strip():
            summary.salary = salary_text.strip()
        return summary

    lines = [ln.rstrip() for ln in text.splitlines()]

    sections: dict[str, list[str]] = defaultdict(list)
    preamble: list[str] = []
    current_section: str | None = None
    any_heading_found = False

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        heading = _match_heading(line)
        if heading:
            current_section = heading
            any_heading_found = True
            continue
        if current_section is None:
            preamble.append(line)
        else:
            sections[current_section].append(line)

    if sections.get("overview"):
        summary.overview = _truncate(" ".join(_split_bullets(sections["overview"])))
    elif preamble and any_heading_found:
        # Text before the first heading, e.g. an unlabelled intro paragraph
        # above "Responsibilities:". When there are NO headings at all,
        # "preamble" is the entire description — handled by the fallback
        # branch below instead, so it isn't double-counted here.
        summary.overview = _truncate(" ".join(preamble))

    summary.responsibilities = _split_bullets(sections.get("responsibilities", []))
    summary.requirements_required = _split_bullets(sections.get("requirements_required", []))
    summary.requirements_preferred = _split_bullets(sections.get("requirements_preferred", []))
    summary.benefits = _split_bullets(sections.get("benefits", []))
    summary.work_environment = _split_bullets(sections.get("work_environment", []))

    if sections.get("salary"):
        summary.salary = " ".join(sections["salary"]).strip()
    else:
        summary.salary = _extract_salary_mention(text) or (salary_text.strip() if salary_text else "")

    summary.visa_notes = _extract_visa_notes(text)

    if not any_heading_found:
        # Conservative fallback: never guess which bullets are
        # responsibilities vs requirements when there's no heading evidence
        # to justify that categorization. Only treat this as "a bullet
        # list" when an actual bullet marker was seen — plain prose with no
        # markers and no headings goes to Overview verbatim instead of
        # being fragmented line-by-line into fake "responsibilities".
        has_bullet_markers = any(_BULLET_PREFIX_RE.match(ln.strip()) for ln in lines if ln.strip())
        if has_bullet_markers:
            summary.responsibilities = _split_bullets(lines)
            summary.warnings.append(
                "No section headings detected — bullet points shown under "
                "Responsibilities without further categorization."
            )
        else:
            summary.overview = _truncate(text)
            summary.warnings.append("No structured sections detected in this job description.")
    else:
        if not summary.responsibilities:
            summary.warnings.append("No responsibilities section detected.")
        if not summary.requirements_required and not summary.requirements_preferred:
            summary.warnings.append("No requirements section detected.")

    if not summary.salary:
        summary.warnings.append("No salary information found.")

    return summary
