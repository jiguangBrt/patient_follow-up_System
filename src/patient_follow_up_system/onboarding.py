from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from patient_follow_up_system.auth import require_roles
from patient_follow_up_system.database import get_db
from patient_follow_up_system.models import User, UserOnboardingState, UserRole

router = APIRouter()
Doctor = Annotated[User, Depends(require_roles(UserRole.DOCTOR))]
DB = Annotated[Session, Depends(get_db)]

DOCTOR_TOUR_KEY = "doctor_workspace"


class OnboardingStatusResponse(BaseModel):
    tour_key: str
    status: str


class OnboardingUpdateRequest(BaseModel):
    action: Literal["complete", "skip"]


def find_state(db: Session, user_id: int) -> UserOnboardingState | None:
    return db.scalar(
        select(UserOnboardingState).where(
            UserOnboardingState.user_id == user_id,
            UserOnboardingState.tour_key == DOCTOR_TOUR_KEY,
        )
    )


@router.get("/onboarding/doctor-tour", response_model=OnboardingStatusResponse)
def read_doctor_tour_status(db: DB, doctor: Doctor) -> OnboardingStatusResponse:
    state = find_state(db, doctor.id)
    return OnboardingStatusResponse(
        tour_key=DOCTOR_TOUR_KEY,
        status=state.status if state else "pending",
    )


@router.post("/onboarding/doctor-tour", response_model=OnboardingStatusResponse)
def update_doctor_tour_status(
    request: OnboardingUpdateRequest,
    db: DB,
    doctor: Doctor,
) -> OnboardingStatusResponse:
    state = find_state(db, doctor.id)
    if state is None:
        state = UserOnboardingState(user_id=doctor.id, tour_key=DOCTOR_TOUR_KEY)
        db.add(state)
    state.status = "completed" if request.action == "complete" else "skipped"
    state.updated_at = datetime.now(UTC).replace(tzinfo=None)
    db.commit()
    return OnboardingStatusResponse(tour_key=DOCTOR_TOUR_KEY, status=state.status)
