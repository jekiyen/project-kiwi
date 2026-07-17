"""
Tests for the SeasonalJobs NZ scraper.

All tests use local fixture HTML — no network requests are made.
Only _parse_page() and _parse_card() are tested directly.
"""
from pathlib import Path

import pytest
from sqlalchemy import create_engine as _sa_engine
from sqlmodel import Session, SQLModel

from backend.scrapers.seasonal import SeasonalJobsScraper
from backend.scrapers.base import ScrapedJob
from backend.database.models import Job, RolePriority
from backend.core.matcher import classify_role
from backend.agents.scan_agent import ScanAgent


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def scraper() -> SeasonalJobsScraper:
    return SeasonalJobsScraper()


@pytest.fixture(scope="module")
def fixture_html() -> str:
    path = Path(__file__).parent / "fixtures" / "seasonal_results.html"
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
    """Cards 4 (non-numeric id) and 5 (no job_search_title link) must be skipped."""
    assert len(parsed_jobs) == 3


def test_all_results_are_scraped_job_instances(parsed_jobs):
    for job in parsed_jobs:
        assert isinstance(job, ScrapedJob)


def test_source_is_seasonal(parsed_jobs):
    for job in parsed_jobs:
        assert job.source == "seasonal"


# ── Parser: field extraction ──────────────────────────────────────────────────


def test_title_extraction(parsed_jobs):
    titles = [j.title for j in parsed_jobs]
    assert "Harvest 2026 packhouse workers needed" in titles
    assert "Kiwifruit Flower Picking Great $$$$" in titles
    assert "Tray Making" in titles


def test_employer_extraction(parsed_jobs):
    packhouse = next(j for j in parsed_jobs if "packhouse" in j.title.lower())
    assert packhouse.employer == "Zespri Bay of Plenty"

    kiwifruit = next(j for j in parsed_jobs if "Kiwifruit Flower" in j.title)
    assert kiwifruit.employer == "Ecowolf"


def test_employer_is_unknown_when_absent(parsed_jobs):
    tray = next(j for j in parsed_jobs if j.title == "Tray Making")
    assert tray.employer == "Unknown"


def test_location_extraction(parsed_jobs):
    packhouse = next(j for j in parsed_jobs if "packhouse" in j.title.lower())
    assert "Te Puke" in packhouse.location

    kiwifruit = next(j for j in parsed_jobs if "Kiwifruit Flower" in j.title)
    assert "Pukehina" in kiwifruit.location


def test_url_contains_seasonaljobs_domain(parsed_jobs):
    for job in parsed_jobs:
        assert "seasonaljobs.co.nz" in job.url


def test_url_format(parsed_jobs):
    packhouse = next(j for j in parsed_jobs if "packhouse" in j.title.lower())
    assert packhouse.url == "https://seasonaljobs.co.nz/46/Harvest-2026-packhouse-workers-needed"


def test_no_salary_field(parsed_jobs):
    for job in parsed_jobs:
        assert job.salary_text is None


# ── External ID ───────────────────────────────────────────────────────────────


def test_external_id_is_numeric_string(parsed_jobs):
    for job in parsed_jobs:
        assert job.external_id.isdigit()


def test_external_id_matches_previewbox_id(parsed_jobs):
    packhouse = next(j for j in parsed_jobs if "packhouse" in j.title.lower())
    assert packhouse.external_id == "46"

    kiwifruit = next(j for j in parsed_jobs if "Kiwifruit Flower" in j.title)
    assert kiwifruit.external_id == "16"


def test_external_ids_are_unique(parsed_jobs):
    ids = [j.external_id for j in parsed_jobs]
    assert len(ids) == len(set(ids))


# ── Role classification ───────────────────────────────────────────────────────


def test_classify_p1_packhouse():
    assert classify_role("Harvest 2026 packhouse workers needed") == RolePriority.P1


def test_classify_p1_kiwifruit_flower_picking():
    assert classify_role("Kiwifruit Flower Picking Great $$$$") == RolePriority.P1


# ── DB storage ────────────────────────────────────────────────────────────────


def make_scraped(external_id="46", title="Harvest 2026 packhouse workers needed") -> ScrapedJob:
    return ScrapedJob(
        external_id=external_id,
        source="seasonal",
        title=title,
        employer="Zespri Bay of Plenty",
        location="Te Puke, North Island New Zealand",
        url=f"https://seasonaljobs.co.nz/{external_id}/Harvest-2026-packhouse-workers-needed",
    )


def test_store_new_seasonal_job(db_session):
    agent = ScanAgent()
    new, changed, _ = agent._store_scraped_jobs(db_session, [make_scraped()])
    assert new == 1
    assert changed == 0


def test_stored_job_has_seasonal_source(db_session):
    agent = ScanAgent()
    agent._store_scraped_jobs(db_session, [make_scraped()])
    import sqlmodel
    job = db_session.exec(sqlmodel.select(Job)).first()
    assert job.source == "seasonal"


def test_seasonal_duplicate_not_stored_twice(db_session):
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


def test_seasonal_and_seek_same_id_not_deduplicated(db_session):
    """Same external_id from seasonal and seek must be stored as separate jobs."""
    agent = ScanAgent()
    seek_job = ScrapedJob(
        external_id="46",
        source="seek",
        title="Packhouse Worker",
        employer="Employer A",
        location="Te Puke",
        url="https://seek.co.nz/job/46",
    )
    seasonal_job = make_scraped("46")
    new, _, __ = agent._store_scraped_jobs(db_session, [seek_job, seasonal_job])
    assert new == 2


def test_multiple_seasonal_jobs_all_stored(db_session):
    agent = ScanAgent()
    jobs = [make_scraped(str(i), f"Seasonal Job {i}") for i in range(10, 13)]
    new, _, __ = agent._store_scraped_jobs(db_session, jobs)
    assert new == 3


# ── Listing URL validation guard ──────────────────────────────────────────────

def test_card_linking_to_category_page_is_skipped(scraper):
    """A card whose link resolves to one of the scraped category/homepage
    URLs (rather than a specific job) must never be stored — see
    backend/core/listing_url.py."""
    html = """
    <div class="previewBox" id="999">
      <a class="job_search_title" href="https://seasonaljobs.co.nz/farm-work-jobs/">Some Job</a>
      <div class="cname">Some Employer</div>
      <div class="location">Bay of Plenty</div>
    </div>
    """
    jobs = scraper._parse_page(html)
    assert jobs == []
