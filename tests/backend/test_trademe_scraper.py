"""
Tests for the Trade Me Jobs scraper.

All tests use local fixture HTML — no network requests are made.
Playwright is not invoked; only _parse_page() and _parse_card() are tested directly.
"""
from pathlib import Path

import pytest
from sqlalchemy import create_engine as _sa_engine
from sqlmodel import Session, SQLModel

from backend.scrapers.trademe import TradeMeScraper
from backend.scrapers.base import ScrapedJob
from backend.database.models import Job, RolePriority
from backend.core.matcher import classify_role
from backend.agents.scan_agent import ScanAgent


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def scraper() -> TradeMeScraper:
    return TradeMeScraper()


@pytest.fixture(scope="module")
def fixture_html() -> str:
    path = Path(__file__).parent / "fixtures" / "trademe_results.html"
    return path.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def parsed_jobs(scraper, fixture_html) -> list[ScrapedJob]:
    return scraper._parse_page(fixture_html)


@pytest.fixture
def db_session():
    """In-memory SQLite session for storage tests."""
    engine = _sa_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)


# ── Parser: count and structure ───────────────────────────────────────────────


def test_parse_returns_three_valid_jobs(parsed_jobs):
    """Cards 4 and 5 in the fixture are malformed and must be skipped."""
    assert len(parsed_jobs) == 3


def test_all_results_are_scraped_job_instances(parsed_jobs):
    for job in parsed_jobs:
        assert isinstance(job, ScrapedJob)


def test_source_is_trademe(parsed_jobs):
    for job in parsed_jobs:
        assert job.source == "trademe"


# ── Parser: field extraction ──────────────────────────────────────────────────


def test_title_extraction(parsed_jobs):
    titles = [j.title for j in parsed_jobs]
    assert "Packhouse Worker" in titles
    assert "Warehouse Operator" in titles
    assert "General Labourer" in titles


def test_employer_extraction(parsed_jobs):
    employers = [j.employer for j in parsed_jobs]
    assert "Zespri International" in employers
    assert "NZ Post" in employers
    assert "Build Corp NZ" in employers


def test_location_extraction(parsed_jobs):
    packhouse = next(j for j in parsed_jobs if j.title == "Packhouse Worker")
    assert packhouse.location == "Te Puke, Bay Of Plenty"


def test_salary_extracted_when_present(parsed_jobs):
    packhouse = next(j for j in parsed_jobs if j.title == "Packhouse Worker")
    assert packhouse.salary_text is not None
    assert "$22" in packhouse.salary_text


def test_salary_is_none_when_absent(parsed_jobs):
    warehouse = next(j for j in parsed_jobs if j.title == "Warehouse Operator")
    assert warehouse.salary_text is None


def test_description_extracted_when_present(parsed_jobs):
    packhouse = next(j for j in parsed_jobs if j.title == "Packhouse Worker")
    assert packhouse.description is not None
    assert "kiwifruit" in packhouse.description.lower()


def test_description_is_none_when_absent(parsed_jobs):
    warehouse = next(j for j in parsed_jobs if j.title == "Warehouse Operator")
    assert warehouse.description is None


def test_url_contains_trademe_domain(parsed_jobs):
    for job in parsed_jobs:
        assert "trademe.co.nz" in job.url


def test_url_has_no_tracking_params(parsed_jobs):
    """The rsqid tracking param must be stripped from the canonical URL."""
    for job in parsed_jobs:
        assert "rsqid" not in job.url
        assert "?" not in job.url


def test_url_contains_listing_id(parsed_jobs):
    packhouse = next(j for j in parsed_jobs if j.title == "Packhouse Worker")
    assert "5981029311" in packhouse.url
    assert packhouse.url == "https://www.trademe.co.nz/a/jobs/agriculture-fishing-forestry/horticulture/bay-of-plenty/te-puke/full-time/listing/5981029311"


# ── Listing ID extraction ─────────────────────────────────────────────────────


def test_extract_id_from_full_path(scraper):
    href = "/a/jobs/agriculture-fishing-forestry/horticulture/bay-of-plenty/listing/5981029311"
    assert scraper._extract_listing_id(href) == "5981029311"


def test_extract_id_strips_query_params(scraper):
    href = "/a/jobs/transport-logistics/listing/6010827670?rsqid=abc123&type=standard"
    assert scraper._extract_listing_id(href) == "6010827670"


def test_extract_id_returns_none_for_non_listing_path(scraper):
    assert scraper._extract_listing_id("/a/jobs/other/some-path") is None


def test_extract_id_returns_none_for_empty_string(scraper):
    assert scraper._extract_listing_id("") is None


def test_external_id_matches_extracted_listing_id(parsed_jobs):
    packhouse = next(j for j in parsed_jobs if j.title == "Packhouse Worker")
    assert packhouse.external_id == "5981029311"


# ── Role classification (shared core, sanity checks) ─────────────────────────


def test_classify_p1_packhouse():
    assert classify_role("Packhouse Worker") == RolePriority.P1


def test_classify_p2_warehouse():
    assert classify_role("Warehouse Operator") == RolePriority.P2


def test_classify_p3_labourer():
    assert classify_role("General Labourer") == RolePriority.P3


# ── DB storage: trademe jobs stored and deduplicated ─────────────────────────


def make_scraped(external_id="tm-test-001", title="Packhouse Worker") -> ScrapedJob:
    return ScrapedJob(
        external_id=external_id,
        source="trademe",
        title=title,
        employer="Test Employer NZ",
        location="Auckland, Auckland",
        url=f"https://www.trademe.co.nz/a/jobs/listing/{external_id}",
        salary_text="$22/hr",
        description="Entry-level packhouse work. Overseas applicants welcome.",
    )


def test_store_new_trademe_job(db_session):
    agent = ScanAgent()
    new, changed, _ = agent._store_scraped_jobs(db_session, [make_scraped()])
    assert new == 1
    assert changed == 0


def test_stored_job_has_trademe_source(db_session):
    agent = ScanAgent()
    agent._store_scraped_jobs(db_session, [make_scraped()])
    import sqlmodel
    job = db_session.exec(sqlmodel.select(Job)).first()
    assert job.source == "trademe"


def test_stored_job_gets_role_priority(db_session):
    agent = ScanAgent()
    agent._store_scraped_jobs(db_session, [make_scraped(title="Packhouse Worker")])
    import sqlmodel
    job = db_session.exec(sqlmodel.select(Job)).first()
    assert job.role_priority == RolePriority.P1


def test_trademe_duplicate_not_stored_twice(db_session):
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


def test_seek_and_trademe_same_id_not_deduplicated(db_session):
    """Same external_id from seek and trademe are treated as separate jobs."""
    agent = ScanAgent()
    seek_job = ScrapedJob(
        external_id="12345",
        source="seek",
        title="Packhouse Worker",
        employer="Employer A",
        location="Auckland",
        url="https://seek.co.nz/job/12345",
    )
    tm_job = make_scraped("12345")  # same id, different source
    new, _, __ = agent._store_scraped_jobs(db_session, [seek_job, tm_job])
    assert new == 2


def test_multiple_trademe_jobs_all_stored(db_session):
    agent = ScanAgent()
    jobs = [make_scraped(f"tm-{i}") for i in range(4)]
    new, _, __ = agent._store_scraped_jobs(db_session, jobs)
    assert new == 4
