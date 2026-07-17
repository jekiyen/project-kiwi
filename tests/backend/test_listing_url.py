"""Tests for backend/core/listing_url.py — the deterministic classifier that
decides whether a Job's stored url is an exact per-listing page (safe to
open for Launch Application) or a search/category page. See docs/ROADMAP.md
"Application Flow Reliability & Assisted Autofill" milestone.
"""
from backend.core.listing_url import build_fallback_link, is_exact_listing_url


# ── is_exact_listing_url — exact listing URLs (real observed shapes) ────────

def test_seek_exact_listing():
    assert is_exact_listing_url("seek", "https://www.seek.co.nz/job/92995285") is True


def test_trademe_exact_listing():
    url = "https://www.trademe.co.nz/a/jobs/agriculture-fishing-forestry/farming/otago/dunedin/full-time/listing/6016040732"
    assert is_exact_listing_url("trademe", url) is True


def test_indeed_exact_listing():
    assert is_exact_listing_url("indeed", "https://nz.indeed.com/viewjob?jk=a02f29e4b8af2184") is True


def test_picknz_exact_listing():
    assert is_exact_listing_url("picknz", "https://jobs.picknz.co.nz/job/kiwifruit-winter-pruning-4/") is True


def test_backpacker_exact_listing():
    url = "https://www.backpackerboard.co.nz/work_jobs/new-zealand-jobs118080.html"
    assert is_exact_listing_url("backpacker", url) is True


def test_seasonal_exact_listing():
    url = "https://seasonaljobs.co.nz/16/Kiwifruit-Flower-Picking-Great-"
    assert is_exact_listing_url("seasonal", url) is True


# ── is_exact_listing_url — generic/category/search pages must be rejected ──

def test_trademe_category_page_rejected():
    url = "https://www.trademe.co.nz/a/jobs/agriculture-fishing-forestry/farming/otago/dunedin"
    assert is_exact_listing_url("trademe", url) is False


def test_trademe_search_page_rejected():
    url = "https://www.trademe.co.nz/a/jobs/search?search_string=farm+worker"
    assert is_exact_listing_url("trademe", url) is False


def test_seek_search_page_rejected():
    url = "https://www.seek.co.nz/jobs?keywords=farm+worker"
    assert is_exact_listing_url("seek", url) is False


def test_indeed_search_page_rejected():
    url = "https://nz.indeed.com/jobs?q=farm+worker&l=New+Zealand"
    assert is_exact_listing_url("indeed", url) is False


def test_picknz_homepage_rejected():
    assert is_exact_listing_url("picknz", "https://jobs.picknz.co.nz/") is False
    assert is_exact_listing_url("picknz", "https://jobs.picknz.co.nz") is False


def test_seasonal_category_root_rejected():
    assert is_exact_listing_url("seasonal", "https://seasonaljobs.co.nz/farm-work-jobs/") is False
    assert is_exact_listing_url("seasonal", "https://seasonaljobs.co.nz/") is False


def test_backpacker_listing_index_rejected():
    url = "https://www.backpackerboard.co.nz/work_jobs/job_listings.php"
    assert is_exact_listing_url("backpacker", url) is False


# ── is_exact_listing_url — edge cases ────────────────────────────────────────

def test_none_url_rejected():
    assert is_exact_listing_url("seek", None) is False


def test_empty_url_rejected():
    assert is_exact_listing_url("seek", "") is False


def test_unknown_source_bare_domain_rejected():
    assert is_exact_listing_url("some_future_source", "https://example.com/") is False


def test_unknown_source_with_path_accepted():
    assert is_exact_listing_url("some_future_source", "https://example.com/jobs/12345") is True


# ── build_fallback_link ──────────────────────────────────────────────────────

def test_fallback_link_for_query_search_sources():
    url, is_search = build_fallback_link("seek", "Farm Worker")
    assert is_search is True
    assert "seek.co.nz" in url
    assert "Farm+Worker" in url or "Farm%20Worker" in url


def test_fallback_link_for_trademe():
    url, is_search = build_fallback_link("trademe", "Farm Worker - Fixed Term")
    assert is_search is True
    assert "trademe.co.nz" in url


def test_fallback_link_for_browse_only_sources():
    url, is_search = build_fallback_link("picknz", "Anything")
    assert is_search is False
    assert url == "https://jobs.picknz.co.nz/"


def test_fallback_link_for_seasonal_is_browse_only():
    url, is_search = build_fallback_link("seasonal", "Anything")
    assert is_search is False
    assert url == "https://seasonaljobs.co.nz/"


def test_fallback_link_unknown_source_returns_empty():
    url, is_search = build_fallback_link("mystery_source", "Anything")
    assert url == ""
    assert is_search is False
