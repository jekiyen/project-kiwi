"""
Seasonal Jobs NZ scraper — seasonaljobs.co.nz

The site's search form backend is broken (POST → 404). All active listings
are rendered directly on the homepage and on category pages. We scrape the
homepage plus relevant category pages and deduplicate by numeric job ID
(the previewBox container's id attribute).
"""
import logging
from typing import Optional

from bs4 import BeautifulSoup, Tag

from backend.scrapers.base import BaseScraper, ScrapedJob

logger = logging.getLogger("scanner")

BASE_URL = "https://seasonaljobs.co.nz"

# Homepage shows all current listings; category pages cover relevant subsets.
SCRAPE_URLS: list[str] = [
    BASE_URL + "/",
    BASE_URL + "/kiwi-picking-jobs-jobs/",
    BASE_URL + "/fruit-picking-jobs-jobs/",
    BASE_URL + "/farm-work-jobs/",
    BASE_URL + "/labourer-jobs-jobs/",
    BASE_URL + "/construction-jobs/",
]


class SeasonalJobsScraper(BaseScraper):
    source_name = "seasonal"

    async def scrape(self) -> list[ScrapedJob]:
        from playwright.async_api import async_playwright

        all_jobs: list[ScrapedJob] = []
        seen_ids: set[str] = set()

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            )
            page = await context.new_page()
            try:
                for url in SCRAPE_URLS:
                    try:
                        html = await self._fetch_html(page, url)
                        jobs = self._parse_page(html)
                        for job in jobs:
                            if job.external_id not in seen_ids:
                                seen_ids.add(job.external_id)
                                all_jobs.append(job)
                        logger.info("SeasonalJobs '%s' → %d job(s)", url, len(jobs))
                    except Exception as exc:
                        logger.error("SeasonalJobs: error on '%s': %s", url, exc)
            finally:
                await browser.close()

        logger.info("SeasonalJobs: %d unique jobs collected", len(all_jobs))
        return all_jobs

    async def is_accessible(self) -> bool:
        from playwright.async_api import async_playwright

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                response = await page.goto(BASE_URL + "/", timeout=15_000)
                await browser.close()
                return response is not None and response.status < 400
        except Exception:
            return False

    # ── Internal ──────────────────────────────────────────────────────────────

    async def _fetch_html(self, page, url: str) -> str:
        await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        return await page.content()

    def _parse_page(self, html: str) -> list[ScrapedJob]:
        """Parse job cards. Separated from Playwright for testability."""
        soup = BeautifulSoup(html, "html.parser")
        cards = soup.select("div.previewBox")
        jobs = []
        for card in cards:
            job = self._parse_card(card)
            if job:
                jobs.append(job)
        return jobs

    def _parse_card(self, card: Tag) -> Optional[ScrapedJob]:
        try:
            job_id = str(card.get("id", "")).strip()
            if not job_id or not job_id.isdigit():
                return None

            title_el = card.select_one("a.job_search_title")
            if not title_el:
                return None
            title = title_el.get_text(strip=True)
            if not title:
                return None

            url = str(title_el.get("href", "")).strip()
            if not url or not url.startswith("http"):
                return None

            # Defence in depth: never store a card whose link resolves to one
            # of the category/homepage URLs we scrape rather than a specific job.
            from backend.core.listing_url import is_exact_listing_url
            if not is_exact_listing_url(self.source_name, url):
                logger.warning("SeasonalJobs: skipping card with non-listing URL: %s", url)
                return None

            employer_el = card.select_one("div.cname")
            employer = employer_el.get_text(strip=True) if employer_el else "Unknown"

            location_el = card.select_one("div.location")
            location = location_el.get_text(strip=True) if location_el else "New Zealand"

            return ScrapedJob(
                external_id=job_id,
                source=self.source_name,
                title=title,
                employer=employer,
                location=location,
                url=url,
            )
        except Exception as exc:
            logger.warning("SeasonalJobs: failed to parse card: %s", exc)
            return None
