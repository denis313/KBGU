from datetime import date, timedelta

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select

from app.deps import CurrentProfile, CurrentUser, DbSession
from app.models import DiaryEntry, Dish, MenuPlan, MenuPlanItem, User
from app.routers.diary import add_entry
from app.schemas import DiaryEntryOut, MenuGenerateIn, MenuPlanOut, Nutrition
from app.services.menu import MenuItem, NoDishesError, Targets, generate_menu, swap_dish
from app.services.profiles import dish_option, energy_plan

router = APIRouter(prefix="/api/menu", tags=["menu"])

RECENT_DAYS = 3


def plan_out(plan: MenuPlan) -> MenuPlanOut:
    items = plan.items
    return MenuPlanOut(
        id=plan.id,
        plan_date=plan.plan_date,
        seed=plan.seed,
        targets=Nutrition(kcal=plan.target_kcal, protein=plan.target_protein,
                          fat=plan.target_fat, carbs=plan.target_carbs),
        totals=Nutrition(
            kcal=round(sum(i.kcal for i in items)),
            protein=round(sum(i.protein for i in items), 1),
            fat=round(sum(i.fat for i in items), 1),
            carbs=round(sum(i.carbs for i in items), 1),
        ),
        items=items,
    )


def _fill_item(row: MenuPlanItem, item: MenuItem) -> None:
    row.dish_id = item.dish.id
    row.name = item.dish.name
    row.servings = item.servings
    row.grams = round(item.grams)
    row.kcal = round(item.kcal)
    row.protein = round(item.protein, 1)
    row.fat = round(item.fat, 1)
    row.carbs = round(item.carbs, 1)


def _recent_dish_ids(db: DbSession, user_id: int, day: date) -> set[int]:
    since, until = day - timedelta(days=RECENT_DAYS), day - timedelta(days=1)
    planned = db.scalars(
        select(MenuPlanItem.dish_id).join(MenuPlan)
        .where(MenuPlan.user_id == user_id, MenuPlan.plan_date.between(since, until))
    )
    eaten = db.scalars(
        select(DiaryEntry.dish_id)
        .where(DiaryEntry.user_id == user_id, DiaryEntry.eaten_on.between(since, until))
    )
    return {i for i in [*planned, *eaten] if i is not None}


def _owned_plan(db: DbSession, user: User, plan_id: int) -> MenuPlan:
    plan = db.get(MenuPlan, plan_id)
    if plan is None or plan.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Меню не найдено")
    return plan


def _catalogue(db: DbSession) -> list:
    return [dish_option(d) for d in db.scalars(select(Dish))]


@router.post("/generate", response_model=MenuPlanOut, status_code=status.HTTP_201_CREATED)
def generate(data: MenuGenerateIn, profile: CurrentProfile, db: DbSession) -> MenuPlanOut:
    energy = energy_plan(profile)
    targets = Targets(kcal=energy.target_kcal, protein=energy.protein_g, fat=energy.fat_g, carbs=energy.carbs_g)
    try:
        menu = generate_menu(
            _catalogue(db),
            targets,
            energy.meal_split,
            diet=profile.diet_type.value,
            excluded_allergens=profile.excluded_allergens,
            recent_dish_ids=_recent_dish_ids(db, profile.user_id, data.plan_date),
            seed=data.seed,
        )
    except NoDishesError as e:
        raise HTTPException(422, str(e)) from e

    existing = db.scalar(
        select(MenuPlan).where(MenuPlan.user_id == profile.user_id, MenuPlan.plan_date == data.plan_date)
    )
    if existing is not None:
        db.delete(existing)
        db.flush()

    plan = MenuPlan(
        user_id=profile.user_id, plan_date=data.plan_date, seed=menu.seed,
        target_kcal=targets.kcal, target_protein=targets.protein, target_fat=targets.fat, target_carbs=targets.carbs,
    )
    for position, item in enumerate(menu.items):
        row = MenuPlanItem(position=position, meal_type=item.meal_type, meal_target_kcal=energy.meal_split[item.meal_type])
        _fill_item(row, item)
        plan.items.append(row)
    db.add(plan)
    db.commit()
    return plan_out(plan)


@router.get("", response_model=MenuPlanOut)
def get_plan(user: CurrentUser, db: DbSession, day: date = Query(default_factory=date.today, alias="date")) -> MenuPlanOut:
    plan = db.scalar(select(MenuPlan).where(MenuPlan.user_id == user.id, MenuPlan.plan_date == day))
    if plan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "На этот день меню ещё нет")
    return plan_out(plan)


@router.post("/{plan_id}/items/{item_id}/swap", response_model=MenuPlanOut)
def swap_item(plan_id: int, item_id: int, profile: CurrentProfile, db: DbSession,
              seed: int | None = Query(None)) -> MenuPlanOut:
    plan = _owned_plan(db, profile.user, plan_id)
    row = next((i for i in plan.items if i.id == item_id), None)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Блюдо в меню не найдено")
    try:
        item = swap_dish(
            _catalogue(db),
            row.meal_type,
            row.meal_target_kcal,
            protein_per_kcal=plan.target_protein / plan.target_kcal,
            diet=profile.diet_type.value,
            excluded_allergens=profile.excluded_allergens,
            exclude_ids={i.dish_id for i in plan.items if i.dish_id is not None},
            seed=seed,
        )
    except NoDishesError as e:
        raise HTTPException(422, "Других подходящих блюд для этого приёма пищи нет") from e
    _fill_item(row, item)
    db.commit()
    return plan_out(plan)


class LogMenuIn(BaseModel):
    item_ids: list[int] | None = None


@router.post("/{plan_id}/log", response_model=list[DiaryEntryOut], status_code=status.HTTP_201_CREATED)
def log_plan(plan_id: int, data: LogMenuIn, user: CurrentUser, db: DbSession) -> list[DiaryEntry]:
    """Copy menu items (all, or the selected ones) into the diary for the plan's date."""
    plan = _owned_plan(db, user, plan_id)
    items = [i for i in plan.items if data.item_ids is None or i.id in data.item_ids]
    entries = []
    for item in items:
        dish = db.get(Dish, item.dish_id) if item.dish_id else None
        if dish is None:
            continue
        entries.append(add_entry(db, user, plan.plan_date, item.meal_type, dish=dish, servings=item.servings))
    db.commit()
    return entries
