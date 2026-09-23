"""Energy (calorie) and macronutrient target calculation.

Method, and why it was chosen over the alternatives:

1. Basal metabolic rate (BMR)
   * Mifflin-St Jeor (1990) is the default. In the systematic review by
     Frankenfield et al. (J Am Diet Assoc, 2005) it predicted resting metabolic
     rate within +/-10 % of measured values for the largest share of non-obese
     and obese adults, beating Harris-Benedict, Owen and WHO/FAO equations. It is
     the equation recommended by the Academy of Nutrition and Dietetics.
   * Katch-McArdle is used instead when the user provides body-fat %, because it
     is based on lean body mass and is more accurate for lean or very muscular
     people, whom weight-only equations underestimate.
   * Revised Harris-Benedict (Roza & Shizgal, 1984) is reported for comparison only.

2. Total daily energy expenditure (TDEE) = BMR x physical activity level (PAL).

3. Goal adjustment: ~7700 kcal per kg of body mass change. A deficit is capped
   at 25 % of TDEE and the intake never drops below 1200 (women) / 1500 (men)
   kcal; a surplus is capped at 15 % of TDEE. Every clamp adds a warning.

4. Macros: protein by body weight (2.0 g/kg when cutting to protect lean mass,
   1.6 g/kg maintenance, 1.8 g/kg bulking); for BMI >= 30 the adjusted body
   weight is used so protein is not overestimated. Fat is 30 % of energy (and at
   least 0.6 g/kg); carbohydrates take the remainder.
"""

from dataclasses import dataclass, field
from datetime import date

from app.models import ActivityLevel, Goal, MealType, Sex

KCAL_PER_KG = 7700
KCAL_PER_G = {"protein": 4, "fat": 9, "carbs": 4}

ACTIVITY_FACTORS: dict[ActivityLevel, float] = {
    ActivityLevel.sedentary: 1.2,  # desk job, little or no exercise
    ActivityLevel.light: 1.375,  # light exercise 1-3 days/week
    ActivityLevel.moderate: 1.55,  # moderate exercise 3-5 days/week
    ActivityLevel.active: 1.725,  # hard exercise 6-7 days/week
    ActivityLevel.very_active: 1.9,  # physical job plus training
}

MIN_INTAKE: dict[Sex, float] = {Sex.female: 1200, Sex.male: 1500}
MAX_DEFICIT_SHARE = 0.25
MAX_SURPLUS_SHARE = 0.15

PROTEIN_PER_KG: dict[Goal, float] = {Goal.lose: 2.0, Goal.maintain: 1.6, Goal.gain: 1.8}
FAT_SHARE = 0.30
MIN_FAT_PER_KG = 0.6
MIN_CARB_SHARE = 0.20

MEAL_SPLITS: dict[int, dict[MealType, float]] = {
    3: {MealType.breakfast: 0.30, MealType.lunch: 0.40, MealType.dinner: 0.30},
    4: {MealType.breakfast: 0.25, MealType.lunch: 0.35, MealType.dinner: 0.30, MealType.snack: 0.10},
}


@dataclass(frozen=True)
class BodyParams:
    sex: Sex
    age: int
    height_cm: float
    weight_kg: float
    activity_level: ActivityLevel
    goal: Goal = Goal.maintain
    weekly_rate_kg: float = 0.5
    body_fat_pct: float | None = None


@dataclass
class EnergyPlan:
    bmr: float
    bmr_formula: str
    bmr_estimates: dict[str, float]
    activity_factor: float
    tdee: float
    daily_adjustment: float
    target_kcal: float
    protein_g: float
    fat_g: float
    carbs_g: float
    bmi: float
    meal_split: dict[MealType, float]
    warnings: list[str] = field(default_factory=list)


def age_on(birth_date: date, today: date | None = None) -> int:
    today = today or date.today()
    return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))


def mifflin_st_jeor(sex: Sex, weight_kg: float, height_cm: float, age: int) -> float:
    base = 10 * weight_kg + 6.25 * height_cm - 5 * age
    return base + 5 if sex == Sex.male else base - 161


def katch_mcardle(weight_kg: float, body_fat_pct: float) -> float:
    lean_mass = weight_kg * (1 - body_fat_pct / 100)
    return 370 + 21.6 * lean_mass


