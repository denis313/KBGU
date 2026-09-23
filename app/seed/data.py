"""Catalogue of foods and ready-made dishes.

Foods: nutrition per 100 g (edible part, cooked where noted), approximated from
USDA FoodData Central. Tuple layout:
    name: (group, kcal, protein, fat, carbs, fiber, allergens)

Dishes: one serving, ingredients in grams. Nutrition, allowed diets and
allergens are derived from the ingredients at runtime.
"""

FOODS: dict[str, tuple[str, float, float, float, float, float, list[str]]] = {
    # grains & starches
    "Rolled oats": ("plant", 379, 13.2, 6.5, 67.7, 10.1, ["gluten"]),
    "Whole wheat bread": ("plant", 247, 13.0, 3.4, 41.0, 7.0, ["gluten"]),
    "Whole wheat tortilla": ("plant", 306, 9.7, 7.9, 49.5, 6.0, ["gluten"]),
    "Whole wheat pasta, cooked": ("plant", 149, 6.0, 1.7, 30.1, 3.9, ["gluten"]),
    "Brown rice, cooked": ("plant", 123, 2.7, 1.0, 25.6, 1.6, []),
    "White rice, cooked": ("plant", 130, 2.7, 0.3, 28.2, 0.4, []),
    "Quinoa, cooked": ("plant", 120, 4.4, 1.9, 21.3, 2.8, []),
    "Buckwheat, cooked": ("plant", 92, 3.4, 0.6, 19.9, 2.7, []),
    "Potato, boiled": ("plant", 87, 1.9, 0.1, 20.1, 1.8, []),
    "Sweet potato, baked": ("plant", 90, 2.0, 0.2, 20.7, 3.3, []),
    "Rice cakes": ("plant", 387, 8.2, 2.8, 81.5, 4.2, []),
    "Granola": ("plant", 471, 10.0, 20.0, 64.0, 7.0, ["gluten", "nuts"]),
    # legumes & soy
    "Chickpeas, cooked": ("plant", 164, 8.9, 2.6, 27.4, 7.6, []),
    "Lentils, cooked": ("plant", 116, 9.0, 0.4, 20.1, 7.9, []),
    "Black beans, cooked": ("plant", 132, 8.9, 0.5, 23.7, 8.7, []),
    "Tofu, firm": ("plant", 144, 17.3, 8.7, 2.8, 2.3, ["soy"]),
    "Edamame": ("plant", 121, 11.9, 5.2, 8.9, 5.2, ["soy"]),
    "Soy milk, unsweetened": ("plant", 33, 2.9, 1.6, 1.7, 0.5, ["soy"]),
    "Soy sauce": ("plant", 53, 8.1, 0.6, 4.9, 0.8, ["soy", "gluten"]),
    "Hummus": ("plant", 166, 7.9, 9.6, 14.3, 6.0, ["sesame"]),
    # fruit
    "Banana": ("plant", 89, 1.1, 0.3, 22.8, 2.6, []),
    "Apple": ("plant", 52, 0.3, 0.2, 13.8, 2.4, []),
    "Orange": ("plant", 47, 0.9, 0.1, 11.8, 2.4, []),
    "Blueberries": ("plant", 57, 0.7, 0.3, 14.5, 2.4, []),
    "Strawberries": ("plant", 32, 0.7, 0.3, 7.7, 2.0, []),
    "Avocado": ("plant", 160, 2.0, 14.7, 8.5, 6.7, []),
    # vegetables
    "Broccoli": ("plant", 34, 2.8, 0.4, 6.6, 2.6, []),
    "Spinach": ("plant", 23, 2.9, 0.4, 3.6, 2.2, []),
    "Tomato": ("plant", 18, 0.9, 0.2, 3.9, 1.2, []),
    "Cucumber": ("plant", 15, 0.7, 0.1, 3.6, 0.5, []),
    "Bell pepper": ("plant", 31, 1.0, 0.3, 6.0, 2.1, []),
    "Carrot": ("plant", 41, 0.9, 0.2, 9.6, 2.8, []),
    "Onion": ("plant", 40, 1.1, 0.1, 9.3, 1.7, []),
    "Mushrooms": ("plant", 22, 3.1, 0.3, 3.3, 1.0, []),
    "Zucchini": ("plant", 17, 1.2, 0.3, 3.1, 1.0, []),
    "Mixed salad greens": ("plant", 15, 1.4, 0.2, 2.9, 1.3, []),
    "Tomato passata": ("plant", 29, 1.3, 0.2, 5.3, 1.5, []),
    # nuts, seeds, fats, sweets
    "Peanut butter": ("plant", 588, 25.0, 50.0, 20.0, 6.0, ["peanuts"]),
    "Almonds": ("plant", 579, 21.2, 49.9, 21.6, 12.5, ["nuts"]),
    "Walnuts": ("plant", 654, 15.2, 65.2, 13.7, 6.7, ["nuts"]),
    "Chia seeds": ("plant", 486, 16.5, 30.7, 42.1, 34.4, []),
    "Pumpkin seeds": ("plant", 559, 30.2, 49.0, 10.7, 6.0, []),
    "Olive oil": ("plant", 884, 0.0, 100.0, 0.0, 0.0, []),
    "Dark chocolate 70%": ("plant", 598, 7.8, 42.6, 45.9, 10.9, []),
    "Honey": ("plant", 304, 0.3, 0.0, 82.4, 0.2, []),
    # dairy & eggs
    "Egg": ("egg", 143, 12.6, 9.5, 0.7, 0.0, ["egg"]),
    "Whole milk 3.2%": ("dairy", 61, 3.2, 3.3, 4.8, 0.0, ["dairy"]),
    "Greek yogurt 2%": ("dairy", 73, 9.9, 1.9, 3.9, 0.0, ["dairy"]),
    "Kefir 1%": ("dairy", 41, 3.3, 1.0, 4.7, 0.0, ["dairy"]),
    "Cottage cheese 4%": ("dairy", 98, 11.1, 4.3, 3.4, 0.0, ["dairy"]),
    "Feta cheese": ("dairy", 264, 14.2, 21.3, 3.9, 0.0, ["dairy"]),
    "Cheddar cheese": ("dairy", 403, 24.9, 33.1, 1.3, 0.0, ["dairy"]),
    "Parmesan": ("dairy", 431, 38.0, 29.0, 4.1, 0.0, ["dairy"]),
    # meat & fish (cooked)
    "Chicken breast, cooked": ("meat", 165, 31.0, 3.6, 0.0, 0.0, []),
    "Turkey breast, cooked": ("meat", 135, 30.0, 1.5, 0.0, 0.0, []),
    "Lean beef 90%, cooked": ("meat", 217, 26.0, 11.7, 0.0, 0.0, []),
    "Pork tenderloin, cooked": ("meat", 143, 26.0, 3.5, 0.0, 0.0, []),
    "Salmon, cooked": ("fish", 206, 22.0, 12.4, 0.0, 0.0, ["fish"]),
    "Tuna, canned in water": ("fish", 116, 25.5, 0.8, 0.0, 0.0, ["fish"]),
    "Cod, cooked": ("fish", 105, 22.8, 0.9, 0.0, 0.0, ["fish"]),
    "Shrimp, cooked": ("fish", 99, 24.0, 0.3, 0.2, 0.0, ["shellfish"]),
}

