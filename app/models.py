"""SQLAlchemy ORM models.

Nutrition values of foods are stored per 100 g. Dishes (ready-made menu options)
are recipes made of foods, so their nutrition is always derived from ingredients
and stays consistent when a food is corrected. Diary entries and saved menu
items keep a snapshot of the numbers they were logged with, so editing a food
never rewrites a user's history.
"""

import enum
from datetime import date, datetime

from sqlalchemy import (
    ARRAY,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Sex(str, enum.Enum):
    male = "male"
    female = "female"


class ActivityLevel(str, enum.Enum):
    sedentary = "sedentary"
    light = "light"
    moderate = "moderate"
    active = "active"
    very_active = "very_active"


class Goal(str, enum.Enum):
    lose = "lose"
    maintain = "maintain"
    gain = "gain"


class DietType(str, enum.Enum):
    omnivore = "omnivore"
    pescatarian = "pescatarian"
    vegetarian = "vegetarian"
    vegan = "vegan"


class MealType(str, enum.Enum):
    breakfast = "breakfast"
    lunch = "lunch"
    dinner = "dinner"
    snack = "snack"


class FoodGroup(str, enum.Enum):
    meat = "meat"
    fish = "fish"
    dairy = "dairy"
    egg = "egg"
    plant = "plant"


def _enum(cls: type[enum.Enum], name: str) -> Enum:
    return Enum(cls, name=name, values_callable=lambda e: [m.value for m in e])


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    profile: Mapped["Profile | None"] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False
    )
    weight_logs: Mapped[list["WeightLog"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    diary_entries: Mapped[list["DiaryEntry"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    menu_plans: Mapped[list["MenuPlan"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Profile(Base):
    __tablename__ = "profiles"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    sex: Mapped[Sex] = mapped_column(_enum(Sex, "sex"))
    birth_date: Mapped[date] = mapped_column(Date)
    height_cm: Mapped[float] = mapped_column(Float)
    weight_kg: Mapped[float] = mapped_column(Float)
    body_fat_pct: Mapped[float | None] = mapped_column(Float)
    activity_level: Mapped[ActivityLevel] = mapped_column(_enum(ActivityLevel, "activity_level"))
    goal: Mapped[Goal] = mapped_column(_enum(Goal, "goal"))
    weekly_rate_kg: Mapped[float] = mapped_column(Float, default=0.5)
    diet_type: Mapped[DietType] = mapped_column(_enum(DietType, "diet_type"), default=DietType.omnivore)
    excluded_allergens: Mapped[list[str]] = mapped_column(ARRAY(String(30)), default=list)
    meals_per_day: Mapped[int] = mapped_column(Integer, default=4)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship(back_populates="profile")


class WeightLog(Base):
    __tablename__ = "weight_logs"
    __table_args__ = (UniqueConstraint("user_id", "logged_on"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    logged_on: Mapped[date] = mapped_column(Date)
    weight_kg: Mapped[float] = mapped_column(Float)

    user: Mapped[User] = relationship(back_populates="weight_logs")


class Food(Base):
    """A food with nutrition per 100 g. owner_id is NULL for the shared catalogue."""

    __tablename__ = "foods"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    food_group: Mapped[FoodGroup] = mapped_column(_enum(FoodGroup, "food_group"))
    kcal: Mapped[float] = mapped_column(Float)
    protein: Mapped[float] = mapped_column(Float)
    fat: Mapped[float] = mapped_column(Float)
    carbs: Mapped[float] = mapped_column(Float)
    fiber: Mapped[float] = mapped_column(Float, default=0)
    allergens: Mapped[list[str]] = mapped_column(ARRAY(String(30)), default=list)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)


class Dish(Base):
    """A ready-made menu option: a recipe of foods, one serving."""

    __tablename__ = "dishes"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    meal_type: Mapped[MealType] = mapped_column(_enum(MealType, "meal_type"), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    prep_minutes: Mapped[int] = mapped_column(Integer, default=15)

    ingredients: Mapped[list["DishIngredient"]] = relationship(
        back_populates="dish", cascade="all, delete-orphan", lazy="selectin"
    )

    def _sum(self, attr: str) -> float:
        return sum(getattr(i.food, attr) * i.grams / 100 for i in self.ingredients)

    @property
    def grams(self) -> float:
        return sum(i.grams for i in self.ingredients)

    @property
    def kcal(self) -> float:
        return self._sum("kcal")

    @property
    def protein(self) -> float:
        return self._sum("protein")

    @property
    def fat(self) -> float:
        return self._sum("fat")

    @property
    def carbs(self) -> float:
        return self._sum("carbs")

    @property
    def fiber(self) -> float:
        return self._sum("fiber")

    @property
    def allergens(self) -> list[str]:
        return sorted({a for i in self.ingredients for a in i.food.allergens})

    @property
    def diets(self) -> list[str]:
        """Diet types this dish is compatible with, derived from its ingredients."""
        groups = {i.food.food_group for i in self.ingredients}
        diets = [DietType.omnivore]
        if FoodGroup.meat not in groups:
            diets.append(DietType.pescatarian)
            if FoodGroup.fish not in groups:
                diets.append(DietType.vegetarian)
                if not groups & {FoodGroup.dairy, FoodGroup.egg}:
                    diets.append(DietType.vegan)
        return [d.value for d in diets]


class DishIngredient(Base):
    __tablename__ = "dish_ingredients"

    dish_id: Mapped[int] = mapped_column(ForeignKey("dishes.id", ondelete="CASCADE"), primary_key=True)
    food_id: Mapped[int] = mapped_column(ForeignKey("foods.id", ondelete="RESTRICT"), primary_key=True)
    grams: Mapped[float] = mapped_column(Float)

    dish: Mapped[Dish] = relationship(back_populates="ingredients")
    food: Mapped[Food] = relationship(lazy="joined")


class DiaryEntry(Base):
    __tablename__ = "diary_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    eaten_on: Mapped[date] = mapped_column(Date)
    meal_type: Mapped[MealType] = mapped_column(_enum(MealType, "meal_type"))
    food_id: Mapped[int | None] = mapped_column(ForeignKey("foods.id", ondelete="SET NULL"))
    dish_id: Mapped[int | None] = mapped_column(ForeignKey("dishes.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String(120))
    servings: Mapped[float | None] = mapped_column(Float)
    grams: Mapped[float] = mapped_column(Float)
    kcal: Mapped[float] = mapped_column(Float)
    protein: Mapped[float] = mapped_column(Float)
    fat: Mapped[float] = mapped_column(Float)
    carbs: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship(back_populates="diary_entries")

    __table_args__ = (Index("ix_diary_entries_user_day", "user_id", "eaten_on"),)


class MenuPlan(Base):
    __tablename__ = "menu_plans"
    __table_args__ = (UniqueConstraint("user_id", "plan_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    plan_date: Mapped[date] = mapped_column(Date)
    target_kcal: Mapped[float] = mapped_column(Float)
    target_protein: Mapped[float] = mapped_column(Float)
    target_fat: Mapped[float] = mapped_column(Float)
    target_carbs: Mapped[float] = mapped_column(Float)
    seed: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship(back_populates="menu_plans")
    items: Mapped[list["MenuPlanItem"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan", order_by="MenuPlanItem.position", lazy="selectin"
    )


class MenuPlanItem(Base):
    __tablename__ = "menu_plan_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("menu_plans.id", ondelete="CASCADE"), index=True)
    dish_id: Mapped[int | None] = mapped_column(ForeignKey("dishes.id", ondelete="SET NULL"))
    position: Mapped[int] = mapped_column(Integer)
    meal_type: Mapped[MealType] = mapped_column(_enum(MealType, "meal_type"))
    meal_target_kcal: Mapped[float] = mapped_column(Float)
    name: Mapped[str] = mapped_column(String(120))
    servings: Mapped[float] = mapped_column(Float)
    grams: Mapped[float] = mapped_column(Float)
    kcal: Mapped[float] = mapped_column(Float)
    protein: Mapped[float] = mapped_column(Float)
    fat: Mapped[float] = mapped_column(Float)
    carbs: Mapped[float] = mapped_column(Float)

    plan: Mapped[MenuPlan] = relationship(back_populates="items")
