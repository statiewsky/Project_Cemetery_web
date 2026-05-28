import os
import json
import hashlib
import sqlite3
from flask import Flask, render_template, jsonify

current_dir = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__,
            template_folder=os.path.join(current_dir, 'templates'),
            static_folder=os.path.join(current_dir, 'static'))

ABOUT_JSON_PATH = os.path.join(current_dir, 'about.json')
DB_PATH = os.path.join(current_dir, '..', 'database.db')


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@app.route('/')
def index():
    return render_template('index_sup.html')


@app.route('/about')
def about_page():
    try:
        with open(ABOUT_JSON_PATH, 'r', encoding='utf-8') as f:
            about_data = json.load(f)
        return render_template('about_sup.html', data=about_data)  # <-- about_sup.html
    except FileNotFoundError:
        return jsonify({"error": "about.json not found"}), 404


@app.route('/api/hash/<string:text>')
def get_hash(text):
    if not text:
        return jsonify({"error": "Empty string"}), 400

    result = hashlib.sha256(text.encode('utf-8')).hexdigest()
    return jsonify({
        "request": text,
        "result": result
    }), 200



if __name__ == '__main__':
    app.run(debug=True, port=5001)