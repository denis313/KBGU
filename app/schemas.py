from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.models import ActivityLevel, DietType, Goal, MealType, Sex
from app.seed.data import ALLERGENS


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- auth ----------
class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=100)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TelegramLoginIn(BaseModel):
    init_data: str = Field(min_length=1, max_length=4096)


class UserOut(ORM):
    id: int
    email: str | None
    name: str
    has_profile: bool = False


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ---------- profile & energy ----------
class BodyBase(BaseModel):
    sex: Sex
    height_cm: float = Field(ge=100, le=250)
    weight_kg: float = Field(ge=30, le=350)
    body_fat_pct: float | None = Field(default=None, ge=3, le=60)
    activity_level: ActivityLevel
    goal: Goal = Goal.maintain
    weekly_rate_kg: float = Field(default=0.5, ge=0, le=1.0)
    meals_per_day: Literal[3, 4] = 4


class ProfileIn(BodyBase):
    birth_date: date
    diet_type: DietType = DietType.omnivore
    excluded_allergens: list[str] = []

    @field_validator("birth_date")
    @classmethod
    def plausible_age(cls, v: date) -> date:
        from app.services.calories import age_on

        if not 14 <= age_on(v) <= 100:
            raise ValueError("age must be between 14 and 100")
        return v

    @field_validator("excluded_allergens")
    @classmethod
    def known_allergens(cls, v: list[str]) -> list[str]:
        unknown = set(v) - set(ALLERGENS)
        if unknown:
            raise ValueError(f"unknown allergens: {sorted(unknown)}; allowed: {ALLERGENS}")
        return sorted(set(v))


class ProfileOut(ProfileIn, ORM):
    age: int

    @field_validator("birth_date")
    @classmethod
    def plausible_age(cls, v: date) -> date:  # stored values are not re-validated
        return v


class CalculatorIn(BodyBase):
    age: int = Field(ge=14, le=100)


class EnergyPlanOut(ORM):
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
    warnings: list[str]


class WeightIn(BaseModel):
    logged_on: date = Field(default_factory=date.today)
    weight_kg: float = Field(ge=30, le=350)


class WeightOut(ORM):
    id: int
    logged_on: date
    weight_kg: float


# ---------- foods & dishes ----------
class Nutrition(BaseModel):
    kcal: float
    protein: float
    fat: float
    carbs: float


class FoodIn(Nutrition):
    name: str = Field(min_length=1, max_length=120)
    food_group: Literal["meat", "fish", "dairy", "egg", "plant"] = "plant"
    kcal: float = Field(ge=0, le=900)
    protein: float = Field(ge=0, le=100)
    fat: float = Field(ge=0, le=100)
    carbs: float = Field(ge=0, le=100)
    fiber: float = Field(default=0, ge=0, le=100)
    allergens: list[str] = []


class FoodOut(Nutrition, ORM):
    id: int
    name: str
    food_group: str
    fiber: float
    allergens: list[str]
    is_custom: bool


class IngredientOut(BaseModel):
    food_id: int
    name: str
    grams: float


class DishOut(Nutrition, ORM):
    id: int
    name: str
    meal_type: MealType
    description: str
    prep_minutes: int
    grams: float
    fiber: float
    diets: list[str]
    allergens: list[str]
    ingredients: list[IngredientOut]


# ---------- diary ----------
class DiaryEntryIn(BaseModel):
    eaten_on: date = Field(default_factory=date.today)
    meal_type: MealType
    food_id: int | None = None
    dish_id: int | None = None
    grams: float | None = Field(default=None, gt=0, le=3000)
    servings: float | None = Field(default=None, gt=0, le=10)

    @model_validator(mode="after")
    def one_source(self) -> "DiaryEntryIn":
        if (self.food_id is None) == (self.dish_id is None):
            raise ValueError("provide exactly one of food_id or dish_id")
        if self.food_id is not None and self.grams is None:
            raise ValueError("grams is required for a food")
        return self


class DiaryEntryUpdate(BaseModel):
    meal_type: MealType | None = None
    grams: float | None = Field(default=None, gt=0, le=3000)
    servings: float | None = Field(default=None, gt=0, le=10)


class DiaryEntryOut(Nutrition, ORM):
    id: int
    eaten_on: date
    meal_type: MealType
    food_id: int | None
    dish_id: int | None
    name: str
    grams: float
    servings: float | None


class DaySummaryOut(BaseModel):
    date: date
    totals: Nutrition
    targets: Nutrition | None
    remaining_kcal: float | None
    entries: list[DiaryEntryOut]


class DayTotalsOut(Nutrition):
    date: date


# ---------- menu ----------
class MenuGenerateIn(BaseModel):
    plan_date: date = Field(default_factory=date.today)
    seed: int | None = Field(default=None, ge=1, le=2**31 - 1)


class MenuItemOut(Nutrition, ORM):
    id: int
    dish_id: int | None
    meal_type: MealType
    meal_target_kcal: float
    name: str
    servings: float
    grams: float


class MenuPlanOut(ORM):
    id: int
    plan_date: date
    seed: int
    targets: Nutrition
    totals: Nutrition
    items: list[MenuItemOut]
