from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ScrapedJob:
    external_id: str
    source: str
    title: str
    employer: str
    location: str
    url: str
    description: Optional[str] = None
    salary_text: Optional[str] = None
    raw_data: dict = field(default_factory=dict)


class BaseScraper(ABC):
    """
    All platform scrapers extend this class. To add a new source:
    1. Create backend/scrapers/<platform>.py extending BaseScraper
    2. Set source_name
    3. Implement scrape() and is_accessible()
    4. Register in ScanAgent.run()
    """

    source_name: str

    @abstractmethod
    async def scrape(self) -> list[ScrapedJob]:
        """Scrape all relevant job listings from the platform."""
        ...

    @abstractmethod
    async def is_accessible(self) -> bool:
        """Return True if the platform is reachable."""
        ...