def harris_benedict_revised(sex: Sex, weight_kg: float, height_cm: float, age: int) -> float:
    if sex == Sex.male:
        return 88.362 + 13.397 * weight_kg + 4.799 * height_cm - 5.677 * age
    return 447.593 + 9.247 * weight_kg + 3.098 * height_cm - 4.330 * age


def bmi(weight_kg: float, height_cm: float) -> float:
    return weight_kg / (height_cm / 100) ** 2


def protein_reference_weight(weight_kg: float, height_cm: float) -> float:
    """Actual weight, or adjusted body weight (IBW + 40 % of excess) when BMI >= 30."""
    if bmi(weight_kg, height_cm) < 30:
        return weight_kg
    ideal = 22 * (height_cm / 100) ** 2
    return ideal + 0.4 * (weight_kg - ideal)


def calculate(p: BodyParams, meals_per_day: int = 4) -> EnergyPlan:
    warnings: list[str] = []

    estimates = {
        "mifflin_st_jeor": mifflin_st_jeor(p.sex, p.weight_kg, p.height_cm, p.age),
        "harris_benedict": harris_benedict_revised(p.sex, p.weight_kg, p.height_cm, p.age),
    }
    if p.body_fat_pct is not None:
        estimates["katch_mcardle"] = katch_mcardle(p.weight_kg, p.body_fat_pct)
        formula = "katch_mcardle"
    else:
        formula = "mifflin_st_jeor"
    bmr_value = estimates[formula]

    factor = ACTIVITY_FACTORS[p.activity_level]
    tdee = bmr_value * factor

    adjustment = 0.0
    if p.goal == Goal.lose:
        adjustment = -p.weekly_rate_kg * KCAL_PER_KG / 7
        if -adjustment > tdee * MAX_DEFICIT_SHARE:
            adjustment = -tdee * MAX_DEFICIT_SHARE
            warnings.append(
                f"Requested weight-loss pace is too aggressive; deficit limited to "
                f"{MAX_DEFICIT_SHARE:.0%} of maintenance ({-adjustment:.0f} kcal/day)."
            )
    elif p.goal == Goal.gain:
        adjustment = p.weekly_rate_kg * KCAL_PER_KG / 7
        if adjustment > tdee * MAX_SURPLUS_SHARE:
            adjustment = tdee * MAX_SURPLUS_SHARE
            warnings.append(
                f"Requested weight-gain pace is too fast for lean gains; surplus limited to "
                f"{MAX_SURPLUS_SHARE:.0%} of maintenance ({adjustment:.0f} kcal/day)."
            )

    target = tdee + adjustment
    floor = MIN_INTAKE[p.sex]
    if target < floor:
        target = floor
        adjustment = target - tdee
        warnings.append(f"Target raised to the safe minimum of {floor:.0f} kcal/day.")

    body_mass_index = bmi(p.weight_kg, p.height_cm)
    if body_mass_index < 18.5 and p.goal == Goal.lose:
        warnings.append("BMI is below 18.5; weight loss is not recommended. Consult a doctor.")

    ref_weight = protein_reference_weight(p.weight_kg, p.height_cm)
    protein_g = PROTEIN_PER_KG[p.goal] * ref_weight
    fat_g = max(target * FAT_SHARE / KCAL_PER_G["fat"], MIN_FAT_PER_KG * ref_weight)
    min_carb_kcal = target * MIN_CARB_SHARE
    protein_kcal = protein_g * KCAL_PER_G["protein"]
    fat_kcal = fat_g * KCAL_PER_G["fat"]
    if target - protein_kcal - fat_kcal < min_carb_kcal:
        # Very low targets: trim protein so carbohydrates keep a minimal share.
        protein_kcal = max(target - fat_kcal - min_carb_kcal, 0)
        protein_g = protein_kcal / KCAL_PER_G["protein"]
    carbs_g = (target - protein_kcal - fat_kcal) / KCAL_PER_G["carbs"]

    split = MEAL_SPLITS.get(meals_per_day, MEAL_SPLITS[4])

    return EnergyPlan(
        bmr=round(bmr_value),
        bmr_formula=formula,
        bmr_estimates={k: round(v) for k, v in estimates.items()},
        activity_factor=factor,
        tdee=round(tdee),
        daily_adjustment=round(adjustment),
        target_kcal=round(target),
        protein_g=round(protein_g),
        fat_g=round(fat_g),
        carbs_g=round(carbs_g),
        bmi=round(body_mass_index, 1),
        meal_split={meal: round(target * share) for meal, share in split.items()},
        warnings=warnings,
    )
