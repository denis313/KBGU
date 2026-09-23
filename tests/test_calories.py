from datetime import date

import pytest

from app.models import ActivityLevel, Goal, Sex
from app.services.calories import (
    BodyParams,
    age_on,
    calculate,
    harris_benedict_revised,
    katch_mcardle,
    mifflin_st_jeor,
    protein_reference_weight,
)


def test_mifflin_st_jeor_reference_values():
    # 10*80 + 6.25*180 - 5*30 + 5 = 1780
    assert mifflin_st_jeor(Sex.male, 80, 180, 30) == pytest.approx(1780)
    # 10*60 + 6.25*165 - 5*25 - 161 = 1345.25
    assert mifflin_st_jeor(Sex.female, 60, 165, 25) == pytest.approx(1345.25)


def test_katch_mcardle_uses_lean_mass():
    assert katch_mcardle(80, 20) == pytest.approx(370 + 21.6 * 64)


def test_harris_benedict_is_reported_for_comparison():
    plan = calculate(BodyParams(Sex.male, 30, 180, 80, ActivityLevel.moderate))
    assert plan.bmr_formula == "mifflin_st_jeor"
    assert plan.bmr_estimates["harris_benedict"] == round(harris_benedict_revised(Sex.male, 80, 180, 30))


def test_body_fat_switches_to_katch_mcardle():
    plan = calculate(BodyParams(Sex.male, 30, 180, 80, ActivityLevel.moderate, body_fat_pct=12))
    assert plan.bmr_formula == "katch_mcardle"
    assert plan.bmr == round(katch_mcardle(80, 12))


def test_maintenance_target_equals_tdee_and_macros_add_up():
    plan = calculate(BodyParams(Sex.male, 30, 180, 80, ActivityLevel.moderate))
    assert plan.tdee == round(1780 * 1.55)
    assert plan.target_kcal == plan.tdee
    kcal_from_macros = plan.protein_g * 4 + plan.fat_g * 9 + plan.carbs_g * 4
    assert kcal_from_macros == pytest.approx(plan.target_kcal, abs=15)
    assert plan.protein_g == round(1.6 * 80)


def test_moderate_loss_uses_7700_kcal_per_kg():
    plan = calculate(BodyParams(Sex.male, 30, 180, 80, ActivityLevel.moderate, Goal.lose, 0.5))
    assert plan.daily_adjustment == -550
    assert not plan.warnings


def test_aggressive_loss_is_capped_and_floored():
    plan = calculate(BodyParams(Sex.female, 60, 155, 50, ActivityLevel.sedentary, Goal.lose, 1.0))
    assert plan.target_kcal == 1200
    assert plan.warnings


def test_surplus_is_capped():
    plan = calculate(BodyParams(Sex.male, 25, 175, 60, ActivityLevel.sedentary, Goal.gain, 1.0))
    assert plan.daily_adjustment == round(plan.tdee * 0.15)
    assert plan.warnings


def test_meal_split_sums_to_target():
    for meals in (3, 4):
        plan = calculate(BodyParams(Sex.female, 35, 170, 70, ActivityLevel.light), meals)
        assert len(plan.meal_split) == meals
        assert sum(plan.meal_split.values()) == pytest.approx(plan.target_kcal, abs=2)


def test_protein_uses_adjusted_weight_for_obesity():
    assert protein_reference_weight(80, 180) == 80
    assert protein_reference_weight(140, 170) < 100


def test_age_on_birthday_boundary():
    assert age_on(date(2000, 6, 15), date(2026, 6, 14)) == 25
    assert age_on(date(2000, 6, 15), date(2026, 6, 15)) == 26