ALLERGENS = ["gluten", "dairy", "egg", "nuts", "peanuts", "soy", "fish", "shellfish", "sesame"]

# name: (meal_type, prep_minutes, description, {food: grams})
DISHES: dict[str, tuple[str, int, str, dict[str, float]]] = {
    # ---------- breakfast ----------
    "Oatmeal with banana & peanut butter": ("breakfast", 10, "Oats simmered in soy milk, topped with banana and peanut butter.", {
        "Rolled oats": 60, "Soy milk, unsweetened": 200, "Banana": 100, "Peanut butter": 15}),
    "Greek yogurt berry parfait": ("breakfast", 5, "Layers of Greek yogurt, blueberries and granola with a drizzle of honey.", {
        "Greek yogurt 2%": 200, "Blueberries": 80, "Granola": 40, "Honey": 10}),
    "Veggie scrambled eggs on toast": ("breakfast", 10, "Three eggs scrambled with spinach and tomato on whole wheat toast.", {
        "Egg": 150, "Spinach": 50, "Tomato": 80, "Whole wheat bread": 60, "Olive oil": 5}),
    "Tofu scramble with toast": ("breakfast", 15, "Crumbled tofu sautéed with peppers, onion and spinach.", {
        "Tofu, firm": 150, "Bell pepper": 60, "Spinach": 40, "Onion": 30, "Olive oil": 7, "Whole wheat bread": 50}),
    "Cottage cheese with strawberries & almonds": ("breakfast", 5, "High-protein cottage cheese bowl with fresh berries.", {
        "Cottage cheese 4%": 200, "Strawberries": 100, "Almonds": 15, "Honey": 10}),
    "Avocado toast with egg": ("breakfast", 10, "Smashed avocado on toast with a poached egg and tomato.", {
        "Whole wheat bread": 70, "Avocado": 60, "Egg": 100, "Tomato": 50}),
    "Chia pudding with berries": ("breakfast", 5, "Overnight chia pudding in soy milk with blueberries, banana and walnuts.", {
        "Chia seeds": 30, "Soy milk, unsweetened": 200, "Blueberries": 60, "Banana": 50, "Walnuts": 10}),
    "Buckwheat porridge with apple": ("breakfast", 15, "Buckwheat cooked in milk with grated apple and honey.", {
        "Buckwheat, cooked": 200, "Whole milk 3.2%": 150, "Apple": 100, "Honey": 10}),
    "Salmon & egg toast": ("breakfast", 10, "Whole wheat toast with salmon, boiled egg and cucumber.", {
        "Whole wheat bread": 60, "Salmon, cooked": 60, "Egg": 50, "Cucumber": 50}),
    "Rice cakes with peanut butter & banana": ("breakfast", 3, "Crunchy rice cakes with peanut butter and banana slices.", {
        "Rice cakes": 30, "Peanut butter": 20, "Banana": 100}),
    "Quinoa fruit bowl": ("breakfast", 10, "Warm quinoa with banana, blueberries, pumpkin and chia seeds.", {
        "Quinoa, cooked": 150, "Banana": 80, "Blueberries": 80, "Pumpkin seeds": 15, "Chia seeds": 10}),
    # ---------- lunch ----------
    "Chicken rice bowl with broccoli": ("lunch", 25, "Grilled chicken breast over brown rice with steamed broccoli.", {
        "Chicken breast, cooked": 150, "Brown rice, cooked": 180, "Broccoli": 120, "Olive oil": 8, "Soy sauce": 10}),
    "Lentil & vegetable stew": ("lunch", 35, "Hearty lentil stew with carrot, onion and tomato, served with bread.", {
        "Lentils, cooked": 250, "Carrot": 60, "Onion": 50, "Tomato passata": 100, "Olive oil": 10, "Whole wheat bread": 40}),
    "Tuna quinoa salad": ("lunch", 15, "Quinoa, tuna, cucumber and tomato on greens with olive oil.", {
        "Tuna, canned in water": 120, "Quinoa, cooked": 150, "Cucumber": 80, "Tomato": 80, "Olive oil": 10, "Mixed salad greens": 50}),
    "Beef with potatoes & salad": ("lunch", 30, "Pan-seared lean beef, boiled potatoes and a fresh cucumber salad.", {
        "Lean beef 90%, cooked": 130, "Potato, boiled": 250, "Mixed salad greens": 60, "Cucumber": 60, "Olive oil": 8}),
    "Chickpea & feta salad": ("lunch", 10, "Mediterranean chickpea salad with feta, cucumber, tomato and pepper.", {
        "Chickpeas, cooked": 180, "Feta cheese": 40, "Cucumber": 80, "Tomato": 100, "Bell pepper": 60, "Olive oil": 10}),
    "Turkey hummus wrap": ("lunch", 10, "Whole wheat wrap with turkey, hummus and crunchy vegetables.", {
        "Whole wheat tortilla": 70, "Turkey breast, cooked": 100, "Hummus": 40, "Mixed salad greens": 30, "Tomato": 50, "Cucumber": 40}),
    "Tofu stir-fry with rice": ("lunch", 20, "Crispy tofu with broccoli and peppers in soy sauce over rice.", {
        "Tofu, firm": 180, "White rice, cooked": 180, "Broccoli": 80, "Bell pepper": 60, "Soy sauce": 15, "Olive oil": 10}),
    "Chicken tomato pasta": ("lunch", 25, "Whole wheat pasta with chicken in tomato sauce and parmesan.", {
        "Whole wheat pasta, cooked": 200, "Chicken breast, cooked": 100, "Tomato passata": 120, "Parmesan": 10, "Olive oil": 5}),
    "Black bean burrito bowl": ("lunch", 15, "Black beans and brown rice with pepper, tomato and avocado.", {
        "Black beans, cooked": 150, "Brown rice, cooked": 150, "Bell pepper": 60, "Tomato": 60, "Avocado": 50, "Mixed salad greens": 30}),
    "Shrimp quinoa bowl": ("lunch", 20, "Shrimp with quinoa, edamame and carrot, soy-dressed.", {
        "Shrimp, cooked": 150, "Quinoa, cooked": 170, "Edamame": 60, "Carrot": 50, "Soy sauce": 10, "Olive oil": 5}),
    "Pork with buckwheat & mushrooms": ("lunch", 30, "Pork tenderloin with buckwheat and sautéed mushrooms and onion.", {
        "Pork tenderloin, cooked": 140, "Buckwheat, cooked": 200, "Mushrooms": 100, "Onion": 40, "Olive oil": 8}),
    # ---------- dinner ----------
    "Baked salmon with sweet potato": ("dinner", 30, "Oven-baked salmon with sweet potato and steamed broccoli.", {
        "Salmon, cooked": 150, "Sweet potato, baked": 200, "Broccoli": 150, "Olive oil": 5}),
    "Chicken & vegetable traybake": ("dinner", 40, "Chicken, potatoes, zucchini and peppers roasted on one tray.", {
        "Chicken breast, cooked": 150, "Potato, boiled": 200, "Zucchini": 100, "Bell pepper": 80, "Olive oil": 10}),
    "Cod with quinoa & spinach": ("dinner", 25, "Pan-fried cod on quinoa with wilted spinach.", {
        "Cod, cooked": 180, "Quinoa, cooked": 150, "Spinach": 80, "Olive oil": 8}),
    "Beef bolognese": ("dinner", 35, "Whole wheat pasta with lean beef, carrot and onion tomato sauce.", {
        "Whole wheat pasta, cooked": 180, "Lean beef 90%, cooked": 100, "Tomato passata": 150, "Onion": 40, "Carrot": 40, "Parmesan": 10}),
    "Chickpea spinach curry": ("dinner", 30, "Chickpeas and spinach simmered in spiced tomato sauce with rice.", {
        "Chickpeas, cooked": 200, "Spinach": 80, "Tomato passata": 150, "Onion": 50, "White rice, cooked": 120, "Olive oil": 8}),
    "Tofu buckwheat bowl": ("dinner", 25, "Buckwheat with seared tofu, mushrooms and zucchini.", {
        "Tofu, firm": 150, "Buckwheat, cooked": 180, "Mushrooms": 100, "Zucchini": 80, "Soy sauce": 10, "Olive oil": 8}),
    "Mushroom & cheese omelette with potatoes": ("dinner", 20, "Three-egg omelette with mushrooms, spinach and cheddar.", {
        "Egg": 150, "Mushrooms": 60, "Spinach": 50, "Cheddar cheese": 20, "Potato, boiled": 150, "Olive oil": 5}),
    "Shrimp stir-fry with rice": ("dinner", 20, "Shrimp, pepper and broccoli stir-fried with soy sauce over rice.", {
        "Shrimp, cooked": 150, "White rice, cooked": 150, "Bell pepper": 80, "Broccoli": 80, "Soy sauce": 15, "Olive oil": 8}),
    "Pork tenderloin with sweet potato": ("dinner", 35, "Roasted pork tenderloin, sweet potato and tomato salad.", {
        "Pork tenderloin, cooked": 150, "Sweet potato, baked": 180, "Mixed salad greens": 60, "Tomato": 80, "Olive oil": 8}),
    "Lentil-stuffed peppers": ("dinner", 45, "Bell peppers stuffed with lentils, rice and tomato, topped with feta.", {
        "Lentils, cooked": 200, "Bell pepper": 200, "Onion": 40, "Tomato passata": 100, "Feta cheese": 30, "Brown rice, cooked": 80}),
    "Chicken avocado salad": ("dinner", 15, "Chicken breast, avocado and vegetables on greens with bread.", {
        "Chicken breast, cooked": 130, "Mixed salad greens": 80, "Avocado": 60, "Tomato": 100, "Cucumber": 80, "Olive oil": 8, "Whole wheat bread": 40}),
    # ---------- snack ----------
    "Apple with almonds": ("snack", 1, "A crunchy apple with a small handful of almonds.", {
        "Apple": 150, "Almonds": 20}),
    "Greek yogurt with honey": ("snack", 1, "Thick Greek yogurt with a spoon of honey.", {
        "Greek yogurt 2%": 170, "Honey": 10}),
    "Hummus with veggie sticks": ("snack", 5, "Carrot and cucumber sticks with hummus.", {
        "Hummus": 60, "Carrot": 100, "Cucumber": 100}),
    "Kefir with banana": ("snack", 1, "A glass of kefir and a banana.", {
        "Kefir 1%": 250, "Banana": 100}),
    "Cottage cheese & cucumber": ("snack", 3, "Savory cottage cheese with sliced cucumber.", {
        "Cottage cheese 4%": 150, "Cucumber": 100}),
    "Rice cakes with peanut butter": ("snack", 2, "Two rice cakes with peanut butter.", {
        "Rice cakes": 20, "Peanut butter": 15}),
    "Boiled eggs with tomato": ("snack", 10, "Two boiled eggs with a sliced tomato.", {
        "Egg": 100, "Tomato": 100}),
    "Dark chocolate & strawberries": ("snack", 1, "A few squares of dark chocolate with fresh strawberries.", {
        "Dark chocolate 70%": 20, "Strawberries": 150}),
    "Steamed edamame": ("snack", 5, "Lightly salted steamed edamame.", {
        "Edamame": 150}),
    "Orange & pumpkin seeds": ("snack", 1, "An orange with a handful of pumpkin seeds.", {
        "Orange": 150, "Pumpkin seeds": 20}),
    "Tuna rice cakes": ("snack", 3, "Rice cakes topped with tuna and cucumber.", {
        "Tuna, canned in water": 60, "Rice cakes": 20, "Cucumber": 40}),
}
