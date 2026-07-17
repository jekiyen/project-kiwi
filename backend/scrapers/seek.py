"""
SEEK NZ scraper.

Selectors use SEEK's data-automation attributes, which have been stable across
major redesigns. If results suddenly drop to zero, check _parse_card() first.
"""
import asyncio
import logging
import re
from typing import Optional
from urllib.parse import quote_plus

from bs4 import BeautifulSoup, Tag

from backend.scrapers.base import BaseScraper, ScrapedJob

logger = logging.getLogger("scanner")

BASE_URL = "https://www.seek.co.nz"
SEARCH_URL = BASE_URL + "/jobs?keywords={query}&where=All+New+Zealand&sortmode=ListedDate"

# One search term per target-role cluster to cover all priority categories.
SEARCH_TERMS: list[str] = [
    "packhouse worker",   # P1
    "fruit picker",       # P1
    "orchard worker",     # P1
    "farm worker",        # P1
    "warehouse",          # P2
    "manufacturing",      # P2
    "factory worker",     # P2
    "construction labourer",  # P3
    "general labourer",   # P3
]

_JOB_ID_RE = re.compile(r"/job/(\d+)")


class SeekScraper(BaseScraper):
    source_name = "seek"

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
                for term in SEARCH_TERMS:
                    try:
                        html = await self._fetch_html(page, term)
                        jobs = self._parse_page(html)
                        for job in jobs:
                            if job.external_id not in seen_ids:
                                seen_ids.add(job.external_id)
                                all_jobs.append(job)
                        logger.info("SEEK '%s' → %d unique job(s)", term, len(jobs))
                        await asyncio.sleep(2)  # respectful pacing
                    except Exception as exc:
                        logger.error("SEEK: error on term '%s': %s", term, exc)
            finally:
                await browser.close()

        logger.info("SEEK: %d unique jobs collected across all terms", len(all_jobs))
        return all_jobs

    async def is_accessible(self) -> bool:
        from playwright.async_api import async_playwright

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                response = await page.goto(BASE_URL, timeout=15_000)
                await browser.close()
                return response is not None and response.status < 400
        except Exception:
            return False

    # ── Internal ──────────────────────────────────────────────────────────────

    async def _fetch_html(self, page, term: str) -> str:
        url = SEARCH_URL.format(query=quote_plus(term))
        await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        await page.wait_for_timeout(2_000)  # allow JS results to render
        return await page.content()

    def _parse_page(self, html: str) -> list[ScrapedJob]:
        """Parse job cards from raw HTML. Separated from Playwright for testability."""
        soup = BeautifulSoup(html, "html.parser")
        cards = soup.select('[data-automation="normalJob"]')
        jobs = []
        for card in cards:
            job = self._parse_card(card)
            if job:
                jobs.append(job)
        return jobs

    def _parse_card(self, card: Tag) -> Optional[ScrapedJob]:
        try:
            title_el = card.select_one('[data-automation="jobTitle"]')
            if not title_el:
                return None
            title = title_el.get_text(strip=True)
            href = str(title_el.get("href", ""))
            job_id = self._extract_job_id(href)
            if not job_id:
                return None

            company_el = card.select_one('[data-automation="jobCompany"]')
            employer = company_el.get_text(strip=True) if company_el else "Unknown"

            # SEEK uses different data-automation values across page variants
            location_el = (
                card.select_one('[data-automation="jobCardLocation"]')
                or card.select_one('[data-automation="jobLocation"]')
            )
            location = location_el.get_text(strip=True) if location_el else "New Zealand"

            salary_el = card.select_one('[data-automation="jobSalary"]')
            salary_text = salary_el.get_text(strip=True) if salary_el else None

            url = f"{BASE_URL}/job/{job_id}"
            from backend.core.listing_url import is_exact_listing_url
            if not is_exact_listing_url(self.source_name, url):
                logger.warning("SEEK: skipping card with non-listing URL: %s", url)
                return None

            return ScrapedJob(
                external_id=job_id,
                source=self.source_name,
                title=title,
                employer=employer,
                location=location,
                url=url,
                salary_text=salary_text,
                raw_data={"seek_href": href},
            )
        except Exception as exc:
            logger.warning("SEEK: failed to parse card: %s", exc)
            return None

    @staticmethod
    def _extract_job_id(href: str) -> Optional[str]:
        m = _JOB_ID_RE.search(href)
        return m.group(1) if m else None
