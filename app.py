from flask import Flask, render_template, request, jsonify
from datetime import datetime
from flask_talisman import Talisman
import sqlite3
import os

app = Flask(__name__)
Talisman(app)  # Force HTTPS

# Config
ALLOWED_IPS = ['127.0.0.1', '192.168.1.']
DB_FILE = 'pizzas.db'

# Initialiser BD
def init_db():
    if not os.path.exists(DB_FILE):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        
        # Table commandes
        c.execute('''CREATE TABLE commandes
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      nom TEXT, base TEXT, ingredients TEXT,
                      created_at TIMESTAMP, statut TEXT DEFAULT 'en attente')''')
        
        # Table ingrédients (avec image et couleur)
        c.execute('''CREATE TABLE ingredients
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      nom TEXT UNIQUE, image_url TEXT, color TEXT DEFAULT '#FF9800', disponible INTEGER DEFAULT 1)''')
        
        # Ingrédients par défaut avec images et couleurs
        ingredients_default = [
            ('Oignons', 'https://images.unsplash.com/photo-1588195538326-c5b1e9f80a1b?w=200&h=200&fit=crop', '#FFC107'),
            ('Jambon', 'https://images.unsplash.com/photo-1628840042765-356cda07f4ee?w=200&h=200&fit=crop', '#FF6B6B'),
            ('Mozzarella', 'https://images.unsplash.com/photo-1452894896566-922e9cd1a51c?w=200&h=200&fit=crop', '#FFFFFF'),
            ('Pepperoni', 'https://images.unsplash.com/photo-1628840042765-356cda07f4ee?w=200&h=200&fit=crop', '#D32F2F'),
            ('Champignons', 'https://images.unsplash.com/photo-1545069975-85b100854f27?w=200&h=200&fit=crop', '#795548'),
            ('Olives', 'https://images.unsplash.com/photo-1599599810694-a5e1ba78b5dc?w=200&h=200&fit=crop', '#424242')
        ]
        for nom, url, color in ingredients_default:
            c.execute('INSERT INTO ingredients (nom, image_url, color, disponible) VALUES (?, ?, ?, 1)', (nom, url, color))
        
        conn.commit()
        conn.close()

# Middleware : vérifier IP

ALLOWED_PUBLIC_IPS = [os.getenv('HOME_IP', '')]  # À configurer

@app.before_request
def check_ip():
    ip = request.remote_addr
    # Vérifie IP locale OU IP publique
    if not (any(ip.startswith(allowed) for allowed in ['127.0.0.1', '192.168.1.']) 
            or ip == ALLOWED_PUBLIC_IPS[0]):
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
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT * FROM commandes WHERE statut = "en attente" ORDER BY created_at DESC')
    commandes = [
        {'id': row[0], 'nom': row[1], 'base': row[2], 'ingredients': row[3], 'heure': row[4]}
        for row in c.fetchall()
    ]
    conn.close()
    return jsonify(commandes)

@app.route('/api/commander', methods=['POST'])
def commander():
    data = request.json
    nom = data.get('nom', '').strip()
    base = data.get('base', '')
    ingredients = ','.join(data.get('ingredients', []))

    if not nom or not ingredients:
        return jsonify({'erreur': 'Données incomplètes'}), 400

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('INSERT INTO commandes (nom, base, ingredients, created_at) VALUES (?, ?, ?, ?)',
              (nom, base, ingredients, datetime.now().isoformat()))
    conn.commit()
    conn.close()

    return jsonify({'success': True, 'message': 'Pizza commandée !'})

@app.route('/api/fait/<int:id>', methods=['POST'])
def marquer_fait(id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('UPDATE commandes SET statut = "fait" WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

# --- API CONFIG (avec ingrédients disponibles, images et couleurs) ---

@app.route('/api/config', methods=['GET'])
def get_config():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT id, nom, image_url, color FROM ingredients WHERE disponible = 1')
    ingredients = [
        {'id': row[0], 'nom': row[1], 'image': row[2], 'color': row[3]}
        for row in c.fetchall()
    ]
    conn.close()
    
    return jsonify({
        'bases': ['Base tomate', 'Base crème fraîche'],
        'ingredients': ingredients
    })

# --- API INGRÉDIENTS (pour le cuisinier) ---

@app.route('/api/ingredients', methods=['GET'])
def get_ingredients():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT id, nom, image_url, color, disponible FROM ingredients')
    ingredients = [
        {'id': row[0], 'nom': row[1], 'image': row[2], 'color': row[3], 'disponible': bool(row[4])}
        for row in c.fetchall()
    ]
    conn.close()
    return jsonify(ingredients)

@app.route('/api/ingredient/<int:id>/toggle', methods=['POST'])
def toggle_ingredient(id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT disponible FROM ingredients WHERE id = ?', (id,))
    result = c.fetchone()
    
    if not result:
        return jsonify({'erreur': 'Ingrédient non trouvé'}), 404
    
    nouveau_statut = 1 - result[0]
    c.execute('UPDATE ingredients SET disponible = ? WHERE id = ?', (nouveau_statut, id))
    conn.commit()
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
        
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('INSERT INTO ingredients (nom, image_url, color, disponible) VALUES (?, ?, ?, 1)', 
                  (nom, image, color))
        conn.commit()
        id_new = c.lastrowid
        conn.close()
        
        return jsonify({'success': True, 'id': id_new})
        
    except sqlite3.IntegrityError:
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
        
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('UPDATE ingredients SET nom = ?, image_url = ?, color = ? WHERE id = ?', 
                  (nom, image, color, id))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
        
    except sqlite3.IntegrityError:
        return jsonify({'erreur': 'Nom existe déjà'}), 400
    except Exception as e:
        return jsonify({'erreur': str(e)}), 500

@app.route('/api/ingredient/<int:id>', methods=['DELETE'])
def delete_ingredient(id):
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('DELETE FROM ingredients WHERE id = ?', (id,))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'erreur': str(e)}), 500

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5050, debug=True)