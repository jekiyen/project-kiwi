"""Deterministic classification of whether a Job's stored URL is the exact,
specific job-listing page — never a search/category/homepage. Used to decide
whether "Launch Application" can safely open `Job.url` directly, or whether
Kiwi should show an honest "exact listing unavailable" state instead of
silently opening the wrong page.

This only validates the *shape* of a URL already captured by a scraper — it
never reconstructs or guesses a URL, and it cannot detect that a
well-formed, once-correct listing has since expired on the third-party site
(that would require probing the live page, which Kiwi does not do). See
docs/ROADMAP.md "Application Flow Reliability & Assisted Autofill" milestone.
"""
import re
from urllib.parse import quote_plus, urlparse

# Each pattern matches the portion of a URL that only ever appears on a
# genuine per-job detail page for that source — never on a search or
# category page. Derived from real scraped rows (not guessed): e.g. Trade
# Me listings always end in /listing/<digits>, Seasonal Jobs listings are
# always /<digits>/<slug>.
_EXACT_PATTERNS: dict[str, re.Pattern] = {
    "seek": re.compile(r"/job/\d+"),
    "trademe": re.compile(r"/listing/\d+"),
    "indeed": re.compile(r"[?&]jk=[0-9a-f]+", re.IGNORECASE),
    "picknz": re.compile(r"/job/[^/?#]+/?$"),
    "backpacker": re.compile(r"new-zealand-jobs\d+\.html"),
    "seasonal": re.compile(r"/\d+/[^/?#]+"),
}


def _category_roots() -> dict[str, set[str]]:
    """Search/listing-index root pages that must never count as an exact
    listing, even if a URL loosely matches a pattern above. Imported lazily
    (function-local) to avoid a module-level import cycle — these scraper
    modules only import backend.core.listing_url inside method bodies."""
    from backend.scrapers import backpacker, picknz, seasonal

    return {
        "seasonal": set(seasonal.SCRAPE_URLS),
        "picknz": {picknz.LISTING_URL},
        "backpacker": {backpacker.LISTING_URL},
    }


def is_exact_listing_url(source: str, url: str | None) -> bool:
    """True only when `url` looks like a specific job's own detail page for
    `source` — never a search/category/homepage."""
    if not url:
        return False

    normalized = url.rstrip("/")
    for root in _category_roots().get(source, set()):
        if normalized == root.rstrip("/"):
            return False

    pattern = _EXACT_PATTERNS.get(source)
    if pattern is None:
        # Unknown source — fall back to "not just a bare domain," so a
        # homepage link can never count as exact even without a known
        # pattern to check.
        return bool(urlparse(url).path.strip("/"))
    return bool(pattern.search(url))


def build_fallback_link(source: str, title: str) -> tuple[str, bool]:
    """When the exact listing can't be resolved, build the best manual
    fallback: a real keyword search on the source (is_search=True) if the
    source has a working query-based search, otherwise just that source's
    listing/browse page (is_search=False). Never a fabricated per-job URL.
    """
    from backend.scrapers import backpacker, indeed, picknz, seasonal, seek, trademe

    search_templates: dict[str, str] = {
        "seek": seek.SEARCH_URL,
        "trademe": trademe.SEARCH_URL,
        "indeed": indeed.SEARCH_URL,
    }
    browse_urls: dict[str, str] = {
        "picknz": picknz.LISTING_URL,
        "backpacker": backpacker.LISTING_URL,
        "seasonal": seasonal.BASE_URL + "/",
    }

    template = search_templates.get(source)
    if template:
        return template.format(query=quote_plus(title)), True
    return browse_urls.get(source, ""), False
