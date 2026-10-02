"""Shared food catalogue with personal values.

Every food is visible to all users. The contributor of a food may still fix it
for everyone until somebody else uses it (logs it or saves their own values);
after that the shared values are frozen and any change, the contributor's
included, is stored as a personal override that only its author sees.
"""

from sqlalchemy import exists, or_, select
from sqlalchemy.orm import Session

from app.models import DiaryEntry, Food, FoodOverride, Overrides
from app.schemas import FoodOut, Nutrition

NUTRIENTS = ("kcal", "protein", "fat", "carbs")


def user_overrides(db: Session, user_id: int, food_ids: list[int] | None = None) -> Overrides:
    stmt = select(FoodOverride).where(FoodOverride.user_id == user_id)
    if food_ids is not None:
        stmt = stmt.where(FoodOverride.food_id.in_(food_ids))
    return {o.food_id: o for o in db.scalars(stmt)}


def effective(food: Food, overrides: Overrides) -> Food | FoodOverride:
    """The object to read kcal/protein/fat/carbs from for this user."""
    return overrides.get(food.id) or food


def used_by_others(db: Session, food_id: int, user_id: int) -> bool:
    logged = exists().where(DiaryEntry.food_id == food_id, DiaryEntry.user_id != user_id)
    corrected = exists().where(FoodOverride.food_id == food_id, FoodOverride.user_id != user_id)
    return bool(db.scalar(select(or_(logged, corrected))))


def can_edit_shared(db: Session, food: Food, user_id: int) -> bool:
    return food.created_by_id == user_id and not used_by_others(db, food.id, user_id)


def food_out(db: Session, food: Food, user_id: int, overrides: Overrides) -> FoodOut:
    own = overrides.get(food.id)
    values = effective(food, overrides)
    mine = food.created_by_id == user_id
    return FoodOut(
        id=food.id,
        name=food.name,
        food_group=food.food_group.value,
        fiber=food.fiber,
        allergens=food.allergens,
        **{n: getattr(values, n) for n in NUTRIENTS},
        shared=Nutrition(**{n: getattr(food, n) for n in NUTRIENTS}),
        personal=own is not None,
        community=food.created_by_id is not None,
        created_by_me=mine,
        can_edit_shared=mine and not used_by_others(db, food.id, user_id),
    )
