from datetime import date, timedelta

from fastapi import APIRouter, Query
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.deps import CurrentProfile, CurrentUser, DbSession
from app.models import Profile, WeightLog
from app.schemas import CalculatorIn, EnergyPlanOut, ProfileIn, ProfileOut, WeightIn, WeightOut
from app.services.calories import BodyParams, calculate
from app.services.profiles import energy_plan, profile_out

router = APIRouter(prefix="/api", tags=["profile"])


@router.post("/calculator", response_model=EnergyPlanOut)
def calculator(data: CalculatorIn) -> EnergyPlanOut:
    """Public calorie calculator; no account needed."""
    params = BodyParams(**data.model_dump(exclude={"meals_per_day"}))
    return EnergyPlanOut.model_validate(calculate(params, data.meals_per_day))


@router.get("/profile", response_model=ProfileOut)
def get_profile(profile: CurrentProfile) -> ProfileOut:
    return profile_out(profile)


@router.put("/profile", response_model=ProfileOut)
def put_profile(data: ProfileIn, user: CurrentUser, db: DbSession) -> ProfileOut:
    profile = user.profile or Profile(user=user)
    weight_changed = profile.weight_kg != data.weight_kg
    for key, value in data.model_dump().items():
        setattr(profile, key, value)
    db.add(profile)
    if weight_changed:
        _upsert_weight(db, user.id, date.today(), data.weight_kg)
    db.commit()
    return profile_out(profile)


@router.get("/profile/targets", response_model=EnergyPlanOut)
def get_targets(profile: CurrentProfile) -> EnergyPlanOut:
    return EnergyPlanOut.model_validate(energy_plan(profile))


def _upsert_weight(db: DbSession, user_id: int, day: date, weight: float) -> None:
    stmt = insert(WeightLog).values(user_id=user_id, logged_on=day, weight_kg=weight)
    db.execute(stmt.on_conflict_do_update(index_elements=["user_id", "logged_on"], set_={"weight_kg": weight}))


@router.get("/weights", response_model=list[WeightOut])
def list_weights(user: CurrentUser, db: DbSession, days: int = Query(90, ge=1, le=3650)) -> list[WeightLog]:
    since = date.today() - timedelta(days=days)
    stmt = (
        select(WeightLog)
        .where(WeightLog.user_id == user.id, WeightLog.logged_on >= since)
        .order_by(WeightLog.logged_on)
    )
    return list(db.scalars(stmt))


@router.post("/weights", response_model=WeightOut)
def log_weight(data: WeightIn, profile: CurrentProfile, db: DbSession) -> WeightLog:
    _upsert_weight(db, profile.user_id, data.logged_on, data.weight_kg)
    latest = db.scalar(
        select(WeightLog).where(WeightLog.user_id == profile.user_id).order_by(WeightLog.logged_on.desc()).limit(1)
    )
    # The profile (and therefore calorie targets) follows the most recent weigh-in.
    profile.weight_kg = latest.weight_kg
    db.commit()
    return db.scalar(
        select(WeightLog).where(WeightLog.user_id == profile.user_id, WeightLog.logged_on == data.logged_on)
    )
