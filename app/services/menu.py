"""Daily menu generation from the catalogue of ready-made dishes.

Recommendations combine both approaches: a curated database of ready-made
dishes (recipes with exact nutrition) plus a generator that assembles them
into a day that hits the user's calorie and macro targets.

Algorithm:
  1. Filter dishes by the user's diet type and excluded allergens.
  2. Build candidate days (one dish per meal slot). Small catalogues are
     enumerated exhaustively, large ones are randomly sampled.
  3. For every candidate, scale each dish's servings (0.5-2.0 in 0.25 steps) to
     that meal's calorie share, then improve servings with a greedy local search.
  4. Score = weighted relative error of calories, protein, fat and carbs, plus
     per-meal balance; protein shortfall is penalised harder than excess.
  5. Pick randomly among the near-best candidates (seeded) so "regenerate"
     yields variety while staying on target. Dishes eaten recently are
     down-weighted.
"""

import itertools
import random
from dataclasses import dataclass

from app.models import MealType

SERVING_STEP = 0.25
MIN_SERVINGS = 0.5
MAX_SERVINGS = 2.0
MAX_EXHAUSTIVE = 5000
SAMPLES = 1500
TOP_K = 6


@dataclass(frozen=True)
class DishOption:
    id: int
    name: str
    meal_type: MealType
    kcal: float
    protein: float
    fat: float
    carbs: float
    grams: float
    diets: tuple[str, ...] = ()
    allergens: tuple[str, ...] = ()


@dataclass(frozen=True)
class Targets:
    kcal: float
    protein: float
    fat: float
    carbs: float


@dataclass
class MenuItem:
    dish: DishOption
    meal_type: MealType
    servings: float

    @property
    def kcal(self) -> float:
        return self.dish.kcal * self.servings

    @property
    def protein(self) -> float:
        return self.dish.protein * self.servings

    @property
    def fat(self) -> float:
        return self.dish.fat * self.servings

    @property
    def carbs(self) -> float:
        return self.dish.carbs * self.servings

    @property
    def grams(self) -> float:
        return self.dish.grams * self.servings


@dataclass
class GeneratedMenu:
    items: list[MenuItem]
    score: float
    seed: int

    @property
    def totals(self) -> Targets:
        return Targets(
            kcal=sum(i.kcal for i in self.items),
            protein=sum(i.protein for i in self.items),
            fat=sum(i.fat for i in self.items),
            carbs=sum(i.carbs for i in self.items),
        )


class NoDishesError(ValueError):
    def __init__(self, meal: MealType):
        super().__init__(f"No dishes match your diet and allergen settings for {meal.value}.")
        self.meal = meal


def filter_dishes(dishes: list[DishOption], diet: str, excluded_allergens: list[str]) -> list[DishOption]:
    excluded = set(excluded_allergens)
    return [d for d in dishes if diet in d.diets and not excluded & set(d.allergens)]


def _snap(servings: float) -> float:
    snapped = round(servings / SERVING_STEP) * SERVING_STEP
    return min(max(snapped, MIN_SERVINGS), MAX_SERVINGS)


def _score(combo: tuple[DishOption, ...], servings: list[float], meals: list[MealType],
           meal_kcal: dict[MealType, float], t: Targets) -> float:
    kcal = sum(d.kcal * s for d, s in zip(combo, servings))
    protein = sum(d.protein * s for d, s in zip(combo, servings))
    fat = sum(d.fat * s for d, s in zip(combo, servings))
    carbs = sum(d.carbs * s for d, s in zip(combo, servings))

    kcal_err = abs(kcal - t.kcal) / t.kcal
    protein_err = max(0.0, t.protein - protein) / t.protein + 0.3 * max(0.0, protein - 1.3 * t.protein) / t.protein
    fat_err = abs(fat - t.fat) / t.fat
    carb_err = abs(carbs - t.carbs) / t.carbs
    balance_err = sum(
        abs(d.kcal * s - meal_kcal[m]) for d, s, m in zip(combo, servings, meals)
    ) / t.kcal
    return 4 * kcal_err + 1.5 * protein_err + 0.7 * fat_err + 0.5 * carb_err + 0.4 * balance_err


