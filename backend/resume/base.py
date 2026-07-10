from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class EducationEntry:
    institution: str = ""
    qualification: str = ""
    dates: str = ""


@dataclass
class ExperienceEntry:
    title: str = ""
    company: str = ""
    dates: str = ""
    description: str = ""


@dataclass
class ParsedResume:
    """Structured facts extracted from resume text.

    This is the contract between text -> ParsedResume. A Phase 8 AI-based
    parser returns the exact same shape, so the API/storage layer never has
    to know which parser produced it.
    """
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    linkedin: str | None = None
    portfolio: str | None = None
    skills: list[str] = field(default_factory=list)
    companies: list[str] = field(default_factory=list)
    job_titles: list[str] = field(default_factory=list)
    education: list[EducationEntry] = field(default_factory=list)
    experience: list[ExperienceEntry] = field(default_factory=list)


class ResumeParser(ABC):
    """
    All resume parsers extend this class. To add a new one (e.g. a Phase 8
    AI-based parser): create backend/resume/<name>_parser.py implementing
    this interface, then select it in backend/resume/__init__.py's
    get_resume_parser() — nothing else in the app needs to change.
    """

    version: str

    @abstractmethod
    async def parse(self, text: str) -> ParsedResume:
        """Extract structured facts from plain resume text."""
        ...
