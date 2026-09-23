"""Load or refresh the food and dish catalogue: `python -m app.seed`. Idempotent."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Dish, DishIngredient, Food, FoodGroup, MealType
from app.seed.data import DISHES, FOODS


def seed(db: Session) -> tuple[int, int]:
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