def _fit_servings(combo: tuple[DishOption, ...], meals: list[MealType],
                  meal_kcal: dict[MealType, float], t: Targets) -> tuple[list[float], float]:
    servings = [_snap(meal_kcal[m] / d.kcal) for d, m in zip(combo, meals)]
    best = _score(combo, servings, meals, meal_kcal, t)
    improved = True
    while improved:
        improved = False
        for i in range(len(servings)):
            for delta in (SERVING_STEP, -SERVING_STEP):
                trial = servings.copy()
                trial[i] = min(max(trial[i] + delta, MIN_SERVINGS), MAX_SERVINGS)
                score = _score(combo, trial, meals, meal_kcal, t)
                if score < best - 1e-9:
                    servings, best, improved = trial, score, True
    return servings, best


def generate_menu(
    dishes: list[DishOption],
    targets: Targets,
    meal_split: dict[MealType, float],
    diet: str = "omnivore",
    excluded_allergens: list[str] | None = None,
    recent_dish_ids: set[int] | None = None,
    seed: int | None = None,
) -> GeneratedMenu:
    seed = seed if seed is not None else random.randrange(1, 2**31)
    rng = random.Random(seed)
    recent = recent_dish_ids or set()
    allowed = filter_dishes(dishes, diet, excluded_allergens or [])

    meals = list(meal_split)
    pools: list[list[DishOption]] = []
    for meal in meals:
        pool = [d for d in allowed if d.meal_type == meal and d.kcal > 0]
        if not pool:
            raise NoDishesError(meal)
        pools.append(pool)

    total = 1
    for pool in pools:
        total *= len(pool)
    if total <= MAX_EXHAUSTIVE:
        combos = list(itertools.product(*pools))
    else:
        weights = [[0.35 if d.id in recent else 1.0 for d in pool] for pool in pools]
        combos = list({tuple(rng.choices(pool, w)[0] for pool, w in zip(pools, weights)) for _ in range(SAMPLES)})

    scored = []
    for combo in combos:
        servings, score = _fit_servings(combo, meals, meal_split, targets)
        # Recently eaten dishes are allowed but made slightly less attractive.
        score += 0.05 * sum(d.id in recent for d in combo)
        scored.append((score, combo, servings))
    scored.sort(key=lambda s: s[0])

    best_score = scored[0][0]
    near_best = [s for s in scored[:TOP_K] if s[0] <= best_score * 1.25 + 0.03]
    score, combo, servings = rng.choice(near_best)
    items = [MenuItem(dish=d, meal_type=m, servings=s) for d, m, s in zip(combo, meals, servings)]
    return GeneratedMenu(items=items, score=round(score, 4), seed=seed)


def swap_dish(
    dishes: list[DishOption],
    meal: MealType,
    meal_kcal: float,
    protein_per_kcal: float,
    diet: str = "omnivore",
    excluded_allergens: list[str] | None = None,
    exclude_ids: set[int] | None = None,
    seed: int | None = None,
) -> MenuItem:
    """Pick a different dish for one meal slot, scaled to that slot's calories."""
    rng = random.Random(seed)
    exclude = exclude_ids or set()
    pool = [
        d for d in filter_dishes(dishes, diet, excluded_allergens or [])
        if d.meal_type == meal and d.id not in exclude and d.kcal > 0
    ]
    if not pool:
        raise NoDishesError(meal)

    target_protein = meal_kcal * protein_per_kcal
    ranked = []
    for d in pool:
        s = _snap(meal_kcal / d.kcal)
        kcal_err = abs(d.kcal * s - meal_kcal) / meal_kcal
        protein_err = max(0.0, target_protein - d.protein * s) / max(target_protein, 1)
        ranked.append((kcal_err * 4 + protein_err, d, s))
    ranked.sort(key=lambda r: r[0])
    _, dish, servings = rng.choice(ranked[:3])
    return MenuItem(dish=dish, meal_type=meal, servings=servings)
