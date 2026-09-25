"""Load or refresh the food and dish catalogue: `python -m app.seed`. Idempotent."""

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import DiaryEntry, Dish, DishIngredient, Food, FoodGroup, MealType, MenuPlanItem
from app.seed.data import DISHES, FOODS
from app.seed.translations import DISH_NAMES_RU, FOOD_NAMES_RU


def rename_legacy(db: Session) -> None:
    """Rename rows from the English catalogue so the upsert below updates them in place."""
    foods = {f.name: f for f in db.scalars(select(Food).where(Food.owner_id.is_(None)))}
    for old, new in FOOD_NAMES_RU.items():
        if old in foods and new not in foods:
            foods[old].name = new
            db.execute(update(DiaryEntry).where(DiaryEntry.food_id == foods[old].id).values(name=new))
    dishes = {d.name: d for d in db.scalars(select(Dish))}
    for old, new in DISH_NAMES_RU.items():
        if old in dishes and new not in dishes:
            dishes[old].name = new
            db.execute(update(DiaryEntry).where(DiaryEntry.dish_id == dishes[old].id).values(name=new))
            db.execute(update(MenuPlanItem).where(MenuPlanItem.dish_id == dishes[old].id).values(name=new))
    db.flush()


def seed(db: Session) -> tuple[int, int]:
    rename_legacy(db)
    foods = {f.name: f for f in db.scalars(select(Food).where(Food.owner_id.is_(None)))}
    for name, (group, kcal, protein, fat, carbs, fiber, allergens) in FOODS.items():
        food = foods.get(name) or Food(name=name)
        food.food_group = FoodGroup(group)
        food.kcal, food.protein, food.fat, food.carbs, food.fiber = kcal, protein, fat, carbs, fiber
        food.allergens = allergens
        db.add(food)
        foods[name] = food
    db.flush()

    dishes = {d.name: d for d in db.scalars(select(Dish))}
    for name, (meal, minutes, description, ingredients) in DISHES.items():
        dish = dishes.get(name) or Dish(name=name)
        dish.meal_type = MealType(meal)
        dish.prep_minutes = minutes
        dish.description = description
        if dish.id is not None:
            # Delete old rows first: new ingredients reuse the same composite keys.
            dish.ingredients.clear()
            db.flush()
        dish.ingredients = [DishIngredient(food=foods[f], grams=g) for f, g in ingredients.items()]
        db.add(dish)
    db.commit()
    return len(FOODS), len(DISHES)


if __name__ == "__main__":
    with SessionLocal() as session:
        n_foods, n_dishes = seed(session)
    print(f"Seeded {n_foods} foods and {n_dishes} dishes.")
