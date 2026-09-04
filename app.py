from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from dotenv import load_dotenv
import os
import json
os.environ['SQLALCHEMY_SILENCE_UBER_WARNING'] = '1'

app = Flask(__name__)

# Charger les variables d'environnement
load_dotenv()

# Config BD
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///pizzas.db')

# Récupérer la HOME_IP depuis les variables d'env
#HOME_IP = os.getenv('HOME_IP', '')

# Forcer psycopg (v3) au lieu de psycopg2
if DATABASE_URL and DATABASE_URL.startswith('postgres://'):
    # Remplace postgres:// par postgresql+psycopg://
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql+psycopg://', 1)
elif DATABASE_URL and DATABASE_URL.startswith('postgresql://'):
    # Remplace postgresql:// par postgresql+psycopg://
    DATABASE_URL = DATABASE_URL.replace('postgresql://', 'postgresql+psycopg://', 1)

print(f"DEBUG: Using DATABASE_URL = {DATABASE_URL[:50]}...")  # Debug
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL


app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- MODÈLES ---

class Commande(db.Model):
    __tablename__ = 'commandes'
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100))
    base = db.Column(db.String(100))
    ingredients = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.now)
    statut = db.Column(db.String(50), default='en attente')

class Ingredient(db.Model):
    __tablename__ = 'ingredients'
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), unique=True)
    image_url = db.Column(db.String(500))
    color = db.Column(db.String(10), default='#FF9800')
    disponible = db.Column(db.Integer, default=1)

# Ajouter ce modèle après la classe Ingredient

class IngredientPrepare(db.Model):
    __tablename__ = 'ingredients_prepares'
    id = db.Column(db.Integer, primary_key=True)
    commande_id = db.Column(db.Integer, db.ForeignKey('commandes.id'), nullable=False)
    ingredient_nom = db.Column(db.String(100))
    prepare = db.Column(db.Integer, default=0)


# Créer les tables
with app.app_context():
    db.create_all()
    
    # Ajouter les ingrédients par défaut
    if Ingredient.query.count() == 0:
        ingredients_default = [
            ('Jambon', 'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcRYojxeVse7As-p9kcLwBCA6aQ-yTpJOMH1wEfeTUiq4w&s=10', '#ff8c82'),
            ('Mozzarella', 'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcTXoNi-O7pYjugIv0VMXc2LFch85JX6RX18ECCiZfldYQ&s=10', '#ebebeb'),
            ('Champignons', 'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcToZT2Hz8y8ztjP09PyPqtPRxzNL0016xpdgvouff1eXA&s=10', '#795548'),
            ('Olives', 'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQ4brQVvDB3D3mDYOG58VrV-ORTh-72bteIb2qQ5FuafQ&s=10', '#424242'),
            ('Oeuf', 'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQUl7FXtNoj2CinComqALbYfAuV1rpXYrD07D50r35hYQ&s=10', '#fffb00'),
            ('Viande hachée', 'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcTGrjD_ay99e6Yhg91WhruZuu6Qo-Gw6Jr9VHW18s5cJQ&s=10', '#ff4013'),
            ('Boursin', 'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcTmfdt6o1vE4HnA60Ma4NOdDuZRrID15CZyIkQwrnmR4w&s=10', '#ff9800'),
            ('Burrata', 'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcT9ztfr3plXSU49Hz2l74cKBkk4TUYrfugTkKQJOvPoOw&s=10', '#ebebeb'),
            ('Mortadelle', 'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQl1XJFXlXSIswaBkQq4DXBkdE1d32Ft-T_kd_-hSvkxw&s=10', '#ff9800'),
            ('Jambon rouge', 'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQY4vOoa7G7IjW5ma7jki9MsUViYnZ0KsYVfFvR6hgfYA&s=10', '#ff2600'),
            ('Oignons rouge', 'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcRVJNfy9cqQidjf2RSMQoP-wCdxq93Tz6DaqD2aPRox9g&s=10', '#ff2600'),
            ('Saumon', 'https://media.istockphoto.com/id/179247374/fr/photo/frais-et-saumon-fumé.jpg?s=612x612&w=0&k=20&c=4fKhBE-vieNl1fuArvOY9t3TUcPlI4y0CHB3Zvmd-Ww=', '#ff9800'),
            ('Oignons jaune', 'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQkWUAQKIlN5T9jaOv6gWRFaQ5s_rJp85YMo52n2IQoTg&s=10', '#c4bc00')
        ]
        for nom, url, color in ingredients_default:
            db.session.add(Ingredient(nom=nom, image_url=url, color=color, disponible=1))
        db.session.commit()

# Middleware : vérifier IP
@app.before_request
def check_ip():
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if ip:
        ip = ip.split(',')[0].strip()
    
    # Récupérer HOME_IP et le parser en liste d'IPs
    home_ips_str = os.getenv('HOME_IP', '')
    home_ips = [h.strip() for h in home_ips_str.split(';') if h.strip()]
    
    print(f"DEBUG: IP={ip}, HOME_IPS={home_ips}")
    
    # Vérifier si l'IP fait partie de l'une des listes autorisées
    ip_autorisee = (
        any(ip.startswith(allowed) for allowed in ['127.0.0.1', '192.168.1.'])
        or any(ip.startswith(home_ip) for home_ip in home_ips)
    )
    
    if not ip_autorisee:
        print(f"DEBUG: Blocage pour {ip}")
        return jsonify({'erreur': 'Accès non autorisé'}), 403
# --- ROUTES PRINCIPALES ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/preparation')
def preparation():
    return render_template('preparation.html')

@app.route('/cuisine')
def cuisine():
    return render_template('cuisine.html')

# --- API COMMANDES ---

