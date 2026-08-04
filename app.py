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
HOME_IP = os.getenv('HOME_IP', '')

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
            ('Oignons', 'https://images.unsplash.com/photo-1588195538326-c5b1e9f80a1b?w=200&h=200&fit=crop', '#FFC107'),
            ('Jambon', 'https://images.unsplash.com/photo-1628840042765-356cda07f4ee?w=200&h=200&fit=crop', '#FF6B6B'),
            ('Mozzarella', 'https://images.unsplash.com/photo-1452894896566-922e9cd1a51c?w=200&h=200&fit=crop', '#FFFFFF'),
            ('Champignons', 'https://images.unsplash.com/photo-1545069975-85b100854f27?w=200&h=200&fit=crop', '#795548'),
            ('Olives', 'https://images.unsplash.com/photo-1599599810694-a5e1ba78b5dc?w=200&h=200&fit=crop', '#424242')
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
    
    home_ip = os.getenv('HOME_IP', '')
    
    print(f"DEBUG: IP={ip}, HOME_IP={home_ip}, Match={ip.startswith(home_ip)}")
    
    if not (any(ip.startswith(allowed) for allowed in ['127.0.0.1', '192.168.1.']) 
            or (home_ip and ip.startswith(home_ip))):
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
