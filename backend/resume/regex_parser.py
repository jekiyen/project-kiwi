"""Deterministic, regex/heuristic resume parser.

No AI involved — same spirit as ManualProvider in backend/ai/manual.py.
Section detection is header-keyword based, which works reasonably well on
typical single-column resumes and degrades gracefully (returns partial
results, never raises) on anything unusual. A Phase 8 AI-based parser can
implement ResumeParser and produce the same ParsedResume shape for a much
higher accuracy ceiling.
"""
import re

from backend.resume.base import (
    EducationEntry,
    ExperienceEntry,
    ParsedResume,
    ResumeParser,
)

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE_RE = re.compile(r"(?:\+?\d[\d \-\(\)]{7,}\d)")
_LINKEDIN_RE = re.compile(r"(?:https?://)?(?:www\.)?linkedin\.com/in/[A-Za-z0-9\-_%]+/?", re.IGNORECASE)
_URL_RE = re.compile(r"(?:https?://)?(?:www\.)?[A-Za-z0-9\-]+\.[A-Za-z]{2,}(?:/[^\s,;]*)?")
_DATE_RANGE_RE = re.compile(
    r"((?:19|20)\d{2})\s*(?:-|–|—|to)\s*((?:19|20)\d{2}|present|current)",
    re.IGNORECASE,
)

_SECTION_KEYWORDS: dict[str, list[str]] = {
    "skills": ["skills", "technical skills", "core competencies", "key skills", "skills & tools"],
    "experience": [
        "experience", "work experience", "employment history",
        "professional experience", "work history",
    ],
    "education": ["education", "academic background", "qualifications", "education & training"],
}

_SPLIT_SKILLS_RE = re.compile(r"[,;|•·]|\s{2,}|\t")


def _find_sections(lines: list[str]) -> dict[str, list[str]]:
    """Split resume lines into named sections based on header keywords.

    A line counts as a header only if it's short and matches a keyword
    exactly (ignoring case/trailing colon) — avoids misfiring on prose that
    happens to contain a keyword mid-sentence.
    """
    sections: dict[str, list[str]] = {}
    current: str | None = None
    header_lookup = {kw: name for name, kws in _SECTION_KEYWORDS.items() for kw in kws}

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        lowered = line.lower().strip(":").strip()
        if len(lowered) <= 40 and lowered in header_lookup:
            current = header_lookup[lowered]
            sections.setdefault(current, [])
            continue
        if current:
            sections.setdefault(current, []).append(line)

    return sections


def _extract_email(text: str) -> str | None:
    m = _EMAIL_RE.search(text)
    return m.group(0) if m else None


def _extract_phone(text: str) -> str | None:
    for candidate in _PHONE_RE.findall(text):
        digits = re.sub(r"\D", "", candidate)
        if 7 <= len(digits) <= 15:
            return candidate.strip()
    return None


def _extract_linkedin(text: str) -> str | None:
    m = _LINKEDIN_RE.search(text)
    return m.group(0) if m else None


def _extract_portfolio(text: str, linkedin: str | None, email: str | None) -> str | None:
    # Blank out the email match first — "name.surname@x.com" otherwise looks
    # like a URL match ("name.surname") to a regex that doesn't know about "@".
    search_text = text
    if email:
        search_text = search_text.replace(email, " " * len(email))

    for m in _URL_RE.finditer(search_text):
        url = m.group(0)
        if "linkedin.com" in url.lower():
            continue
        return url
    return None


def _extract_name(lines: list[str], email: str | None) -> str | None:
    for line in lines[:5]:
        stripped = line.strip()
        if not stripped or len(stripped) > 60:
            continue
        if "@" in stripped or _URL_RE.search(stripped) or any(ch.isdigit() for ch in stripped):
            continue
        if stripped.lower().strip(":") in {kw for kws in _SECTION_KEYWORDS.values() for kw in kws}:
            continue
        return stripped
    return None


def _extract_skills(section_lines: list[str]) -> list[str]:
    joined = "\n".join(section_lines)
    tokens = [t.strip(" -•\t") for t in _SPLIT_SKILLS_RE.split(joined)]
    seen: set[str] = set()
    skills: list[str] = []
    for token in tokens:
        if not token or len(token) > 60:
            continue
        key = token.lower()
        if key in seen:
            continue
        seen.add(key)
        skills.append(token)
    return skills


