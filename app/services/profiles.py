"""Glue between ORM rows and the pure calculation services."""

from app.models import Dish, Food, Profile
from app.schemas import DishOut, FoodOut, IngredientOut, ProfileOut
from app.services.calories import BodyParams, EnergyPlan, age_on, calculate
from app.services.menu import DishOption


def body_params(profile: Profile) -> BodyParams:
    return BodyParams(
        sex=profile.sex,
        age=age_on(profile.birth_date),
        height_cm=profile.height_cm,
        weight_kg=profile.weight_kg,
        body_fat_pct=profile.body_fat_pct,
        activity_level=profile.activity_level,
        goal=profile.goal,
        weekly_rate_kg=profile.weekly_rate_kg,
    )


def energy_plan(profile: Profile) -> EnergyPlan:
    return calculate(body_params(profile), profile.meals_per_day)


def profile_out(profile: Profile) -> ProfileOut:
    return ProfileOut(
        sex=profile.sex,
        birth_date=profile.birth_date,
        age=age_on(profile.birth_date),
        height_cm=profile.height_cm,
        weight_kg=profile.weight_kg,
        body_fat_pct=profile.body_fat_pct,
        activity_level=profile.activity_level,
        goal=profile.goal,
        weekly_rate_kg=profile.weekly_rate_kg,
        meals_per_day=profile.meals_per_day,
        diet_type=profile.diet_type,
        excluded_allergens=profile.excluded_allergens,
    )


def food_out(food: Food) -> FoodOut:
    return FoodOut(
        id=food.id,
        name=food.name,
        food_group=food.food_group.value,
        kcal=food.kcal,
        protein=food.protein,
        fat=food.fat,
        carbs=food.carbs,
        fiber=food.fiber,
        allergens=food.allergens,
        is_custom=food.owner_id is not None,
    )


def dish_out(dish: Dish) -> DishOut:
    return DishOut(
        id=dish.id,
        name=dish.name,
        meal_type=dish.meal_type,
        description=dish.description,
        prep_minutes=dish.prep_minutes,
        grams=round(dish.grams),
        kcal=round(dish.kcal),
        protein=round(dish.protein, 1),
        fat=round(dish.fat, 1),
        carbs=round(dish.carbs, 1),
        fiber=round(dish.fiber, 1),
        diets=dish.diets,
        allergens=dish.allergens,
        ingredients=[
            IngredientOut(food_id=i.food_id, name=i.food.name, grams=i.grams) for i in dish.ingredients
        ],
    )


def dish_option(dish: Dish) -> DishOption:
    return DishOption(
        id=dish.id,
        name=dish.name,
        meal_type=dish.meal_type,
        kcal=dish.kcal,
        protein=dish.protein,
        fat=dish.fat,
        carbs=dish.carbs,
        grams=dish.grams,
        diets=tuple(dish.diets),
        allergens=tuple(dish.allergens),
    )
