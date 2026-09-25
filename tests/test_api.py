from datetime import date, timedelta

from tests.conftest import PROFILE


def test_register_login_me(client):
    r = client.post("/api/auth/register", json={"email": "Bob@Example.com", "password": "password1", "name": "Bob"})
    assert r.status_code == 201
    assert r.json()["user"] == {"id": 1, "email": "bob@example.com", "name": "Bob", "has_profile": False}

    assert client.post("/api/auth/register", json={"email": "bob@example.com", "password": "password1", "name": "B"}).status_code == 409
    assert client.post("/api/auth/login", json={"email": "bob@example.com", "password": "wrong-pass"}).status_code == 401

    token = client.post("/api/auth/login", json={"email": "BOB@example.com", "password": "password1"}).json()["access_token"]
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.json()["email"] == "bob@example.com"


def test_protected_routes_need_a_token(client):
    assert client.get("/api/diary").status_code == 401
    assert client.get("/api/diary", headers={"Authorization": "Bearer nope"}).status_code == 401


def test_register_validates_input(client):
    r = client.post("/api/auth/register", json={"email": "not-an-email", "password": "short", "name": ""})
    assert r.status_code == 422


def test_profile_required_before_targets(client):
    token = client.post("/api/auth/register", json={"email": "c@example.com", "password": "password1", "name": "C"}).json()["access_token"]
    assert client.get("/api/profile/targets", headers={"Authorization": f"Bearer {token}"}).status_code == 409


def test_profile_and_targets(client, auth):
    profile = client.get("/api/profile", headers=auth).json()
    assert profile["weight_kg"] == 68 and profile["age"] > 0
    targets = client.get("/api/profile/targets", headers=auth).json()
    assert targets["bmr_formula"] == "mifflin_st_jeor"
    assert targets["target_kcal"] < targets["tdee"]
    assert set(targets["meal_split"]) == {"breakfast", "lunch", "dinner", "snack"}


def test_invalid_allergen_rejected(client, auth):
    r = client.put("/api/profile", json={**PROFILE, "excluded_allergens": ["kryptonite"]}, headers=auth)
    assert r.status_code == 422


def test_public_calculator(client):
    r = client.post("/api/calculator", json={
        "sex": "male", "age": 30, "height_cm": 180, "weight_kg": 80, "activity_level": "moderate"})
    assert r.status_code == 200
    assert r.json()["bmr"] == 1780


def test_food_search_and_custom_food(client, auth):
    assert any(f["name"] == "Банан" for f in client.get("/api/foods?q=бана", headers=auth).json())  # case-insensitive Cyrillic
    r = client.post("/api/foods", headers=auth, json={
        "name": "Бабушкин пирог", "kcal": 320, "protein": 5, "fat": 15, "carbs": 40})
    assert r.status_code == 201 and r.json()["is_custom"]
    assert client.get("/api/foods?q=бабушкин", headers=auth).json()[0]["id"] == r.json()["id"]
    assert client.delete(f"/api/foods/{r.json()['id']}", headers=auth).status_code == 204


def test_dishes_filter_by_diet(client, auth):
    vegan = client.get("/api/dishes?diet=vegan&meal_type=lunch", headers=auth).json()
    assert vegan and all("vegan" in d["diets"] and d["meal_type"] == "lunch" for d in vegan)
    no_gluten = client.get("/api/dishes?exclude_allergens=gluten", headers=auth).json()
    assert all("gluten" not in d["allergens"] for d in no_gluten)


