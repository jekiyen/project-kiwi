"""
Trade Me Jobs scraper.

Selectors target Trade Me's custom Angular elements and BEM class names, which
have been stable across recent page versions. If result counts drop to zero,
check _parse_card() against the live site first.
"""
import asyncio
import logging
import re
from typing import Optional
from urllib.parse import quote_plus

from bs4 import BeautifulSoup, Tag

from backend.scrapers.base import BaseScraper, ScrapedJob

logger = logging.getLogger("scanner")

BASE_URL = "https://www.trademe.co.nz"
SEARCH_URL = BASE_URL + "/a/jobs/search?search_string={query}"

SEARCH_TERMS: list[str] = [
    "packhouse worker",     # P1
    "fruit picker",         # P1
    "orchard worker",       # P1
    "farm worker",          # P1
    "warehouse",            # P2
    "manufacturing",        # P2
    "factory worker",       # P2
    "construction labourer",  # P3
    "general labourer",     # P3
]

_LISTING_ID_RE = re.compile(r"/listing/(\d+)")


class TradeMeScraper(BaseScraper):
    source_name = "trademe"

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
                        logger.info("Trade Me '%s' → %d unique job(s)", term, len(jobs))
                        await asyncio.sleep(2)
                    except Exception as exc:
                        logger.error("Trade Me: error on term '%s': %s", term, exc)
            finally:
                await browser.close()

        logger.info("Trade Me: %d unique jobs collected across all terms", len(all_jobs))
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
        # Trade Me renders cards via Angular — wait for at least one card or 4s
        try:
            await page.wait_for_selector("tm-jobs-search-card", timeout=4_000)
        except Exception:
            pass  # no cards for this term is fine
        return await page.content()

    def _parse_page(self, html: str) -> list[ScrapedJob]:
        """Parse job cards from raw HTML. Separated from Playwright for testability."""
        soup = BeautifulSoup(html, "html.parser")
        cards = soup.find_all("tm-jobs-search-card")
        jobs = []
        for card in cards:
            job = self._parse_card(card)
            if job:
                jobs.append(job)
        return jobs

    def _parse_card(self, card: Tag) -> Optional[ScrapedJob]:
        try:
            title_el = card.select_one(".tm-jobs-search-card__title")
            if not title_el:
                return None
            title = title_el.get_text(strip=True)
            if not title:
                return None

            link_el = card.select_one("a.tm-jobs-search-card__link")
            if not link_el:
                return None
            href = str(link_el.get("href", ""))
            listing_id = self._extract_listing_id(href)
            if not listing_id:
                return None

            employer_el = card.select_one(".jobs-search-card-metadata__company")
            employer = employer_el.get_text(strip=True) if employer_el else "Unknown"

            location_el = card.select_one(".jobs-search-card-metadata__location")
            location = location_el.get_text(strip=True) if location_el else "New Zealand"

            salary_el = card.select_one(".tm-jobs-search-card__approximate-pay-range")
            salary_text = salary_el.get_text(strip=True) if salary_el else None

            desc_el = card.select_one(".tm-jobs-search-card__short-description")
            description = desc_el.get_text(strip=True) if desc_el else None

            # Strip the rsqid tracking parameter from the canonical URL
            clean_path = href.split("?")[0]
            url = BASE_URL + clean_path

            return ScrapedJob(
                external_id=listing_id,
                source=self.source_name,
                title=title,
                employer=employer,
                location=location,
                url=url,
                salary_text=salary_text,
                description=description,
                raw_data={"trademe_href": href},
            )
        except Exception as exc:
            logger.warning("Trade Me: failed to parse card: %s", exc)
            return None

    @staticmethod
    def _extract_listing_id(href: str) -> Optional[str]:
        m = _LISTING_ID_RE.search(href)
        return m.group(1) if m else None
