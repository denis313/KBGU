from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import or_, select

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
    limit: int = Query(30, ge=1, le=100),
) -> list[FoodOut]:
    stmt = select(Food).where(or_(Food.owner_id.is_(None), Food.owner_id == user.id))
    if q.strip():
        stmt = stmt.where(Food.name.ilike(f"%{q.strip()}%"))
    stmt = stmt.order_by(Food.owner_id.is_(None), Food.name).limit(limit)
    return [food_out(f) for f in db.scalars(stmt)]


@router.post("/foods", response_model=FoodOut, status_code=status.HTTP_201_CREATED)
def create_food(data: FoodIn, user: CurrentUser, db: DbSession) -> FoodOut:
    food = Food(**data.model_dump(exclude={"food_group"}), food_group=FoodGroup(data.food_group), owner_id=user.id)
    db.add(food)
    db.commit()
    return food_out(food)


@router.delete("/foods/{food_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_food(food_id: int, user: CurrentUser, db: DbSession) -> None:
    food = db.get(Food, food_id)
    if food is None or food.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ваш продукт не найден")
    db.delete(food)
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
