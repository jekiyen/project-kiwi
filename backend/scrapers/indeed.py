"""
Indeed NZ scraper — nz.indeed.com

Indeed uses a mix of server-rendered and client-hydrated HTML.
Job cards are present at domcontentloaded; a short selector wait
ensures JS hydration completes before parsing.

Cloudflare may block some search terms. Blocked pages are detected by
the "Just a moment" challenge text and silently skipped.
"""
import asyncio
import logging
from typing import Optional
from urllib.parse import quote_plus

from bs4 import BeautifulSoup, Tag

from backend.scrapers.base import BaseScraper, ScrapedJob

logger = logging.getLogger("scanner")

BASE_URL = "https://nz.indeed.com"
SEARCH_URL = BASE_URL + "/jobs?q={query}&l=New+Zealand"

SEARCH_TERMS: list[str] = [
    "farm worker",            # P1
    "orchard worker",         # P1
    "fruit picker",           # P1
    "packhouse",              # P1
    "labourer",               # P3
    "warehouse",              # P2
    "factory worker",         # P2
    "construction labourer",  # P3
    "manufacturing",          # P2
]


class IndeedScraper(BaseScraper):
    source_name = "indeed"

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
                        if "Just a moment" in html or "cf-browser-verification" in html:
                            logger.warning("Indeed: Cloudflare block on '%s', skipping", term)
                            await asyncio.sleep(3)
                            continue
                        jobs = self._parse_page(html)
                        for job in jobs:
                            if job.external_id not in seen_ids:
                                seen_ids.add(job.external_id)
                                all_jobs.append(job)
                        logger.info("Indeed '%s' → %d unique job(s)", term, len(jobs))
                        await asyncio.sleep(2)
                    except Exception as exc:
                        logger.error("Indeed: error on term '%s': %s", term, exc)
            finally:
                await browser.close()

        logger.info("Indeed: %d unique jobs collected", len(all_jobs))
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
        # Indeed hydrates job cards via JS after initial HTML load
        try:
            await page.wait_for_selector(".job_seen_beacon", timeout=5_000)
        except Exception:
            pass
        return await page.content()

    def _parse_page(self, html: str) -> list[ScrapedJob]:
        """Parse job cards. Separated from Playwright for testability."""
        soup = BeautifulSoup(html, "html.parser")
        cards = soup.select(".job_seen_beacon")
        jobs = []
        for card in cards:
            job = self._parse_card(card)
            if job:
                jobs.append(job)
        return jobs

    def _parse_card(self, card: Tag) -> Optional[ScrapedJob]:
        try:
            title_link = card.select_one(".jcs-JobTitle")
            if not title_link:
                return None
            jk = str(title_link.get("data-jk", "")).strip()
            if not jk:
                return None

            # Title span has id="jobTitle-{jk}" or is the first plain span
            title_span = title_link.select_one("span[id^='jobTitle-']")
            if not title_span:
                title_span = title_link.select_one("span")
            if not title_span:
                return None
            title = title_span.get_text(strip=True)
            if not title:
                return None

            employer_el = card.select_one("[data-testid='company-name']")
            employer = employer_el.get_text(strip=True) if employer_el else "Unknown"

            location_el = card.select_one("[data-testid='text-location']")
            location = location_el.get_text(strip=True) if location_el else "New Zealand"

            return ScrapedJob(
                external_id=jk,
                source=self.source_name,
                title=title,
                employer=employer,
                location=location,
                url=f"{BASE_URL}/viewjob?jk={jk}",
            )
        except Exception as exc:
            logger.warning("Indeed: failed to parse card: %s", exc)
            return None
