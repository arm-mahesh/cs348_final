import sqlite3
import os
from flask import Flask, request, render_template, url_for, redirect
from peewee import *

app = Flask(__name__)
db = SqliteDatabase('recipes.db')

class BaseModel(Model):
    class Meta:
        database = db

class Recipe(BaseModel):
    name = CharField()
    prep_time = IntegerField()
    cook_time = IntegerField()

class Ingredient(BaseModel):
    name = CharField(unique=True)

class RecipeIngredient(BaseModel):
    recipe = ForeignKeyField(Recipe)
    ingredient = ForeignKeyField(Ingredient)
    amount = CharField()

@app.before_request
def before_request():
    db.connect()

@app.after_request
def after_request(response):
    db.close()
    return response

@app.route('/')
def root():
    return render_template('frontend.html')

@app.route('/create_recipe', methods=['GET', 'POST'])
def create_recipe():
    if request.method == 'POST':
        name = request.form['name']
        prep_time = request.form['prep_time']
        cook_time = request.form['cook_time']
        recipe = Recipe.create(name=name, prep_time=prep_time, cook_time=cook_time)

        ingredients = request.form.getlist('ingredient_name[]')
        quantities = request.form.getlist('ingredient_quantity[]')
        for ingredient_name, quantity in zip(ingredients, quantities):
            ingredient, created = Ingredient.get_or_create(name=ingredient_name)
            RecipeIngredient.create(recipe=recipe, ingredient=ingredient, amount=quantity)

        return redirect(url_for('all_recipes'))

    return render_template('create_recipe.html')

def get_all_ingredients():
    db = sqlite3.connect('recipes.db')
    cursor = db.cursor()
    cursor.execute('SELECT name FROM ingredient')
    ingredients = cursor.fetchall()
    db.close()
    return ingredients

@app.route('/all_recipes')
def all_recipes():
    recipes = Recipe.select()
    recipe_data = [(recipe.id, recipe.name) for recipe in recipes]
    ingredients = get_all_ingredients()
    print(ingredients)
    ingredient_names = [ingredient[0] for ingredient in ingredients]  # Extracting only the names
    return render_template('all_recipes.html', recipes=recipe_data, ingredients=ingredient_names)

@app.route('/search', methods=['GET'])
def search_recipes():
    ingredient = request.args.get('ingredient', '')
    db = sqlite3.connect('recipes.db')
    cursor = db.cursor()
    if ingredient:
        cursor.execute('''
            SELECT COUNT(*) 
            FROM recipeingredient 
            WHERE ingredient_id IN (
                SELECT id 
                FROM ingredient 
                WHERE name = ?
            )
        ''', (ingredient,))
        count = cursor.fetchone()[0]
        cursor.execute('''
            SELECT recipe.id, recipe.name, recipeingredient.amount
            FROM recipeingredient 
            JOIN recipe ON recipeingredient.recipe_id = recipe.id
            WHERE ingredient_id IN (
                SELECT id 
                FROM ingredient 
                WHERE name = ?
            )
        ''', (ingredient,))
        # Subquery to find the mode (most common value) of the amount column
        cursor.execute('''
            SELECT amount
            FROM recipeingredient 
            JOIN ingredient ON recipeingredient.ingredient_id = ingredient.id
            WHERE ingredient.name = ?
            GROUP BY amount
            ORDER BY COUNT(*) DESC
            LIMIT 1
        ''', (ingredient,))
        most_common_amount = cursor.fetchone()[0]
        cursor.execute('''
                    SELECT recipe.id, recipe.name
                    FROM recipeingredient
                    JOIN recipe ON recipeingredient.recipe_id = recipe.id
                    WHERE ingredient_id IN (
                        SELECT id
                        FROM ingredient
                        WHERE name = ?
                    )
                ''', (ingredient,))
        recipes = cursor.fetchall()
        percent = (count / Recipe.select().count()) * 100
    else:
        cursor.execute('''
            SELECT recipe.id, recipe.name
            FROM recipe
        ''')
        count = None
        most_common_amount = None
        percent = None
        recipes = cursor.fetchall()
    print(recipes)
    db.close()
    return render_template('all_recipes.html', recipes=recipes, count=count, most_common_amount=most_common_amount, percent=percent)
@app.route('/recipe/<int:recipe_id>')
def recipe(recipe_id):
    db = sqlite3.connect('recipes.db')
    cursor = db.cursor()

    cursor.execute('SELECT name, prep_time, cook_time FROM recipe WHERE id = ?', (recipe_id,))

    recipe_data = cursor.fetchone()
    recipe_name = recipe_data[0]
    prep_time = recipe_data[1]
    cook_time = recipe_data[2]

    cursor.execute('''SELECT ingredient.name, recipeingredient.amount
                      FROM ingredient
                      JOIN recipeingredient ON ingredient.id = recipeingredient.ingredient_id
                      WHERE recipeingredient.recipe_id = ?''', (recipe_id,))
    ingredients = cursor.fetchall()

    db.close()
    return render_template('recipe.html', recipe_name=recipe_name, ingredients=ingredients, recipe_prep_time=prep_time,
                           recipe_cook_time=cook_time)


@app.route('/update_recipe/<int:recipe_id>', methods=['GET', 'POST'])
def update_recipe(recipe_id):
    recipe = Recipe.get_or_none(Recipe.id == recipe_id)
    if request.method == 'POST' and recipe:
        recipe.name = request.form['name']
        recipe.prep_time = request.form['prep_time']
        recipe.cook_time = request.form['cook_time']
        recipe.save()
        return redirect(url_for('all_recipes'))
    elif recipe:
        return render_template('update_recipe.html', recipe=recipe)
    else:
        return "Recipe not found", 404

@app.route('/delete_recipe/<int:recipe_id>')
def delete_recipe(recipe_id):
    recipe = Recipe.get_or_none(Recipe.id == recipe_id)
    if recipe:
        recipe.delete_instance(recursive=True)
        return redirect(url_for('all_recipes'))
    else:
        return "Recipe not found", 404

if __name__ == '__main__':
    import os
    from gunicorn.app.base import BaseApplication

    class FlaskApp(BaseApplication):
        def __init__(self, app, options=None):
            self.options = options or {}
            self.application = app
            super().__init__()

        def load_config(self):
            for key, value in self.options.items():
                self.cfg.set(key, value)

        def load(self):
            print("")
            return self.application

    options = {
        'bind': '0.0.0.0:' + str(os.environ.get('PORT', 5000)),
        'workers': 4,
    }

    FlaskApp(app, options).run()

