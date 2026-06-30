#!/usr/bin/env python3
"""
Seed test jobs for development.
Run from the project root: python scripts/seed_jobs.py

Each job is designed to produce a specific ManualProvider score range
so the scoring logic can be verified visually in the dashboard.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlmodel import Session, select

from backend.database.models import Job
from backend.database.session import create_db_and_tables, engine

TEST_JOBS = [
    {
        "external_id": "seed-001",
        "source": "seed",
        "title": "Packhouse Worker",
        "employer": "Zespri International",
        "location": "Te Puke, Bay of Plenty",
        "url": "https://example.com/job/seed-001",
        "salary_text": "$22–$25/hr",
        "description": (
            "We are an accredited employer seeking reliable packhouse workers for the kiwifruit season. "
            "Overseas applicants are welcome and we assist with relocation. No NZ experience required. "
            "Entry-level role, training provided."
        ),
        # Expected score: P1 base 70 + accredited +10 + overseas +8 = 88
    },
    {
        "external_id": "seed-002",
        "source": "seed",
        "title": "Fruit Picker — Seasonal",
        "employer": "Hawke's Bay Orchards Ltd",
        "location": "Hastings, Hawke's Bay",
        "url": "https://example.com/job/seed-002",
        "salary_text": "$23/hr",
        "description": (
            "Seasonal fruit picking work available now. Open to international applicants with a valid work visa "
            "or those who can obtain one. We provide visa support for the right candidates. "
            "Physical, outdoor work. No prior experience needed."
        ),
        # Expected score: P1 base 70 + overseas +8 + sponsorship +5 = 83
    },
    {
        "external_id": "seed-003",
        "source": "seed",
        "title": "Orchard Worker",
        "employer": "Mount Eden Orchards",
        "location": "Nelson, Marlborough",
        "url": "https://example.com/job/seed-003",
        "salary_text": "$21/hr",
        "description": (
            "Looking for a reliable orchard worker for general orchard maintenance and harvesting. "
            "No special signals detected in this listing."
        ),
        # Expected score: P1 base 70 (no extras) = 70
    },
    {
        "external_id": "seed-004",
        "source": "seed",
        "title": "Farm Worker — Dairy",
        "employer": "Waikato Dairy Farm",
        "location": "Hamilton, Waikato",
        "url": "https://example.com/job/seed-004",
        "salary_text": "$24/hr + accommodation",
        "description": (
            "Dairy farm worker required. Applicants must be a NZ citizen or NZ permanent resident "
            "with the right to work in NZ without restriction."
        ),
        # Expected score: P1 base 70 - nz_rights 25 = 45
    },
    {
        "external_id": "seed-005",
        "source": "seed",
        "title": "Warehouse Operator",
        "employer": "NZ Post",
        "location": "Auckland, Auckland",
        "url": "https://example.com/job/seed-005",
        "salary_text": "$24–$26/hr",
        "description": (
            "We are an accredited employer. Join our warehouse team. "
            "Overseas applicants welcome. Forklift experience preferred but not required. "
            "Entry-level applications considered."
        ),
        # Expected score: P2 base 55 + accredited +10 + overseas +8 = 73
    },
    {
        "external_id": "seed-006",
        "source": "seed",
        "title": "Factory Worker — Manufacturing",
        "employer": "Fonterra Co-operative",
        "location": "Palmerston North, Manawatū",
        "url": "https://example.com/job/seed-006",
        "salary_text": "$25/hr",
        "description": (
            "Production line and manufacturing work available. "
            "No overseas sponsorship available. Must be eligible to work in NZ without restriction."
        ),
        # Expected score: P2 base 55 - nz_rights 25 = 30
    },
    {
        "external_id": "seed-007",
        "source": "seed",
        "title": "General Labourer",
        "employer": "Wellington Labour Hire Co",
        "location": "Wellington, Wellington",
        "url": "https://example.com/job/seed-007",
        "salary_text": "$22/hr",
        "description": (
            "Labour hire for various construction and site labourer roles across Wellington. "
            "No specific signals in this listing."
        ),
        # Expected score: P3 base 40 = 40
    },
    {
        "external_id": "seed-008",
        "source": "seed",
        "title": "Chef de Partie",
        "employer": "The Grand Hotel Auckland",
        "location": "Auckland, Auckland",
        "url": "https://example.com/job/seed-008",
        "salary_text": "$60,000/yr",
        "description": (
            "Experienced chef required for a 5-star hotel. Must be a NZ citizen or permanent resident. "
            "This role does not align with blue-collar agricultural or manufacturing work."
        ),
        # Expected score: no match base 20 - nz_rights 25 = 0 (capped)
    },
]


def seed() -> None:
    create_db_and_tables()

    with Session(engine) as session:
        existing = set(
            row for row in session.exec(
                __import__("sqlmodel").select(Job.external_id).where(Job.source == "seed")
            ).all()
        )

        added = 0
        for data in TEST_JOBS:
            if data["external_id"] in existing:
                continue
            job = Job(**data)
            session.add(job)
            added += 1

        session.commit()

    if added == 0:
        print("Seed jobs already present — nothing added.")
    else:
        print(f"Added {added} test job(s).")
        print()
        print("Expected scores after analysis (ManualProvider):")
        print("  seed-001  Packhouse / accredited + overseas         → ~88")
        print("  seed-002  Fruit Picker / overseas + sponsorship      → ~83")
        print("  seed-003  Orchard Worker / no extras                 → ~70")
        print("  seed-004  Farm Worker / NZ rights required           → ~45")
        print("  seed-005  Warehouse / accredited + overseas          → ~73")
        print("  seed-006  Factory / NZ rights required               → ~30")
        print("  seed-007  General Labourer / no extras               → ~40")
        print("  seed-008  Chef / NZ rights required + no match       → ~0")
        print()
        print("Run: python scripts/seed_jobs.py")
        print("Then: Trigger Scan or Score Unscored Jobs in the dashboard.")


if __name__ == "__main__":
    seed()
