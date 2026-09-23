# Calorie Tracker (BnB v2)

A calorie tracker with registration, a food diary, personal calorie and macro
targets, and daily menus generated from a curated database of ready-made dishes.
It runs on **FastAPI**, **PostgreSQL** and **SQLAlchemy 2 ORM**, with **Alembic**
migrations. The mobile-first web UI with a bottom navigation bar is served from
the same app.

## Quick start

```bash
# 1. PostgreSQL (or use: docker compose up -d db)
createuser -s calorie && createdb -O calorie calorie_tracker   # password: calorie

# 2. App
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env            # set SECRET_KEY
alembic upgrade head            # create schema
python -m app.seed              # load 61 foods + 44 ready-made dishes (idempotent)
uvicorn app.main:app --reload   # UI: http://localhost:8000, API docs: /docs
```

Or run everything with `docker compose up --build`.

Tests run against a real PostgreSQL database named `calorie_tracker_test`
(override with `TEST_DATABASE_URL`). The schema is built by the Alembic
migrations themselves:

```bash
createdb -O calorie calorie_tracker_test
pytest
```

## Calorie calculation: which method and why

| Step | Method | Rationale |
|---|---|---|
| BMR (default) | **Mifflin-St Jeor** | Most accurate weight-based equation in the systematic review by Frankenfield et al. (JADA 2005): it came within ±10% of measured values for the most people, lean and obese, and beat Harris-Benedict, Owen and WHO/FAO. The Academy of Nutrition and Dietetics recommends it. |
| BMR (if body-fat % known) | **Katch-McArdle** | Based on lean body mass, so it is better for lean or muscular people, whom weight-only equations misjudge. |
| BMR (reference only) | Revised Harris-Benedict | Shown for comparison. It tends to overestimate by about 5%. |
| TDEE | BMR × activity factor (1.2 / 1.375 / 1.55 / 1.725 / 1.9) | Standard physical-activity-level multipliers. |
| Goal | ±(kg per week × 7700) / 7 kcal | About 7700 kcal per kg of body mass. The deficit is capped at 25% of TDEE and the surplus at 15%. Intake never drops below 1200 kcal (women) or 1500 kcal (men). Each clamp is shown to the user as a warning. |
| Protein | 2.0 / 1.6 / 1.8 g per kg (lose / maintain / gain) | Protects lean mass during a deficit. At BMI ≥ 30 the adjusted body weight is used (ideal weight + 40% of the excess). |
| Fat / carbs | Fat 30% of kcal (at least 0.6 g/kg). Carbs take the remainder (at least 20%). | |

The formulas live in `app/services/calories.py`. Anyone can try them without an
account at `POST /api/calculator`.

## Menu recommendations: a database plus a generator

The app does both, because each approach alone has a weakness. Hand-written
menus don't fit individual targets. Menus generated from single foods produce
meals nobody would actually cook.

* **Database of ready-made dishes** (`app/seed/data.py`): 44 realistic recipes
  (breakfast, lunch, dinner and snacks) built from 61 foods whose values come
  from USDA FoodData Central. Each dish's nutrition, diet compatibility
  (omnivore, pescatarian, vegetarian, vegan) and allergens are **derived from
  its ingredients**. Correcting a food therefore fixes every dish that uses it.
* **Generator** (`app/services/menu.py`) builds a day from those dishes:
  1. It filters dishes by the user's diet and excluded allergens.
  2. It enumerates small catalogues completely and randomly samples about 1500
     candidate days for large ones.
  3. It scales each dish (0.5–2 servings, in steps of 0.25) to its meal's
     calorie share (for example breakfast 25%, lunch 35%, dinner 30%, snack
     10%), then refines the servings with a greedy local search.
  4. It scores each day on calorie error, protein shortfall (penalised
     hardest), fat, carbs and per-meal balance.
  5. It picks at random among the near-best days. The pick is seeded, so a
     given seed is reproducible and "Regenerate" still gives variety.
     Dishes eaten or planned in the last 3 days are down-weighted.
* **Swap** replaces one meal with the best-fitting alternative. **Add to
  diary** logs one menu item or the whole day.

## Data model (PostgreSQL, SQLAlchemy ORM)

`users` 1–1 `profiles` · `users` 1–N `weight_logs`, `diary_entries`, `menu_plans` 1–N `menu_plan_items`
`foods` (shared catalogue, plus custom foods with `owner_id`) N–M `dishes` through `dish_ingredients`

Diary entries and menu items store a **nutrition snapshot**, so later catalogue
edits don't rewrite a user's history. The schema uses PostgreSQL-native enums
and `ARRAY` columns (allergens). Migrations are in `alembic/versions`.

## API overview

| | |
|---|---|
| `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/me` | Email and password accounts. Passwords are hashed with bcrypt. Sessions use JWT bearer tokens. |
| `GET/PUT /api/profile`, `GET /api/profile/targets` | Body data and preferences, and the computed energy plan |
| `POST /api/calculator` | Public calculator (no account needed) |
| `GET/POST /api/weights` | Weigh-ins. The latest one updates the profile and the targets. |
| `GET/POST/DELETE /api/foods`, `GET /api/dishes[/{id}]` | Catalogue search and custom foods |
| `GET /api/diary?date=`, `POST/PATCH/DELETE /api/diary[/{id}]`, `GET /api/diary/history` | Food diary |
| `POST /api/menu/generate`, `GET /api/menu?date=`, `POST /api/menu/{id}/items/{item}/swap`, `POST /api/menu/{id}/log` | Menu generation |

Interactive documentation is available at `/docs`.

## Web UI

`web/Calorie Tracker BnB v2.html` is a single-file, dependency-free page served
at `/`. It has sign-in/registration, onboarding, **Today** (a calorie ring,
macro bars and meals), **Menu** (generate, swap, log), an **Add** bottom sheet
(search foods or ready-made dishes), **Progress** (7-day chart and weight log)
and **Profile** (targets and how they're calculated). It follows the system
light/dark theme.
