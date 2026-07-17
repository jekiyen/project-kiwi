"""
Tests for the PickNZ scraper.

All tests use local fixture HTML — no network requests are made.
Only _parse_page() and _parse_row() are tested directly.
"""
from pathlib import Path

import pytest
from sqlalchemy import create_engine as _sa_engine
from sqlmodel import Session, SQLModel

from backend.scrapers.picknz import PickNZScraper
from backend.scrapers.base import ScrapedJob
from backend.database.models import Job, RolePriority
from backend.core.matcher import classify_role
from backend.agents.scan_agent import ScanAgent


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def scraper() -> PickNZScraper:
    return PickNZScraper()


@pytest.fixture(scope="module")
def fixture_html() -> str:
    path = Path(__file__).parent / "fixtures" / "picknz_results.html"
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
    """Rows 4 (no link) and 5 (relative href) must be skipped."""
    assert len(parsed_jobs) == 3


def test_all_results_are_scraped_job_instances(parsed_jobs):
    for job in parsed_jobs:
        assert isinstance(job, ScrapedJob)


def test_source_is_picknz(parsed_jobs):
    for job in parsed_jobs:
        assert job.source == "picknz"


# ── Parser: field extraction ──────────────────────────────────────────────────


def test_title_extraction(parsed_jobs):
    titles = [j.title for j in parsed_jobs]
    assert "Kiwifruit Winter Pruning" in titles
    assert "Packhouse Sorter" in titles
    assert "Apple Picker" in titles


def test_employer_extraction(parsed_jobs):
    pruning = next(j for j in parsed_jobs if j.title == "Kiwifruit Winter Pruning")
    assert pruning.employer == "Bay of Plenty Orchards Ltd"

    sorter = next(j for j in parsed_jobs if j.title == "Packhouse Sorter")
    assert sorter.employer == "Zespri Pack Ltd"


def test_employer_is_unknown_when_absent(parsed_jobs):
    picker = next(j for j in parsed_jobs if j.title == "Apple Picker")
    assert picker.employer == "Unknown"


def test_location_extraction(parsed_jobs):
    pruning = next(j for j in parsed_jobs if j.title == "Kiwifruit Winter Pruning")
    assert "Te Puke" in pruning.location
    assert "Bay of Plenty" in pruning.location


def test_location_strips_need_staff_now(parsed_jobs):
    """'Need Staff Now' sub-text must be removed from location."""
    pruning = next(j for j in parsed_jobs if j.title == "Kiwifruit Winter Pruning")
    assert "Need Staff Now" not in pruning.location


def test_location_strips_icon_text(parsed_jobs):
    """Icon spans must not bleed into the location string."""
    for job in parsed_jobs:
        assert job.location.strip() != ""
        # Icon element text should not appear in location
        assert "wpjb-icon" not in job.location


def test_url_is_absolute(parsed_jobs):
    for job in parsed_jobs:
        assert job.url.startswith("https://jobs.picknz.co.nz/")


def test_no_salary_field(parsed_jobs):
    for job in parsed_jobs:
        assert job.salary_text is None


# ── External ID from URL slug ─────────────────────────────────────────────────


def test_external_id_is_url_slug(parsed_jobs):
    pruning = next(j for j in parsed_jobs if j.title == "Kiwifruit Winter Pruning")
    assert pruning.external_id == "kiwifruit-winter-pruning-4"


def test_external_id_differs_per_job(parsed_jobs):
    ids = [j.external_id for j in parsed_jobs]
    assert len(ids) == len(set(ids))


# ── Role classification ───────────────────────────────────────────────────────


def test_classify_p1_kiwifruit_pruning():
    assert classify_role("Kiwifruit Winter Pruning") == RolePriority.P1


def test_classify_p1_packhouse_sorter():
    assert classify_role("Packhouse Sorter") == RolePriority.P1


def test_classify_p1_apple_picker():
    assert classify_role("Apple Picker") == RolePriority.P1


# ── DB storage ────────────────────────────────────────────────────────────────


def make_scraped(external_id="kiwifruit-winter-pruning-4", title="Kiwifruit Winter Pruning") -> ScrapedJob:
    return ScrapedJob(
        external_id=external_id,
        source="picknz",
        title=title,
        employer="Bay of Plenty Orchards Ltd",
        location="Te Puke, Bay of Plenty",
        url=f"https://jobs.picknz.co.nz/job/{external_id}/",
    )


def test_store_new_picknz_job(db_session):
    agent = ScanAgent()
    new, changed, _ = agent._store_scraped_jobs(db_session, [make_scraped()])
    assert new == 1
    assert changed == 0


def test_stored_job_has_picknz_source(db_session):
    agent = ScanAgent()
    agent._store_scraped_jobs(db_session, [make_scraped()])
    import sqlmodel
    job = db_session.exec(sqlmodel.select(Job)).first()
    assert job.source == "picknz"


def test_picknz_duplicate_not_stored_twice(db_session):
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


def test_picknz_and_seek_same_id_not_deduplicated(db_session):
    """Same external_id from picknz and seek must be stored as separate jobs."""
    agent = ScanAgent()
    seek_job = ScrapedJob(
        external_id="kiwifruit-winter-pruning-4",
        source="seek",
        title="Kiwifruit Winter Pruning",
        employer="Employer A",
        location="Te Puke",
        url="https://seek.co.nz/job/12345",
    )
    picknz_job = make_scraped("kiwifruit-winter-pruning-4")
    new, _, __ = agent._store_scraped_jobs(db_session, [seek_job, picknz_job])
    assert new == 2


def test_multiple_picknz_jobs_all_stored(db_session):
    agent = ScanAgent()
    jobs = [make_scraped(f"job-slug-{i}") for i in range(3)]
    new, _, __ = agent._store_scraped_jobs(db_session, jobs)
    assert new == 3


# ── Listing URL validation guard ──────────────────────────────────────────────

def test_card_linking_to_listing_index_is_skipped(scraper):
    """A card whose link resolves to the listing-index page itself (rather
    than a specific job) must never be stored — see backend/core/listing_url.py."""
    html = """
    <table><tbody class="wpjb-job-list"><tr>
      <td class="wpjb-column-title">
        <a href="https://jobs.picknz.co.nz/">Some Job Title</a>
        <span class="wpjb-sub">Some Employer</span>
      </td>
      <td class="wpjb-column-location">Auckland</td>
    </tr></tbody></table>
    """
    jobs = scraper._parse_page(html)
    assert jobs == []
