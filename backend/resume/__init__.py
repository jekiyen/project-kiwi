from backend.resume.base import (
    EducationEntry,
    ExperienceEntry,
    ParsedResume,
    ResumeParser,
)
from backend.resume.regex_parser import RegexResumeParser


def get_resume_parser() -> ResumeParser:
    """
    Single switch point for which parser produces ParsedResume from text.
    Phase 8 adds an AI-based parser here (e.g. backend/resume/ai_parser.py)
    behind a settings flag — nothing else in the app needs to change.
    """
    return RegexResumeParser()


__all__ = [
    "EducationEntry",
    "ExperienceEntry",
    "ParsedResume",
    "ResumeParser",
    "RegexResumeParser",
    "get_resume_parser",
]
