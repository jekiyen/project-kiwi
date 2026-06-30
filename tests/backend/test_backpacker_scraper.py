"""
Tests for the BackpackerBoard NZ scraper.

All tests use local fixture HTML — no network requests are made.
Only _parse_page() and _parse_row() are tested directly.
"""
from pathlib import Path

import pytest
from sqlalchemy import create_engine as _sa_engine
from sqlmodel import Session, SQLModel

from backend.scrapers.backpacker import BackpackerBoardScraper
from backend.scrapers.base import ScrapedJob
from backend.database.models import Job, RolePriority
from backend.core.matcher import classify_role
from backend.agents.scan_agent import ScanAgent


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def scraper() -> BackpackerBoardScraper:
    return BackpackerBoardScraper()


@pytest.fixture(scope="module")
def fixture_html() -> str:
    path = Path(__file__).parent / "fixtures" / "backpacker_results.html"
    return path.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def parsed_jobs(scraper, fixture_html) -> list[ScrapedJob]:
    return scraper._parse_page(fixture_html)


@pytest.fixture
def db_session():
    engine = _sa_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)


# ── Parser: count and structure ───────────────────────────────────────────────


def test_parse_returns_three_valid_jobs(parsed_jobs):
    """Rows with non-NZ links, no links, and unclassed header rows must be skipped."""
    assert len(parsed_jobs) == 3


def test_all_results_are_scraped_job_instances(parsed_jobs):
    for job in parsed_jobs:
        assert isinstance(job, ScrapedJob)


def test_source_is_backpacker(parsed_jobs):
    for job in parsed_jobs:
        assert job.source == "backpacker"


# ── Parser: field extraction ──────────────────────────────────────────────────


def test_title_extraction(parsed_jobs):
    titles = [j.title for j in parsed_jobs]
    assert any("Packhouse" in t for t in titles)
    assert any("Farm Labourer" in t for t in titles)
    assert any("Orchard Worker" in t for t in titles)


def test_employer_is_unknown(parsed_jobs):
    """BackpackerBoard list view does not expose employer — defaults to Unknown."""
    for job in parsed_jobs:
        assert job.employer == "Unknown"


def test_location_extraction(parsed_jobs):
    locations = [j.location for j in parsed_jobs]
    assert "Hawke's Bay" in locations or any("Hawke" in l for l in locations)
    assert "Bay of Plenty" in locations
    assert "Nelson" in locations


def test_url_contains_backpackerboard_domain(parsed_jobs):
    for job in parsed_jobs:
        assert "backpackerboard.co.nz" in job.url


def test_url_contains_work_jobs_path(parsed_jobs):
    for job in parsed_jobs:
        assert "/work_jobs/" in job.url


def test_url_contains_new_zealand_jobs(parsed_jobs):
    for job in parsed_jobs:
        assert "new-zealand-jobs" in job.url


def test_no_salary_field(parsed_jobs):
    for job in parsed_jobs:
        assert job.salary_text is None


# ── Job ID extraction ─────────────────────────────────────────────────────────


def test_extract_id_from_filename(scraper):
    assert scraper._extract_job_id("new-zealand-jobs118080.html") == "118080"


def test_extract_id_from_path_with_subdir(scraper):
    assert scraper._extract_job_id("../new-zealand-jobs999.html") == "999"


def test_extract_id_returns_none_for_non_nz_link(scraper):
    assert scraper._extract_job_id("australia-jobs99999.html") is None


def test_extract_id_returns_none_for_empty_string(scraper):
    assert scraper._extract_job_id("") is None


def test_external_id_is_numeric_string(parsed_jobs):
    for job in parsed_jobs:
        assert job.external_id.isdigit()


def test_featured_job_has_correct_id(parsed_jobs):
    packhouse = next(j for j in parsed_jobs if "Packhouse" in j.title)
    assert packhouse.external_id == "118080"


# ── Role classification ───────────────────────────────────────────────────────


def test_classify_p1_packhouse():
    assert classify_role("Packhouse Workers Wanted") == RolePriority.P1


def test_classify_p1_orchard():
    assert classify_role("Orchard Worker") == RolePriority.P1


def test_classify_p3_farm_labourer():
    assert classify_role("Farm Labourer") in (RolePriority.P1, RolePriority.P3)


# ── DB storage ────────────────────────────────────────────────────────────────


def make_scraped(external_id="118080", title="Packhouse Workers Wanted") -> ScrapedJob:
    return ScrapedJob(
        external_id=external_id,
        source="backpacker",
        title=title,
        employer="Unknown",
        location="Hawke's Bay",
        url=f"https://www.backpackerboard.co.nz/work_jobs/new-zealand-jobs{external_id}.html",
    )


def test_store_new_backpacker_job(db_session):
    agent = ScanAgent()
    new, changed, _ = agent._store_scraped_jobs(db_session, [make_scraped()])
    assert new == 1
    assert changed == 0


def test_stored_job_has_backpacker_source(db_session):
    agent = ScanAgent()
    agent._store_scraped_jobs(db_session, [make_scraped()])
    import sqlmodel
    job = db_session.exec(sqlmodel.select(Job)).first()
    assert job.source == "backpacker"


def test_backpacker_duplicate_not_stored_twice(db_session):
    agent = ScanAgent()
    scraped = make_scraped()
    agent._store_scraped_jobs(db_session, [scraped])
    new2, _, __ = agent._store_scraped_jobs(db_session, [scraped])
    assert new2 == 0
    import sqlmodel
    count = db_session.exec(
        sqlmodel.select(sqlmodel.func.count()).select_from(Job)
    ).one()
    assert count == 1


def test_backpacker_and_trademe_same_id_not_deduplicated(db_session):
    """Same external_id from backpacker and trademe must be stored as separate jobs."""
    agent = ScanAgent()
    tm_job = ScrapedJob(
        external_id="118080",
        source="trademe",
        title="Packhouse Worker",
        employer="Employer A",
        location="Hawke's Bay",
        url="https://www.trademe.co.nz/a/jobs/listing/118080",
    )
    bp_job = make_scraped("118080")
    new, _, __ = agent._store_scraped_jobs(db_session, [tm_job, bp_job])
    assert new == 2


def test_multiple_backpacker_jobs_all_stored(db_session):
    agent = ScanAgent()
    jobs = [make_scraped(str(100 + i), f"Job Title {i}") for i in range(3)]
    new, _, __ = agent._store_scraped_jobs(db_session, jobs)
    assert new == 3
