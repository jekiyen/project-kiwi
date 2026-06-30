"""Tests for ManualProvider deterministic scoring."""
import pytest

from backend.ai.manual import ManualProvider
from backend.database.models import RolePriority


@pytest.fixture
def provider() -> ManualProvider:
    return ManualProvider()


def make_job(title: str = "", description: str = "") -> dict:
    return {"title": title, "description": description, "employer": "", "salary_text": ""}


# ── Role detection ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_p1_packhouse(provider):
    result = await provider.analyze_job(make_job("Packhouse Worker"), {})
    assert result.score == 70  # base only


@pytest.mark.asyncio
async def test_p1_picker(provider):
    result = await provider.analyze_job(make_job("Fruit Picker"), {})
    assert result.score == 70


@pytest.mark.asyncio
async def test_p1_orchard(provider):
    result = await provider.analyze_job(make_job("Orchard Worker"), {})
    assert result.score == 70


@pytest.mark.asyncio
async def test_p2_warehouse(provider):
    result = await provider.analyze_job(make_job("Warehouse Operator"), {})
    assert result.score == 55


@pytest.mark.asyncio
async def test_p2_factory(provider):
    result = await provider.analyze_job(make_job("Factory Worker"), {})
    assert result.score == 55


@pytest.mark.asyncio
async def test_p3_labourer(provider):
    result = await provider.analyze_job(make_job("General Labourer"), {})
    assert result.score == 40


@pytest.mark.asyncio
async def test_no_match(provider):
    result = await provider.analyze_job(make_job("Chef de Partie"), {})
    assert result.score == 20


# ── Score adjustments ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_accredited_adds_10(provider):
    result = await provider.analyze_job(
        make_job("Packhouse Worker", "We are an accredited employer."), {}
    )
    assert result.score == 80
    assert result.visa_accredited_employer is True


@pytest.mark.asyncio
async def test_overseas_adds_8(provider):
    result = await provider.analyze_job(
        make_job("Packhouse Worker", "Overseas applicants are welcome."), {}
    )
    assert result.score == 78
    assert result.visa_overseas_friendly is True


@pytest.mark.asyncio
async def test_sponsorship_adds_5(provider):
    result = await provider.analyze_job(
        make_job("Packhouse Worker", "Work visa support available."), {}
    )
    assert result.score == 75
    assert result.visa_sponsorship_potential is True


@pytest.mark.asyncio
async def test_nz_rights_subtracts_25(provider):
    result = await provider.analyze_job(
        make_job("Packhouse Worker", "Must be a NZ citizen or permanent resident."), {}
    )
    assert result.score == 45
    assert result.visa_nz_rights_required is True


@pytest.mark.asyncio
async def test_nz_rights_caps_at_zero(provider):
    result = await provider.analyze_job(
        make_job("Chef de Partie", "Must be a NZ citizen."), {}
    )
    # 20 - 25 = -5 → clamped to 0
    assert result.score == 0


@pytest.mark.asyncio
async def test_all_positive_signals(provider):
    result = await provider.analyze_job(
        make_job(
            "Packhouse Worker",
            "Accredited employer. Overseas applicants welcome. Work visa support available.",
        ),
        {},
    )
    # 70 + 10 + 8 + 5 = 93
    assert result.score == 93
    assert result.visa_accredited_employer is True
    assert result.visa_overseas_friendly is True
    assert result.visa_sponsorship_potential is True
    assert result.visa_nz_rights_required is False


@pytest.mark.asyncio
async def test_score_caps_at_100(provider):
    result = await provider.analyze_job(
        make_job(
            "Packhouse Worker",
            "Accredited employer. Overseas applicants welcome. Work visa support available. " * 5,
        ),
        {},
    )
    assert result.score <= 100


# ── Determinism ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_same_input_same_score(provider):
    job = make_job("Packhouse Worker", "Accredited employer. Overseas applicants welcome.")
    r1 = await provider.analyze_job(job, {})
    r2 = await provider.analyze_job(job, {})
    assert r1.score == r2.score
    assert r1.explanation == r2.explanation


# ── Explanation ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_explanation_contains_verdict(provider):
    result = await provider.analyze_job(make_job("Packhouse Worker"), {})
    assert "Strong match" in result.explanation
    assert "70/100" in result.explanation


@pytest.mark.asyncio
async def test_weak_verdict_for_low_score(provider):
    result = await provider.analyze_job(make_job("Chef"), {})
    assert "Weak match" in result.explanation


@pytest.mark.asyncio
async def test_is_available(provider):
    assert await provider.is_available() is True


# ── Phase 3: new fields ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_priority_p1(provider):
    result = await provider.analyze_job(make_job("Packhouse Worker"), {})
    assert result.priority == "P1"


@pytest.mark.asyncio
async def test_priority_p2(provider):
    result = await provider.analyze_job(make_job("Warehouse Operator"), {})
    assert result.priority == "P2"


@pytest.mark.asyncio
async def test_priority_reject_for_no_match(provider):
    result = await provider.analyze_job(make_job("Chef de Partie"), {})
    assert result.priority == "Reject"


@pytest.mark.asyncio
async def test_provider_is_manual(provider):
    result = await provider.analyze_job(make_job("Packhouse Worker"), {})
    assert result.provider == "manual"
    assert result.model == ""


@pytest.mark.asyncio
async def test_confidence_is_80(provider):
    result = await provider.analyze_job(make_job("Packhouse Worker"), {})
    assert result.confidence == 80


@pytest.mark.asyncio
async def test_reasons_is_nonempty_list(provider):
    result = await provider.analyze_job(make_job("Packhouse Worker"), {})
    assert isinstance(result.reasons, list)
    assert len(result.reasons) >= 1


@pytest.mark.asyncio
async def test_pros_populated_for_p1(provider):
    result = await provider.analyze_job(make_job("Packhouse Worker"), {})
    assert len(result.pros) >= 1


@pytest.mark.asyncio
async def test_cons_populated_when_nz_rights_required(provider):
    result = await provider.analyze_job(
        make_job("Packhouse Worker", "Must be a NZ citizen."), {}
    )
    assert any("NZ work rights" in c or "work rights" in c.lower() for c in result.cons)


@pytest.mark.asyncio
async def test_visa_probability_increases_with_accreditation(provider):
    base = await provider.analyze_job(make_job("Packhouse Worker"), {})
    accredited = await provider.analyze_job(
        make_job("Packhouse Worker", "Accredited employer."), {}
    )
    assert accredited.visa_probability > base.visa_probability


@pytest.mark.asyncio
async def test_visa_probability_zero_when_nz_rights_required(provider):
    result = await provider.analyze_job(
        make_job("Chef", "Must be a NZ citizen."), {}
    )
    assert result.visa_probability == 0