@app.route('/api/commandes', methods=['GET'])
def get_commandes():
    commandes = Commande.query.filter_by(statut='en attente').order_by(Commande.created_at.desc()).all()
    return jsonify([{
        'id': c.id, 'nom': c.nom, 'base': c.base, 
        'ingredients': c.ingredients, 'heure': c.created_at.isoformat()
    } for c in commandes])

@app.route('/api/commander', methods=['POST'])
def commander():
    data = request.json
    nom = data.get('nom', '').strip()
    base = data.get('base', '')
    ingredients_data = data.get('ingredients', [])

    if not nom:
        return jsonify({'erreur': 'Données incomplètes'}), 400

    # Gérer les deux formats (liste simple ou dict moitié-moitié)
    if isinstance(ingredients_data, dict):
        # Format moitié-moitié
        ingredients = json.dumps(ingredients_data)
    else:
        # Format simple
        ingredients = ','.join(ingredients_data)

    cmd = Commande(nom=nom, base=base, ingredients=ingredients)
    db.session.add(cmd)
    db.session.commit()

    return jsonify({'success': True, 'message': 'Pizza commandée !'})

@app.route('/api/fait/<int:id>', methods=['POST'])
def marquer_fait(id):
    cmd = Commande.query.get(id)
    if cmd:
        cmd.statut = 'fait'
        db.session.commit()
    return jsonify({'success': True})

# --- API CONFIG ---

@app.route('/api/config', methods=['GET'])
def get_config():
    ingredients = Ingredient.query.filter_by(disponible=1).all()
    return jsonify({
        'bases': ['Base tomate', 'Base crème fraîche'],
        'ingredients': [{
            'id': ing.id, 'nom': ing.nom, 
            'image': ing.image_url, 'color': ing.color
        } for ing in ingredients]
    })

# --- API INGRÉDIENTS ---

@app.route('/api/ingredients', methods=['GET'])
def get_ingredients():
    ingredients = Ingredient.query.all()
    return jsonify([{
        'id': ing.id, 'nom': ing.nom, 'image': ing.image_url,
        'color': ing.color, 'disponible': ing.disponible
    } for ing in ingredients])

@app.route('/api/ingredient/<int:id>/toggle', methods=['POST'])
def toggle_ingredient(id):
    ing = Ingredient.query.get(id)
    if not ing:
        return jsonify({'erreur': 'Ingrédient non trouvé'}), 404
    
    ing.disponible = 1 - ing.disponible
    db.session.commit()
    return jsonify({'success': True, 'disponible': bool(ing.disponible)})

@app.route('/api/ingredient', methods=['POST'])
def add_ingredient():
    try:
        data = request.json
        nom = data.get('nom', '').strip()
        image = data.get('image', 'https://via.placeholder.com/200').strip()
        color = data.get('color', '#FF9800')
        
        if not nom:
            return jsonify({'erreur': 'Nom vide'}), 400
        
        ing = Ingredient(nom=nom, image_url=image, color=color, disponible=1)
        db.session.add(ing)
        db.session.commit()
        
        return jsonify({'success': True, 'id': ing.id})
        
    except Exception as e:
        db.session.rollback()
        if 'UNIQUE constraint failed' in str(e) or 'duplicate key' in str(e):
            return jsonify({'erreur': 'Ingrédient existe déjà'}), 400
        return jsonify({'erreur': str(e)}), 500

@app.route('/api/ingredient/<int:id>', methods=['PUT'])
def update_ingredient(id):
    try:
        ing = Ingredient.query.get(id)
        if not ing:
            return jsonify({'erreur': 'Ingrédient non trouvé'}), 404
        
        data = request.json
        nom = data.get('nom', '').strip()
        image = data.get('image', '').strip()
        color = data.get('color', '#FF9800')
        
        if not nom or not image:
            return jsonify({'erreur': 'Données incomplètes'}), 400
        
        ing.nom = nom
        ing.image_url = image
        ing.color = color
        db.session.commit()
        
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        if 'UNIQUE constraint failed' in str(e) or 'duplicate key' in str(e):
            return jsonify({'erreur': 'Nom existe déjà'}), 400
        return jsonify({'erreur': str(e)}), 500

@app.route('/api/ingredient/<int:id>', methods=['DELETE'])
def delete_ingredient(id):
    try:
        ing = Ingredient.query.get(id)
        if ing:
            db.session.delete(ing)
            db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'erreur': str(e)}), 500

@app.route('/api/commande/<int:commande_id>/ingredient/<ingredient_nom>/toggle-prepare', methods=['POST'])
def toggle_ingredient_prepare(commande_id, ingredient_nom):
    try:
        # Chercher si déjà tracké
        prep = IngredientPrepare.query.filter_by(
            commande_id=commande_id, 
            ingredient_nom=ingredient_nom
        ).first()
        
        if prep:
            # Basculer l'état
            prep.prepare = 1 - prep.prepare
        else:
            # Créer une nouvelle entrée
            prep = IngredientPrepare(
                commande_id=commande_id,
                ingredient_nom=ingredient_nom,
                prepare=1
            )
            db.session.add(prep)
        
        db.session.commit()
        return jsonify({'success': True, 'prepare': bool(prep.prepare)})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'erreur': str(e)}), 500

@app.route('/api/commande/<int:commande_id>/ingredients-prepares', methods=['GET'])
def get_ingredients_prepares(commande_id):
    try:
        preps = IngredientPrepare.query.filter_by(commande_id=commande_id).all()
        return jsonify({
            ing.ingredient_nom: bool(ing.prepare) 
            for ing in preps
        })
    except Exception as e:
        return jsonify({'erreur': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
