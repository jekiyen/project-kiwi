"""
BackpackerBoard NZ Jobs scraper — backpackerboard.co.nz

Static PHP HTML served without JS rendering. Table rows use alternating
class names rowgrey (featured) and rowlightgrey (regular). Job IDs are
extracted from the listing filename (e.g. new-zealand-jobs118080.html → 118080).
If row counts drop, check for table class or URL pattern changes first.
"""
import logging
import re
from typing import Optional

from bs4 import BeautifulSoup, Tag

from backend.scrapers.base import BaseScraper, ScrapedJob

logger = logging.getLogger("scanner")

BASE_URL = "https://www.backpackerboard.co.nz"
LISTING_URL = BASE_URL + "/work_jobs/job_listings.php"

_JOB_ID_RE = re.compile(r"new-zealand-jobs(\d+)\.html")


class BackpackerBoardScraper(BaseScraper):
    source_name = "backpacker"

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
                logger.info("BackpackerBoard: %d jobs collected", len(jobs))
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
        await page.goto(LISTING_URL, wait_until="domcontentloaded", timeout=30_000)
        return await page.content()

    def _parse_page(self, html: str) -> list[ScrapedJob]:
        """Parse job rows. Separated from Playwright for testability."""
        soup = BeautifulSoup(html, "html.parser")
        rows = soup.select("tr.rowgrey, tr.rowlightgrey")
        jobs = []
        for row in rows:
            job = self._parse_row(row)
            if job:
                jobs.append(job)
        return jobs

    def _parse_row(self, row: Tag) -> Optional[ScrapedJob]:
        try:
            link_el = row.select_one("a[href*='new-zealand-jobs']")
            if not link_el:
                return None

            title = link_el.get_text(strip=True)
            if not title:
                return None

            href = str(link_el.get("href", "")).strip()
            job_id = self._extract_job_id(href)
            if not job_id:
                return None

            url = f"{BASE_URL}/work_jobs/{href}"

            from backend.core.listing_url import is_exact_listing_url
            if not is_exact_listing_url(self.source_name, url):
                logger.warning("BackpackerBoard: skipping row with non-listing URL: %s", url)
                return None

            # Location is in the 3rd table cell (index 2)
            cells = row.find_all("td")
            location = "New Zealand"
            if len(cells) >= 3:
                location = cells[2].get_text(strip=True) or "New Zealand"

            return ScrapedJob(
                external_id=job_id,
                source=self.source_name,
                title=title,
                employer="Unknown",
                location=location,
                url=url,
            )
        except Exception as exc:
            logger.warning("BackpackerBoard: failed to parse row: %s", exc)
            return None

    @staticmethod
    def _extract_job_id(href: str) -> Optional[str]:
        m = _JOB_ID_RE.search(href)
        return m.group(1) if m else None
