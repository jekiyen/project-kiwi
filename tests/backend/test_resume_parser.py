"""Tests for the regex resume parser and text extraction (no API involved)."""
import io

import pytest
from docx import Document

from backend.resume import RegexResumeParser, get_resume_parser
from backend.resume.text_extraction import (
    TextExtractionError,
    extract_text,
    extract_text_from_docx,
    extract_text_from_pdf,
)


def make_minimal_pdf(text_lines: list[str]) -> bytes:
    """Hand-crafted minimal single-page PDF with the given lines of text.
    Avoids adding a PDF-generation library as a dependency just for tests."""
    buf = io.BytesIO()

    def w(s):
        buf.write(s.encode("latin-1") if isinstance(s, str) else s)

    offsets: dict[int, int] = {}
    w("%PDF-1.4\n")
    offsets[1] = buf.tell()
    w("1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
    offsets[2] = buf.tell()
    w("2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n")
    offsets[3] = buf.tell()
    w(
        "3 0 obj\n<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 4 0 R >> >> "
        "/MediaBox [0 0 612 792] /Contents 5 0 R >>\nendobj\n"
    )
    offsets[4] = buf.tell()
    w("4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n")

    content_lines = ["BT", "/F1 11 Tf", "12 TL", "72 740 Td"]
    for i, line in enumerate(text_lines):
        escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        if i > 0:
            content_lines.append("T*")
        content_lines.append(f"({escaped}) Tj")
    content_lines.append("ET")
    content_bytes = "\n".join(content_lines).encode("latin-1")

    offsets[5] = buf.tell()
    w(f"5 0 obj\n<< /Length {len(content_bytes)} >>\nstream\n")
    w(content_bytes)
    w("\nendstream\nendobj\n")

    xref_offset = buf.tell()
    w("xref\n0 6\n0000000000 65535 f \n")
    for i in range(1, 6):
        w(f"{offsets[i]:010d} 00000 n \n")
    w(f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF")
    return buf.getvalue()


def make_minimal_docx(paragraphs: list[str]) -> bytes:
    doc = Document()
    for p in paragraphs:
        doc.add_paragraph(p)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


SAMPLE_RESUME_TEXT = """Rizky Pratama
rizky.pratama@email.com
+62 812 3456 7890
linkedin.com/in/rizkypratama
github.com/rizkypratama

Skills
Python, Product Design, Figma, Communication, Problem Solving

Experience
Product Designer at Tokopedia
2021 - 2023
• Led design for checkout flow, improved conversion by 12%.
• Mentored two junior designers.

UX Intern, Gojek
2020 - 2021
• Supported research and prototyping for driver app.

Education
Bandung Institute of Technology, Bachelor of Design
2016 - 2020
"""


# ── Text extraction ──────────────────────────────────────────────────────────

def test_extract_text_from_pdf():
    pdf_bytes = make_minimal_pdf(["Hello World", "Second line"])
    text = extract_text_from_pdf(pdf_bytes)
    assert "Hello World" in text
    assert "Second line" in text


def test_extract_text_from_pdf_no_text_raises():
    pdf_bytes = make_minimal_pdf([])
    with pytest.raises(TextExtractionError):
        extract_text_from_pdf(pdf_bytes)


def test_extract_text_from_pdf_garbage_raises():
    with pytest.raises(TextExtractionError):
        extract_text_from_pdf(b"not a pdf at all")


def test_extract_text_from_docx():
    docx_bytes = make_minimal_docx(["Jane Doe", "jane@example.com"])
    text = extract_text_from_docx(docx_bytes)
    assert "Jane Doe" in text
    assert "jane@example.com" in text


def test_extract_text_from_docx_garbage_raises():
    with pytest.raises(TextExtractionError):
        extract_text_from_docx(b"not a docx at all")


def test_extract_text_dispatches_by_type():
    pdf_bytes = make_minimal_pdf(["PDF content"])
    assert "PDF content" in extract_text(pdf_bytes, "pdf")

    docx_bytes = make_minimal_docx(["DOCX content"])
    assert "DOCX content" in extract_text(docx_bytes, "docx")


def test_extract_text_unsupported_type_raises():
    with pytest.raises(TextExtractionError):
        extract_text(b"whatever", "txt")


# ── get_resume_parser() factory ─────────────────────────────────────────────

def test_get_resume_parser_returns_regex_parser():
    parser = get_resume_parser()
    assert isinstance(parser, RegexResumeParser)
    assert parser.version == "regex-v1"


# ── RegexResumeParser — field extraction ────────────────────────────────────

@pytest.mark.asyncio
async def test_parses_name():
    result = await RegexResumeParser().parse(SAMPLE_RESUME_TEXT)
    assert result.name == "Rizky Pratama"


@pytest.mark.asyncio
async def test_parses_email():
    result = await RegexResumeParser().parse(SAMPLE_RESUME_TEXT)
    assert result.email == "rizky.pratama@email.com"


@pytest.mark.asyncio
async def test_parses_phone():
    result = await RegexResumeParser().parse(SAMPLE_RESUME_TEXT)
    assert result.phone is not None
    assert "812" in result.phone


@pytest.mark.asyncio
async def test_parses_linkedin():
    result = await RegexResumeParser().parse(SAMPLE_RESUME_TEXT)
    assert result.linkedin == "linkedin.com/in/rizkypratama"


@pytest.mark.asyncio
async def test_parses_portfolio_not_confused_with_email():
    result = await RegexResumeParser().parse(SAMPLE_RESUME_TEXT)
    assert result.portfolio == "github.com/rizkypratama"
    assert "email.com" not in (result.portfolio or "")


@pytest.mark.asyncio
async def test_parses_skills():
    result = await RegexResumeParser().parse(SAMPLE_RESUME_TEXT)
    assert "Python" in result.skills
    assert "Product Design" in result.skills
    assert "Figma" in result.skills


@pytest.mark.asyncio
async def test_parses_companies_and_titles():
    result = await RegexResumeParser().parse(SAMPLE_RESUME_TEXT)
    assert "Tokopedia" in result.companies
    assert "Gojek" in result.companies
    assert "Product Designer" in result.job_titles
    assert "UX Intern" in result.job_titles


@pytest.mark.asyncio
async def test_parses_experience_with_dates_and_description():
    result = await RegexResumeParser().parse(SAMPLE_RESUME_TEXT)
    assert len(result.experience) == 2
    tokopedia = next(e for e in result.experience if e.company == "Tokopedia")
    assert tokopedia.title == "Product Designer"
    assert "2021" in tokopedia.dates and "2023" in tokopedia.dates
    assert "checkout flow" in tokopedia.description
    assert "Mentored" in tokopedia.description
    # Standalone date line must not leak into the description.
    assert "2021 - 2023" not in tokopedia.description


@pytest.mark.asyncio
async def test_parses_education():
    result = await RegexResumeParser().parse(SAMPLE_RESUME_TEXT)
    assert len(result.education) == 1
    edu = result.education[0]
    assert edu.institution == "Bandung Institute of Technology"
    assert "Design" in edu.qualification
    assert "2016" in edu.dates


@pytest.mark.asyncio
async def test_empty_text_returns_empty_result_without_raising():
    result = await RegexResumeParser().parse("")
    assert result.name is None
    assert result.email is None
    assert result.skills == []
    assert result.experience == []


@pytest.mark.asyncio
async def test_text_with_no_recognizable_structure_degrades_gracefully():
    result = await RegexResumeParser().parse("just some random prose with no sections at all")
    assert result.email is None
    assert result.skills == []