def test_diary_flow(client, auth):
    banana = client.get("/api/foods?q=банан", headers=auth).json()[0]
    dish = client.get("/api/dishes?meal_type=lunch", headers=auth).json()[0]

    r = client.post("/api/diary", headers=auth, json={"meal_type": "snack", "food_id": banana["id"], "grams": 120})
    assert r.status_code == 201
    assert r.json()["kcal"] == round(banana["kcal"] * 1.2, 1)
    entry_id = r.json()["id"]

    r = client.post("/api/diary", headers=auth, json={"meal_type": "lunch", "dish_id": dish["id"], "servings": 1.5})
    assert abs(r.json()["kcal"] - dish["kcal"] * 1.5) < 1  # dish kcal in the API is rounded

    assert client.post("/api/diary", headers=auth, json={"meal_type": "lunch", "food_id": 1}).status_code == 422

    r = client.patch(f"/api/diary/{entry_id}", headers=auth, json={"grams": 240})
    assert r.json()["kcal"] == round(banana["kcal"] * 2.4, 1)

    day = client.get("/api/diary", headers=auth).json()
    assert [e["meal_type"] for e in day["entries"]] == ["lunch", "snack"]
    assert day["remaining_kcal"] == round(day["targets"]["kcal"] - day["totals"]["kcal"])

    history = client.get("/api/diary/history?days=7", headers=auth).json()
    assert len(history) == 7 and history[-1]["kcal"] == day["totals"]["kcal"]

    assert client.delete(f"/api/diary/{entry_id}", headers=auth).status_code == 204
    assert len(client.get("/api/diary", headers=auth).json()["entries"]) == 1


def test_users_cannot_touch_each_others_entries(client, auth):
    food = client.get("/api/foods?q=яблоко", headers=auth).json()[0]
    entry = client.post("/api/diary", headers=auth, json={"meal_type": "snack", "food_id": food["id"], "grams": 100}).json()
    other = client.post("/api/auth/register", json={"email": "eve@example.com", "password": "password1", "name": "Eve"}).json()
    headers = {"Authorization": f"Bearer {other['access_token']}"}
    assert client.delete(f"/api/diary/{entry['id']}", headers=headers).status_code == 404


def test_menu_generate_swap_and_log(client, auth):
    r = client.post("/api/menu/generate", headers=auth, json={"seed": 123})
    assert r.status_code == 201, r.text
    plan = r.json()
    assert [i["meal_type"] for i in plan["items"]] == ["breakfast", "lunch", "dinner", "snack"]
    assert abs(plan["totals"]["kcal"] - plan["targets"]["kcal"]) / plan["targets"]["kcal"] < 0.1

    # Regenerating the same day replaces the plan.
    again = client.post("/api/menu/generate", headers=auth, json={"seed": 123}).json()
    assert [i["dish_id"] for i in again["items"]] == [i["dish_id"] for i in plan["items"]]
    assert client.get("/api/menu", headers=auth).json()["id"] == again["id"]

    lunch = again["items"][1]
    swapped = client.post(f"/api/menu/{again['id']}/items/{lunch['id']}/swap", headers=auth).json()
    assert swapped["items"][1]["dish_id"] != lunch["dish_id"]

    logged = client.post(f"/api/menu/{again['id']}/log", headers=auth, json={}).json()
    assert len(logged) == 4
    day = client.get("/api/diary", headers=auth).json()
    assert abs(day["totals"]["kcal"] - swapped["totals"]["kcal"]) <= 4  # per-item rounding


def test_menu_respects_diet_and_allergens(client, auth):
    client.put("/api/profile", headers=auth, json={**PROFILE, "diet_type": "vegan", "excluded_allergens": ["soy", "gluten"]})
    plan = client.post("/api/menu/generate", headers=auth, json={}).json()
    dishes = {d["id"]: d for d in client.get("/api/dishes", headers=auth).json()}
    for item in plan["items"]:
        dish = dishes[item["dish_id"]]
        assert "vegan" in dish["diets"]
        assert not {"soy", "gluten"} & set(dish["allergens"])


def test_weight_log_updates_profile(client, auth):
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    client.post("/api/weights", headers=auth, json={"logged_on": yesterday, "weight_kg": 67.5})
    client.post("/api/weights", headers=auth, json={"weight_kg": 67.0})
    weights = client.get("/api/weights", headers=auth).json()
    assert [w["weight_kg"] for w in weights] == [67.5, 67.0]
    assert client.get("/api/profile", headers=auth).json()["weight_kg"] == 67.0


def test_web_page_is_served(client):
    r = client.get("/")
    assert r.status_code == 200 and "Трекер калорий" in r.text and 'lang="ru"' in r.text
