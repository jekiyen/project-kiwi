from datetime import datetime

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from backend.database.models import (
    ApplicationProfile,
    ApplicationProfileResponse,
    ApplicationProfileUpdate,
    ApplicationReference,
    ApplicationReferenceOut,
)
from backend.database.session import get_session

router = APIRouter(prefix="/application-profile", tags=["application-profile"])


def _get_or_create(session: Session) -> ApplicationProfile:
    """Exactly one profile ever exists — created lazily on first read/write."""
    profile = session.exec(select(ApplicationProfile)).first()
    if not profile:
        profile = ApplicationProfile()
        session.add(profile)
        session.commit()
        session.refresh(profile)
    return profile


def _get_references(session: Session, profile_id: int) -> list[ApplicationReference]:
    return list(
        session.exec(
            select(ApplicationReference)
            .where(ApplicationReference.profile_id == profile_id)
            .order_by(ApplicationReference.id.asc())
        ).all()
    )


def _to_response(session: Session, profile: ApplicationProfile) -> ApplicationProfileResponse:
    refs = _get_references(session, profile.id)
    return ApplicationProfileResponse(
        id=profile.id,
        full_name=profile.full_name,
        preferred_name=profile.preferred_name,
        email=profile.email,
        phone=profile.phone,
        current_address=profile.current_address,
        city=profile.city,
        country=profile.country,
        nationality=profile.nationality,
        work_rights_current_country=profile.work_rights_current_country,
        visa_status=profile.visa_status,
        eligible_to_work_nz=profile.eligible_to_work_nz,
        need_sponsorship=profile.need_sponsorship,
        driver_license=profile.driver_license,
        own_vehicle=profile.own_vehicle,
        linkedin_url=profile.linkedin_url,
        portfolio_url=profile.portfolio_url,
        github_url=profile.github_url,
        website_url=profile.website_url,
        emergency_contact_name=profile.emergency_contact_name,
        emergency_contact_relationship=profile.emergency_contact_relationship,
        emergency_contact_phone=profile.emergency_contact_phone,
        notes=profile.notes,
        references=[
            ApplicationReferenceOut(
                id=r.id, name=r.name, company=r.company,
                relationship=r.relationship, email=r.email, phone=r.phone,
            )
            for r in refs
        ],
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


@router.get("/", response_model=ApplicationProfileResponse)
async def get_application_profile(session: Session = Depends(get_session)) -> ApplicationProfileResponse:
    profile = _get_or_create(session)
    return _to_response(session, profile)


@router.put("/", response_model=ApplicationProfileResponse)
async def update_application_profile(
    body: ApplicationProfileUpdate,
    session: Session = Depends(get_session),
) -> ApplicationProfileResponse:
    """Upsert the single profile — every field is replaced with what's sent,
    and `references` fully replaces the existing reference list."""
    profile = _get_or_create(session)

    data = body.model_dump(exclude={"references"})
    for field_name, value in data.items():
        setattr(profile, field_name, value)
    profile.updated_at = datetime.utcnow()
    session.add(profile)

    for ref in _get_references(session, profile.id):
        session.delete(ref)
    for ref_in in body.references:
        session.add(ApplicationReference(profile_id=profile.id, **ref_in.model_dump()))

    session.commit()
    session.refresh(profile)
    return _to_response(session, profile)
