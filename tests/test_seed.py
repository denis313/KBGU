from sqlalchemy import func, select

from app.database import SessionLocal
from app.models import DiaryEntry, Dish, Food, MealType, User
from app.seed.__main__ import seed
from app.seed.data import DISHES, FOODS


def test_seed_renames_english_catalogue_in_place():
    """A database seeded before the translation gets Russian names, not duplicates."""
    with SessionLocal() as db:
        banana = db.scalar(select(Food).where(Food.name == "Банан"))
        dish = db.scalar(select(Dish).where(Dish.name == "Яблоко с миндалём"))
        banana.name, dish.name = "Banana", "Apple with almonds"
        user = User(email="legacy@example.com", password_hash="x", name="L")
        db.add(user)
        db.flush()
        entry = DiaryEntry(user_id=user.id, eaten_on=func.current_date(), meal_type=MealType.snack,
                           dish_id=dish.id, name="Apple with almonds", grams=170, kcal=194,
                           protein=5, fat=10, carbs=25)
        db.add(entry)
        db.commit()
        food_id, dish_id = banana.id, dish.id

        seed(db)

        assert db.scalar(select(func.count()).select_from(Food).where(Food.owner_id.is_(None))) == len(FOODS)
        assert db.scalar(select(func.count()).select_from(Dish)) == len(DISHES)
        assert db.get(Food, food_id).name == "Банан"
        assert db.get(Dish, dish_id).name == "Яблоко с миндалём"
        db.refresh(entry)
        assert entry.name == "Яблоко с миндалём"
