from flask import Flask, render_template, request, jsonify
from datetime import datetime
import os
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)

# Config BD
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://localhost/pizzeria_dev')

def get_db():
    conn = psycopg2.connect(DATABASE_URL)
    return conn

# Config
ALLOWED_IPS = ['127.0.0.1', '192.168.1.']

# Initialiser BD
def init_db():
    conn = get_db()
    c = conn.cursor()
    
    # Table commandes
    c.execute('''CREATE TABLE IF NOT EXISTS commandes (
        id SERIAL PRIMARY KEY,
        nom TEXT,
        base TEXT,
        ingredients TEXT,
        created_at TIMESTAMP,
        statut TEXT DEFAULT 'en attente'
    )''')
    
    # Table ingrédients
    c.execute('''CREATE TABLE IF NOT EXISTS ingredients (
        id SERIAL PRIMARY KEY,
        nom TEXT UNIQUE,
        image_url TEXT,
        color TEXT DEFAULT '#FF9800',
        disponible INTEGER DEFAULT 1
    )''')
    
    # Vérifier si les données par défaut existent
    c.execute('SELECT COUNT(*) FROM ingredients')
    count = c.fetchone()[0]
    
    if count == 0:
        ingredients_default = [
            ('Oignons', 'https://images.unsplash.com/photo-1588195538326-c5b1e9f80a1b?w=200&h=200&fit=crop', '#FFC107'),
            ('Jambon', 'https://images.unsplash.com/photo-1628840042765-356cda07f4ee?w=200&h=200&fit=crop', '#FF6B6B'),
            ('Mozzarella', 'https://images.unsplash.com/photo-1452894896566-922e9cd1a51c?w=200&h=200&fit=crop', '#FFFFFF'),
            ('Pepperoni', 'https://images.unsplash.com/photo-1628840042765-356cda07f4ee?w=200&h=200&fit=crop', '#D32F2F'),
            ('Champignons', 'https://images.unsplash.com/photo-1545069975-85b100854f27?w=200&h=200&fit=crop', '#795548'),
            ('Olives', 'https://images.unsplash.com/photo-1599599810694-a5e1ba78b5dc?w=200&h=200&fit=crop', '#424242')
        ]
        for nom, url, color in ingredients_default:
            c.execute('INSERT INTO ingredients (nom, image_url, color, disponible) VALUES (%s, %s, %s, 1)',
                     (nom, url, color))
    
    conn.commit()
    c.close()
    conn.close()

# Middleware : vérifier IP
@app.before_request
def check_ip():
    ip = request.remote_addr
    if not any(ip.startswith(allowed) for allowed in ALLOWED_IPS):
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
    conn = get_db()
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute('SELECT * FROM commandes WHERE statut = %s ORDER BY created_at DESC', ('en attente',))
    commandes = c.fetchall()
    c.close()
    conn.close()
    
    return jsonify([dict(cmd) for cmd in commandes])

@app.route('/api/commander', methods=['POST'])
def commander():
    data = request.json
    nom = data.get('nom', '').strip()
    base = data.get('base', '')
    ingredients = ','.join(data.get('ingredients', []))

    if not nom or not ingredients:
        return jsonify({'erreur': 'Données incomplètes'}), 400

    conn = get_db()
    c = conn.cursor()
    c.execute('INSERT INTO commandes (nom, base, ingredients, created_at) VALUES (%s, %s, %s, %s)',
              (nom, base, ingredients, datetime.now()))
    conn.commit()
    c.close()
    conn.close()

    return jsonify({'success': True, 'message': 'Pizza commandée !'})

@app.route('/api/fait/<int:id>', methods=['POST'])
def marquer_fait(id):
    conn = get_db()
    c = conn.cursor()
    c.execute('UPDATE commandes SET statut = %s WHERE id = %s', ('fait', id))
    conn.commit()
    c.close()
    conn.close()
    return jsonify({'success': True})

# --- API CONFIG ---

@app.route('/api/config', methods=['GET'])
def get_config():
    conn = get_db()
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute('SELECT id, nom, image_url, color FROM ingredients WHERE disponible = 1')
    ingredients = c.fetchall()
    c.close()
    conn.close()
    
    return jsonify({
        'bases': ['Base tomate', 'Base crème fraîche'],
        'ingredients': [dict(ing) for ing in ingredients]
    })

# --- API INGRÉDIENTS ---

@app.route('/api/ingredients', methods=['GET'])
def get_ingredients():
    conn = get_db()
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute('SELECT id, nom, image_url, color, disponible FROM ingredients')
    ingredients = c.fetchall()
    c.close()
    conn.close()
    
    return jsonify([dict(ing) for ing in ingredients])

@app.route('/api/ingredient/<int:id>/toggle', methods=['POST'])
def toggle_ingredient(id):
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT disponible FROM ingredients WHERE id = %s', (id,))
    result = c.fetchone()
    
    if not result:
        c.close()
        conn.close()
        return jsonify({'erreur': 'Ingrédient non trouvé'}), 404
    
    nouveau_statut = 1 - result[0]
    c.execute('UPDATE ingredients SET disponible = %s WHERE id = %s', (nouveau_statut, id))
    conn.commit()
    c.close()
    conn.close()
    
    return jsonify({'success': True, 'disponible': bool(nouveau_statut)})

@app.route('/api/ingredient', methods=['POST'])
def add_ingredient():
    try:
        data = request.json
        nom = data.get('nom', '').strip()
        image = data.get('image', 'https://via.placeholder.com/200').strip()
        color = data.get('color', '#FF9800')
        
        if not nom:
            return jsonify({'erreur': 'Nom vide'}), 400
        
        if not image:
            image = 'https://via.placeholder.com/200'
        
        conn = get_db()
        c = conn.cursor()
        c.execute('INSERT INTO ingredients (nom, image_url, color, disponible) VALUES (%s, %s, %s, 1)',
                  (nom, image, color))
        conn.commit()
        c.close()
        conn.close()
        
        return jsonify({'success': True})
        
    except psycopg2.IntegrityError:
        return jsonify({'erreur': 'Ingrédient existe déjà'}), 400
    except Exception as e:
        return jsonify({'erreur': str(e)}), 500

@app.route('/api/ingredient/<int:id>', methods=['PUT'])
def update_ingredient(id):
    try:
        data = request.json
        nom = data.get('nom', '').strip()
        image = data.get('image', '').strip()
        color = data.get('color', '#FF9800')
        
        if not nom:
            return jsonify({'erreur': 'Nom vide'}), 400
        
        if not image:
            return jsonify({'erreur': 'URL image vide'}), 400
        
        conn = get_db()
        c = conn.cursor()
        c.execute('UPDATE ingredients SET nom = %s, image_url = %s, color = %s WHERE id = %s',
                  (nom, image, color, id))
        conn.commit()
        c.close()
        conn.close()
        
        return jsonify({'success': True})
        
    except psycopg2.IntegrityError:
        return jsonify({'erreur': 'Nom existe déjà'}), 400
    except Exception as e:
        return jsonify({'erreur': str(e)}), 500

@app.route('/api/ingredient/<int:id>', methods=['DELETE'])
def delete_ingredient(id):
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute('DELETE FROM ingredients WHERE id = %s', (id,))
        conn.commit()
        c.close()
        conn.close()
        
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'erreur': str(e)}), 500

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
