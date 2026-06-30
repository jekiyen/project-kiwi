"""
Tests for the Indeed NZ scraper.

All tests use local fixture HTML — no network requests are made.
Only _parse_page() and _parse_card() are tested directly.
"""
from pathlib import Path

import pytest
from sqlalchemy import create_engine as _sa_engine
from sqlmodel import Session, SQLModel

from backend.scrapers.indeed import IndeedScraper
from backend.scrapers.base import ScrapedJob
from backend.database.models import Job, RolePriority
from backend.core.matcher import classify_role
from backend.agents.scan_agent import ScanAgent


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def scraper() -> IndeedScraper:
    return IndeedScraper()


@pytest.fixture(scope="module")
def fixture_html() -> str:
    path = Path(__file__).parent / "fixtures" / "indeed_results.html"
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
    """Cards 4 (no jcs-JobTitle) and 5 (empty data-jk) must be skipped."""
    assert len(parsed_jobs) == 3


def test_all_results_are_scraped_job_instances(parsed_jobs):
    for job in parsed_jobs:
        assert isinstance(job, ScrapedJob)


def test_source_is_indeed(parsed_jobs):
    for job in parsed_jobs:
        assert job.source == "indeed"


# ── Parser: field extraction ──────────────────────────────────────────────────


def test_title_extraction(parsed_jobs):
    titles = [j.title for j in parsed_jobs]
    assert any("Farm Worker" in t for t in titles)
    assert any("General Labourer" in t for t in titles)
    assert any("Packhouse Operator" in t for t in titles)


def test_employer_extraction(parsed_jobs):
    farm = next(j for j in parsed_jobs if "Farm Worker" in j.title)
    assert farm.employer == "Green Valley Farms Ltd"

    labourer = next(j for j in parsed_jobs if "General Labourer" in j.title)
    assert labourer.employer == "BuildRight NZ"


def test_employer_is_unknown_when_absent(parsed_jobs):
    packhouse = next(j for j in parsed_jobs if "Packhouse Operator" in j.title)
    assert packhouse.employer == "Unknown"


def test_location_extraction(parsed_jobs):
    farm = next(j for j in parsed_jobs if "Farm Worker" in j.title)
    assert "Hamilton" in farm.location or "Waikato" in farm.location

    labourer = next(j for j in parsed_jobs if "General Labourer" in j.title)
    assert "Auckland" in labourer.location


def test_url_format(parsed_jobs):
    for job in parsed_jobs:
        assert job.url.startswith("https://nz.indeed.com/viewjob?jk=")
        assert len(job.url) > len("https://nz.indeed.com/viewjob?jk=")


def test_url_contains_job_key(parsed_jobs):
    farm = next(j for j in parsed_jobs if "Farm Worker" in j.title)
    assert farm.external_id in farm.url
    assert farm.url == f"https://nz.indeed.com/viewjob?jk={farm.external_id}"


def test_url_does_not_contain_tracking_path(parsed_jobs):
    """URL must be the canonical viewjob URL, not the /rc/clk tracking redirect."""
    for job in parsed_jobs:
        assert "/rc/clk" not in job.url


def test_no_salary_field(parsed_jobs):
    for job in parsed_jobs:
        assert job.salary_text is None


# ── External ID (job key) ─────────────────────────────────────────────────────


def test_external_id_is_jk_value(parsed_jobs):
    farm = next(j for j in parsed_jobs if "Farm Worker" in j.title)
    assert farm.external_id == "c6f05a3eaf67c494"


def test_external_ids_are_unique(parsed_jobs):
    ids = [j.external_id for j in parsed_jobs]
    assert len(ids) == len(set(ids))


def test_external_id_is_nonempty(parsed_jobs):
    for job in parsed_jobs:
        assert job.external_id


# ── Role classification ───────────────────────────────────────────────────────


def test_classify_p1_farm_worker():
    assert classify_role("Farm Worker") == RolePriority.P1


def test_classify_p3_general_labourer():
    assert classify_role("General Labourer") == RolePriority.P3


def test_classify_p1_packhouse_operator():
    assert classify_role("Packhouse Operator") == RolePriority.P1


# ── DB storage ────────────────────────────────────────────────────────────────


def make_scraped(external_id="c6f05a3eaf67c494", title="Farm Worker") -> ScrapedJob:
    return ScrapedJob(
        external_id=external_id,
        source="indeed",
        title=title,
        employer="Green Valley Farms Ltd",
        location="Hamilton, Waikato",
        url=f"https://nz.indeed.com/viewjob?jk={external_id}",
    )


def test_store_new_indeed_job(db_session):
    agent = ScanAgent()
    new, changed, _ = agent._store_scraped_jobs(db_session, [make_scraped()])
    assert new == 1
    assert changed == 0


def test_stored_job_has_indeed_source(db_session):
    agent = ScanAgent()
    agent._store_scraped_jobs(db_session, [make_scraped()])
    import sqlmodel
    job = db_session.exec(sqlmodel.select(Job)).first()
    assert job.source == "indeed"


def test_indeed_duplicate_not_stored_twice(db_session):
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


def test_indeed_and_seek_same_id_not_deduplicated(db_session):
    """Same job key appearing in both indeed and seek must be stored as separate jobs."""
    agent = ScanAgent()
    seek_job = ScrapedJob(
        external_id="c6f05a3eaf67c494",
        source="seek",
        title="Farm Worker",
        employer="Employer A",
        location="Waikato",
        url="https://seek.co.nz/job/c6f05a3eaf67c494",
    )
    indeed_job = make_scraped("c6f05a3eaf67c494")
    new, _, __ = agent._store_scraped_jobs(db_session, [seek_job, indeed_job])
    assert new == 2


def test_multiple_indeed_jobs_all_stored(db_session):
    agent = ScanAgent()
    jobs = [make_scraped(f"abc{i:09d}", f"Job {i}") for i in range(4)]
    new, _, __ = agent._store_scraped_jobs(db_session, jobs)
    assert new == 4
