from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, or_, select

from app.deps import CurrentUser, DbSession
from app.models import DietType, Dish, Food, FoodGroup, MealType
from app.schemas import DishOut, FoodIn, FoodOut
from app.services.profiles import dish_out, food_out

router = APIRouter(prefix="/api", tags=["catalog"])


@router.get("/foods", response_model=list[FoodOut])
def search_foods(
    user: CurrentUser,
    db: DbSession,
    q: str = "",
    mine: bool = False,
    limit: int = Query(30, ge=1, le=100),
) -> list[FoodOut]:
    """Catalogue plus the user's own foods (own first); `mine=true` lists only the user's foods."""
    visible = Food.owner_id == user.id if mine else or_(Food.owner_id.is_(None), Food.owner_id == user.id)
    stmt = select(Food).where(visible)
    if q.strip():
        stmt = stmt.where(Food.name.ilike(f"%{q.strip()}%"))
    stmt = stmt.order_by(Food.owner_id.is_(None), Food.name).limit(limit)
    return [food_out(f) for f in db.scalars(stmt)]


def _own_food(db: DbSession, user_id: int, food_id: int) -> Food:
    food = db.get(Food, food_id)
    if food is None or food.owner_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ваш продукт не найден")
    return food


def _check_unique_name(db: DbSession, user_id: int, name: str, exclude_id: int | None = None) -> None:
    stmt = select(Food.id).where(Food.owner_id == user_id, func.lower(Food.name) == name.lower())
    if exclude_id is not None:
        stmt = stmt.where(Food.id != exclude_id)
    if db.scalar(stmt) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, f"У вас уже есть продукт «{name}»")


def _apply(food: Food, data: FoodIn) -> None:
    for key, value in data.model_dump(exclude={"food_group"}).items():
        setattr(food, key, value)
    food.food_group = FoodGroup(data.food_group)


@router.post("/foods", response_model=FoodOut, status_code=status.HTTP_201_CREATED)
def create_food(data: FoodIn, user: CurrentUser, db: DbSession) -> FoodOut:
    _check_unique_name(db, user.id, data.name)
    food = Food(owner_id=user.id)
    _apply(food, data)
    db.add(food)
    db.commit()
    return food_out(food)


@router.put("/foods/{food_id}", response_model=FoodOut)
def update_food(food_id: int, data: FoodIn, user: CurrentUser, db: DbSession) -> FoodOut:
    """Edit an own food. Diary entries keep the nutrition they were logged with."""
    food = _own_food(db, user.id, food_id)
    _check_unique_name(db, user.id, data.name, exclude_id=food.id)
    _apply(food, data)
    db.commit()
    return food_out(food)


@router.delete("/foods/{food_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_food(food_id: int, user: CurrentUser, db: DbSession) -> None:
    """Delete an own food. Diary entries that used it keep their name and numbers."""
    db.delete(_own_food(db, user.id, food_id))
    db.commit()


@router.get("/dishes", response_model=list[DishOut])
def list_dishes(
    db: DbSession,
    _: CurrentUser,
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
    return [dish_out(d) for d in dishes]


@router.get("/dishes/{dish_id}", response_model=DishOut)
def get_dish(dish_id: int, db: DbSession, _: CurrentUser) -> DishOut:
    dish = db.get(Dish, dish_id)
    if dish is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Блюдо не найдено")
    return dish_out(dish)
