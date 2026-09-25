from datetime import date, timedelta

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.deps import CurrentUser, DbSession
from app.models import DiaryEntry, Dish, Food, MealType, User
from app.schemas import DayTotalsOut, DaySummaryOut, DiaryEntryIn, DiaryEntryOut, DiaryEntryUpdate, Nutrition
from app.services.profiles import energy_plan

router = APIRouter(prefix="/api/diary", tags=["diary"])

MEAL_ORDER = {m: i for i, m in enumerate(MealType)}


def _apply_amount(entry: DiaryEntry, food: Food | None, dish: Dish | None,
                  grams: float | None, servings: float | None) -> None:
    """Fill the entry's nutrition snapshot from a food (by grams) or a dish (by servings)."""
    if food is not None:
        factor = grams / 100
        entry.name, entry.grams, entry.servings = food.name, grams, None
        src = food
    else:
        servings = servings if servings is not None else (grams / dish.grams if grams else 1.0)
        factor = servings
        entry.name, entry.grams, entry.servings = dish.name, dish.grams * servings, servings
        src = dish
    entry.kcal = round(src.kcal * factor, 1)
    entry.protein = round(src.protein * factor, 1)
    entry.fat = round(src.fat * factor, 1)
    entry.carbs = round(src.carbs * factor, 1)


def add_entry(db: DbSession, user: User, eaten_on: date, meal_type: MealType, *,
              food: Food | None = None, dish: Dish | None = None,
              grams: float | None = None, servings: float | None = None) -> DiaryEntry:
    entry = DiaryEntry(user_id=user.id, eaten_on=eaten_on, meal_type=meal_type,
                       food_id=food.id if food else None, dish_id=dish.id if dish else None)
    _apply_amount(entry, food, dish, grams, servings)
    db.add(entry)
    return entry


def _owned_entry(db: DbSession, user: User, entry_id: int) -> DiaryEntry:
    entry = db.get(DiaryEntry, entry_id)
    if entry is None or entry.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Запись в дневнике не найдена")
    return entry


def _visible_food(db: DbSession, user: User, food_id: int) -> Food:
    food = db.get(Food, food_id)
    if food is None or food.owner_id not in (None, user.id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Продукт не найден")
    return food


def _dish(db: DbSession, dish_id: int) -> Dish:
    dish = db.get(Dish, dish_id)
    if dish is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Блюдо не найдено")
    return dish


@router.get("", response_model=DaySummaryOut)
def get_day(user: CurrentUser, db: DbSession, day: date = Query(default_factory=date.today, alias="date")) -> DaySummaryOut:
    entries = sorted(
        db.scalars(select(DiaryEntry).where(DiaryEntry.user_id == user.id, DiaryEntry.eaten_on == day)),
        key=lambda e: (MEAL_ORDER[e.meal_type], e.created_at),
    )
    totals = Nutrition(
        kcal=round(sum(e.kcal for e in entries)),
        protein=round(sum(e.protein for e in entries), 1),
        fat=round(sum(e.fat for e in entries), 1),
        carbs=round(sum(e.carbs for e in entries), 1),
    )
    targets = None
    if user.profile is not None:
        plan = energy_plan(user.profile)
        targets = Nutrition(kcal=plan.target_kcal, protein=plan.protein_g, fat=plan.fat_g, carbs=plan.carbs_g)
    return DaySummaryOut(
        date=day,
        totals=totals,
        targets=targets,
        remaining_kcal=round(targets.kcal - totals.kcal) if targets else None,
        entries=[DiaryEntryOut.model_validate(e) for e in entries],
    )


@router.get("/history", response_model=list[DayTotalsOut])
def history(user: CurrentUser, db: DbSession, days: int = Query(7, ge=1, le=365)) -> list[DayTotalsOut]:
    since = date.today() - timedelta(days=days - 1)
    rows = db.execute(
        select(
            DiaryEntry.eaten_on,
            func.sum(DiaryEntry.kcal),
            func.sum(DiaryEntry.protein),
            func.sum(DiaryEntry.fat),
            func.sum(DiaryEntry.carbs),
        )
        .where(DiaryEntry.user_id == user.id, DiaryEntry.eaten_on >= since)
        .group_by(DiaryEntry.eaten_on)
    ).all()
    by_day = {r[0]: r[1:] for r in rows}
    result = []
    for i in range(days):
        day = since + timedelta(days=i)
        kcal, protein, fat, carbs = by_day.get(day, (0, 0, 0, 0))
        result.append(DayTotalsOut(date=day, kcal=round(kcal), protein=round(protein, 1),
                                   fat=round(fat, 1), carbs=round(carbs, 1)))
    return result


@router.post("", response_model=DiaryEntryOut, status_code=status.HTTP_201_CREATED)
def create_entry(data: DiaryEntryIn, user: CurrentUser, db: DbSession) -> DiaryEntry:
    food = _visible_food(db, user, data.food_id) if data.food_id is not None else None
    dish = _dish(db, data.dish_id) if data.dish_id is not None else None
    entry = add_entry(db, user, data.eaten_on, data.meal_type, food=food, dish=dish,
                      grams=data.grams, servings=data.servings)
    db.commit()
    return entry


@router.patch("/{entry_id}", response_model=DiaryEntryOut)
def update_entry(entry_id: int, data: DiaryEntryUpdate, user: CurrentUser, db: DbSession) -> DiaryEntry:
    entry = _owned_entry(db, user, entry_id)
    if data.meal_type is not None:
        entry.meal_type = data.meal_type
    if data.grams is not None or data.servings is not None:
        food = db.get(Food, entry.food_id) if entry.food_id else None
        dish = db.get(Dish, entry.dish_id) if entry.dish_id else None
        if food is None and dish is None:
            # Source was deleted: scale the stored snapshot proportionally.
            new_grams = data.grams if data.grams is not None else entry.grams * data.servings / (entry.servings or 1)
            factor = new_grams / entry.grams
            entry.grams = new_grams
            entry.servings = entry.servings * factor if entry.servings else None
            for attr in ("kcal", "protein", "fat", "carbs"):
                setattr(entry, attr, round(getattr(entry, attr) * factor, 1))
        elif food is not None:
            grams = data.grams if data.grams is not None else entry.grams
            _apply_amount(entry, food, None, grams, None)
        else:
            _apply_amount(entry, None, dish, data.grams, data.servings)
    db.commit()
    return entry


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_entry(entry_id: int, user: CurrentUser, db: DbSession) -> None:
    db.delete(_owned_entry(db, user, entry_id))
    db.commit()
