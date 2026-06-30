"""
PickNZ Jobs scraper — jobs.picknz.co.nz

WordPress WPJB job board. All listings appear on a single page,
so one request is sufficient. Selectors target WPJB's standard BEM
class structure which has been stable across recent site versions.
"""
import logging
from typing import Optional
from urllib.parse import urlparse

from bs4 import BeautifulSoup, Tag

from backend.scrapers.base import BaseScraper, ScrapedJob

logger = logging.getLogger("scanner")

LISTING_URL = "https://jobs.picknz.co.nz/"


class PickNZScraper(BaseScraper):
    source_name = "picknz"

    async def scrape(self) -> list[ScrapedJob]:
        from playwright.async_api import async_playwright

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
                html = await self._fetch_html(page)
                jobs = self._parse_page(html)
                logger.info("PickNZ: %d jobs collected", len(jobs))
                return jobs
            finally:
                await browser.close()

    async def is_accessible(self) -> bool:
        from playwright.async_api import async_playwright

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                response = await page.goto(LISTING_URL, timeout=15_000)
                await browser.close()
                return response is not None and response.status < 400
        except Exception:
            return False

    # ── Internal ──────────────────────────────────────────────────────────────

    async def _fetch_html(self, page) -> str:
        await page.goto(LISTING_URL, wait_until="networkidle", timeout=30_000)
        return await page.content()

    def _parse_page(self, html: str) -> list[ScrapedJob]:
        """Parse job rows. Separated from Playwright for testability."""
        soup = BeautifulSoup(html, "html.parser")
        rows = soup.select("tbody.wpjb-job-list tr")
        jobs = []
        for row in rows:
            job = self._parse_row(row)
            if job:
                jobs.append(job)
        return jobs

    def _parse_row(self, row: Tag) -> Optional[ScrapedJob]:
        try:
            title_el = row.select_one(".wpjb-column-title a")
            if not title_el:
                return None
            title = title_el.get_text(strip=True)
            if not title:
                return None

            url = str(title_el.get("href", "")).strip()
            if not url or not url.startswith("http"):
                return None

            # External ID from the final URL slug: /job/{slug}/
            slug = urlparse(url).path.rstrip("/").split("/")[-1]
            if not slug:
                return None

            employer_el = row.select_one(".wpjb-column-title .wpjb-sub")
            employer = employer_el.get_text(strip=True) if employer_el else "Unknown"

            location_el = row.select_one(".wpjb-column-location")
            location = "New Zealand"
            if location_el:
                # Remove icon elements and sub-text like "Need Staff Now"
                for sub in location_el.select(".wpjb-sub, i, span"):
                    sub.decompose()
                location = location_el.get_text(strip=True) or "New Zealand"

            return ScrapedJob(
                external_id=slug,
                source=self.source_name,
                title=title,
                employer=employer,
                location=location,
                url=url,
            )
        except Exception as exc:
            logger.warning("PickNZ: failed to parse row: %s", exc)
            return None