def _is_bullet(stripped: str) -> bool:
    return stripped.startswith(("•", "-", "*", "‣", "◦"))


def _is_date_only_line(stripped: str) -> bool:
    m = _DATE_RANGE_RE.search(stripped)
    return bool(m) and len(m.group(0)) >= 0.7 * len(stripped)


def _group_blocks(section_lines: list[str]) -> list[list[str]]:
    """Group section lines into entry blocks.

    Blank lines are usually lost by PDF text extraction, so a new entry is
    detected structurally: once a block has seen a bullet (its description),
    the next non-bullet line is the header of a new entry. Everything before
    the first bullet (title/company line, a standalone date line) stays part
    of the same header.
    """
    blocks: list[list[str]] = []
    current: list[str] = []
    seen_bullet = False

    for raw in section_lines:
        stripped = raw.strip()
        if not stripped:
            continue
        is_bullet = _is_bullet(stripped)

        if current and seen_bullet and not is_bullet:
            blocks.append(current)
            current = []
            seen_bullet = False

        current.append(raw)
        if is_bullet:
            seen_bullet = True

    if current:
        blocks.append(current)
    return blocks


def _split_title_company(line: str) -> tuple[str, str]:
    line = line.lstrip("•-* \t")
    for sep in (" at ", " @ ", " — ", " – ", " - ", ", "):
        if sep in line:
            left, right = line.split(sep, 1)
            return left.strip(), right.strip()
    return line.strip(), ""


def _block_description(block: list[str]) -> str:
    """Every line after the header, minus standalone date lines and bullet markers."""
    lines = []
    for line in block[1:]:
        stripped = line.strip()
        if not stripped or _is_date_only_line(stripped):
            continue
        lines.append(stripped.lstrip("•-*‣◦ \t"))
    return "\n".join(lines)


def _extract_experience(section_lines: list[str]) -> list[ExperienceEntry]:
    entries: list[ExperienceEntry] = []
    for block in _group_blocks(section_lines):
        if not block:
            continue
        header = block[0]
        date_match = _DATE_RANGE_RE.search(" ".join(block))
        dates = date_match.group(0) if date_match else ""
        header_no_dates = _DATE_RANGE_RE.sub("", header).strip(" ,-–—\t")
        title, company = _split_title_company(header_no_dates)
        description = _block_description(block)
        if not title and not company:
            continue
        entries.append(ExperienceEntry(title=title, company=company, dates=dates, description=description))
    return entries


def _extract_education(section_lines: list[str]) -> list[EducationEntry]:
    entries: list[EducationEntry] = []
    for block in _group_blocks(section_lines):
        if not block:
            continue
        header = block[0]
        date_match = _DATE_RANGE_RE.search(" ".join(block))
        dates = date_match.group(0) if date_match else ""
        header_no_dates = _DATE_RANGE_RE.sub("", header).strip(" ,-–—\t")
        institution, qualification = _split_title_company(header_no_dates)
        if not institution:
            continue
        entries.append(EducationEntry(institution=institution, qualification=qualification, dates=dates))
    return entries


class RegexResumeParser(ResumeParser):
    version = "regex-v1"

    async def parse(self, text: str) -> ParsedResume:
        lines = text.splitlines()
        sections = _find_sections(lines)

        email = _extract_email(text)
        linkedin = _extract_linkedin(text)
        experience = _extract_experience(sections.get("experience", []))
        education = _extract_education(sections.get("education", []))

        companies, seen_c = [], set()
        job_titles, seen_t = [], set()
        for entry in experience:
            if entry.company and entry.company.lower() not in seen_c:
                seen_c.add(entry.company.lower())
                companies.append(entry.company)
            if entry.title and entry.title.lower() not in seen_t:
                seen_t.add(entry.title.lower())
                job_titles.append(entry.title)

        return ParsedResume(
            name=_extract_name(lines, email),
            email=email,
            phone=_extract_phone(text),
            linkedin=linkedin,
            portfolio=_extract_portfolio(text, linkedin, email),
            skills=_extract_skills(sections.get("skills", [])),
            companies=companies,
            job_titles=job_titles,
            education=education,
            experience=experience,
        )
