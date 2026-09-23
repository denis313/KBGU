import pytest

from app.models import MealType
from app.services.menu import DishOption, NoDishesError, Targets, generate_menu, swap_dish

ALL = ("omnivore", "pescatarian", "vegetarian", "vegan")


def dish(i, meal, kcal, p, f, c, diets=ALL, allergens=()):
    return DishOption(i, f"dish {i}", meal, kcal, p, f, c, 300, tuple(diets), tuple(allergens))


CATALOGUE = [
    dish(1, MealType.breakfast, 400, 25, 12, 50),
    dish(2, MealType.breakfast, 350, 10, 15, 45, allergens=("nuts",)),
    dish(3, MealType.lunch, 550, 45, 15, 55, diets=("omnivore",)),
    dish(4, MealType.lunch, 500, 20, 12, 80),
    dish(5, MealType.dinner, 500, 40, 18, 45, diets=("omnivore", "pescatarian")),
    dish(6, MealType.dinner, 480, 25, 15, 65),
    dish(7, MealType.snack, 180, 15, 5, 15),
    dish(8, MealType.snack, 170, 5, 9, 20),
]
SPLIT = {MealType.breakfast: 500, MealType.lunch: 700, MealType.dinner: 600, MealType.snack: 200}
TARGETS = Targets(kcal=2000, protein=140, fat=65, carbs=210)


def test_menu_hits_calorie_target_and_covers_every_meal():
    menu = generate_menu(CATALOGUE, TARGETS, SPLIT, seed=1)
    assert [i.meal_type for i in menu.items] == list(SPLIT)
    assert menu.totals.kcal == pytest.approx(TARGETS.kcal, rel=0.08)
    assert all(0.5 <= i.servings <= 2.0 and (i.servings * 4).is_integer() for i in menu.items)


def test_same_seed_is_reproducible():
    a = generate_menu(CATALOGUE, TARGETS, SPLIT, seed=7)
    b = generate_menu(CATALOGUE, TARGETS, SPLIT, seed=7)
    assert [(i.dish.id, i.servings) for i in a.items] == [(i.dish.id, i.servings) for i in b.items]


def test_diet_and_allergens_are_respected():
    menu = generate_menu(CATALOGUE, TARGETS, SPLIT, diet="vegan", excluded_allergens=["nuts"], seed=3)
    ids = {i.dish.id for i in menu.items}
    assert ids.isdisjoint({2, 3, 5})


def test_missing_meal_options_raise():
    with pytest.raises(NoDishesError):
        generate_menu(CATALOGUE[:2], TARGETS, SPLIT, seed=1)


def test_swap_returns_a_different_dish_scaled_to_the_meal():
    item = swap_dish(CATALOGUE, MealType.lunch, 700, 0.07, exclude_ids={3}, seed=1)
    assert item.dish.id == 4
    assert item.kcal == pytest.approx(700, rel=0.15)


def test_large_catalogue_uses_sampling_and_stays_on_target():
    big = [dish(100 + i, meal, 300 + 13 * i, 20 + i % 15, 10 + i % 7, 40 + i % 20)
           for i in range(40) for meal in MealType]
    menu = generate_menu(big, TARGETS, SPLIT, seed=5)
    assert menu.totals.kcal == pytest.approx(TARGETS.kcal, rel=0.05)
