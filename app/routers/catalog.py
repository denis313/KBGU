from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.exc import IntegrityError

from app.deps import CurrentUser, DbSession
from app.models import DietType, Dish, Food, FoodGroup, FoodOverride, MealType
from app.schemas import DishOut, FoodIn, FoodOut, NutritionIn
from app.services.foods import NUTRIENTS, food_out, used_by_others, user_overrides
from app.services.profiles import dish_out

router = APIRouter(prefix="/api", tags=["catalog"])


@router.get("/foods", response_model=list[FoodOut])
def search_foods(
    user: CurrentUser,
    db: DbSession,
    q: str = "",
    mine: bool = False,
    limit: int = Query(30, ge=1, le=100),
) -> list[FoodOut]:
    """Search the shared catalogue; foods the user added or corrected come first.

    `mine=true` lists only foods the user added or has their own values for.
    """
    has_own_values = FoodOverride.user_id.is_not(None)
    is_mine = or_(has_own_values, Food.created_by_id == user.id)
    stmt = select(Food).outerjoin(
        FoodOverride, and_(FoodOverride.food_id == Food.id, FoodOverride.user_id == user.id)
    )
    if mine:
        stmt = stmt.where(is_mine)
    if q.strip():
        stmt = stmt.where(Food.name.ilike(f"%{q.strip()}%"))
    foods = db.scalars(stmt.order_by(case((is_mine, 0), else_=1), Food.name).limit(limit)).all()
    overrides = user_overrides(db, user.id, [f.id for f in foods])
    return [food_out(db, f, user.id, overrides) for f in foods]


def _food(db: DbSession, food_id: int) -> Food:
    food = db.get(Food, food_id)
    if food is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Продукт не найден")
    return food


def _check_unique_name(db: DbSession, name: str, exclude_id: int | None = None) -> None:
    stmt = select(Food.name).where(func.lower(Food.name) == name.lower())
    if exclude_id is not None:
        stmt = stmt.where(Food.id != exclude_id)
    existing = db.scalar(stmt)
    if existing is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"«{existing}» уже есть в общей базе. Найдите его в поиске — при необходимости поправьте КБЖУ для себя.",
        )


def _out(db: DbSession, food: Food, user_id: int) -> FoodOut:
    return food_out(db, food, user_id, user_overrides(db, user_id, [food.id]))


@router.post("/foods", response_model=FoodOut, status_code=status.HTTP_201_CREATED)
def create_food(data: FoodIn, user: CurrentUser, db: DbSession) -> FoodOut:
    """Add a food to the shared catalogue; it becomes visible to every user."""
    _check_unique_name(db, data.name)
    food = Food(created_by_id=user.id, **data.model_dump(exclude={"food_group"}), food_group=FoodGroup(data.food_group))
    db.add(food)
    try:
        db.commit()
    except IntegrityError:  # someone added the same name a moment ago
        db.rollback()
        _check_unique_name(db, data.name)
        raise
    return _out(db, food, user.id)


@router.put("/foods/{food_id}", response_model=FoodOut)
def update_food(food_id: int, data: FoodIn, user: CurrentUser, db: DbSession) -> FoodOut:
    """Change a food for everyone: only its contributor, and only while nobody else uses it."""
    food = _food(db, food_id)
    if food.created_by_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Это продукт общей базы — поменять КБЖУ можно только для себя")
    if used_by_others(db, food.id, user.id):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Продуктом уже пользуются другие — изменения можно сохранить только для себя",
        )
    _check_unique_name(db, data.name, exclude_id=food.id)
    for key, value in data.model_dump(exclude={"food_group"}).items():
        setattr(food, key, value)
    food.food_group = FoodGroup(data.food_group)
    db.commit()
    return _out(db, food, user.id)


@router.put("/foods/{food_id}/personal", response_model=FoodOut)
def set_personal_values(food_id: int, data: NutritionIn, user: CurrentUser, db: DbSession) -> FoodOut:
    """Save the user's own nutrition values for a food; nobody else sees them.

    Values equal to the shared ones simply remove the personal copy.
    """
    food = _food(db, food_id)
    own = db.get(FoodOverride, (user.id, food.id))
    if all(abs(getattr(data, n) - getattr(food, n)) < 1e-9 for n in NUTRIENTS):
        if own is not None:
            db.delete(own)
    else:
        own = own or FoodOverride(user_id=user.id, food_id=food.id)
        for n in NUTRIENTS:
            setattr(own, n, getattr(data, n))
        db.add(own)
    db.commit()
    return _out(db, food, user.id)


@router.delete("/foods/{food_id}/personal", response_model=FoodOut)
def reset_personal_values(food_id: int, user: CurrentUser, db: DbSession) -> FoodOut:
    """Go back to the shared values. Diary entries keep the numbers they were logged with."""
    food = _food(db, food_id)
    own = db.get(FoodOverride, (user.id, food.id))
    if own is not None:
        db.delete(own)
        db.commit()
    return _out(db, food, user.id)


@router.delete("/foods/{food_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_food(food_id: int, user: CurrentUser, db: DbSession) -> None:
    """Remove a food from the catalogue: its contributor only, while nobody else uses it."""
    food = _food(db, food_id)
    if food.created_by_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Удалить можно только продукт, который добавили вы")
    if used_by_others(db, food.id, user.id):
        raise HTTPException(status.HTTP_409_CONFLICT, "Продуктом уже пользуются другие — удалить его нельзя")
    db.delete(food)
    db.commit()


@router.get("/dishes", response_model=list[DishOut])
def list_dishes(
    db: DbSession,
    user: CurrentUser,
    meal_type: MealType | None = None,
    diet: DietType | None = None,
    exclude_allergens: list[str] = Query([]),
    q: str = "",
) -> list[DishOut]:
    stmt = select(Dish).order_by(Dish.meal_type, Dish.name)
    if meal_type:
        stmt = stmt.where(Dish.meal_type == meal_type)
    if q.strip():
        stmt = stmt.where(Dish.name.ilike(f"%{q.strip()}%"))
    dishes = db.scalars(stmt).all()
    if diet:
        dishes = [d for d in dishes if diet.value in d.diets]
    if exclude_allergens:
        dishes = [d for d in dishes if not set(exclude_allergens) & set(d.allergens)]
    overrides = user_overrides(db, user.id)
    return [dish_out(d, overrides) for d in dishes]


@router.get("/dishes/{dish_id}", response_model=DishOut)
def get_dish(dish_id: int, db: DbSession, user: CurrentUser) -> DishOut:
    dish = db.get(Dish, dish_id)
    if dish is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Блюдо не найдено")
    return dish_out(dish, user_overrides(db, user.id))
