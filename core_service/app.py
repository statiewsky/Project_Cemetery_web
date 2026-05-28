import os
from datetime import datetime, timedelta
import requests
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_jwt_extended import JWTManager, create_access_token

from database import (
    init_db, register_user, login_user, get_user_by_username, get_all_projects, add_project, get_project_by_id, search_projects, add_candle, get_candles_count,
    add_comment, get_comments, add_publication, get_publications, get_publication_by_id, get_stats, get_user_candles, get_user_publications, has_user_candle, get_db)


app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-cemetery-secret-key')
app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'jwt-cemetery-secret')
app.config['JWT_TOKEN_LOCATION'] = ['headers']
jwt = JWTManager(app)





def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Для доступа необходимо войти в систему.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


@app.template_filter('msk')
def format_msk_time(date_str):
    if not date_str:
        return ""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
        dt_msk = dt + timedelta(hours=3)
        return dt_msk.strftime("%d.%m.%Y %H:%M")
    except Exception as e:
        return date_str

@app.context_processor
def inject_auth():
    return {
        'is_logged_in': 'user_id' in session,
        'current_user': session.get('username', 'Гость')
    }



#ВОЗМОЖНОСТИ ДО РЕГИСТРАЦИИ
@app.route('/')
def index():
    stats = get_stats()
    return render_template('index.html', stats=stats)

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contacts')
def contacts():
    return render_template("contacts.html")


#РЕГИСТРАЦИЯ, ВХОД, ВЫХОД
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        username = request.form.get('username')
        password = request.form.get('password')

        if not all([name, username, password]):
            flash('Заполните все поля!', 'error')
            return redirect(url_for('register'))

        user = register_user(name, username, password)
        if user:
            return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = login_user(username, password)
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['name'] = user['name']

            access_token = create_access_token(identity=username)
            session['jwt_token'] = access_token

            return redirect(url_for('index'))

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('Вы вышли из системы.', 'info')
    return redirect(url_for('index'))

#ДОСТУПНО ПОСЛЕ ВХОДА


@app.route('/feed')
@login_required
def feed():
    query = request.args.get('q', '').strip()
    stage = request.args.get('stage', '').strip()
    tech = request.args.get('tech', '').strip()
    page = request.args.get('page', 1, type=int)

    projects = search_projects(query=query, stage=stage, tech=tech, page=page, per_page=10)

    return render_template('feed.html',
                           projects=projects,
                           query=query,
                           stage=stage,
                           tech=tech,
                           page=page)


@app.route('/candles')
@login_required
def my_candles():
    projects = get_user_candles(session['username'])
    return render_template('candles.html', projects=projects)


@app.route('/<username>')
@login_required
def user_profile(username):
    if session['username'] != username:
        return redirect(url_for('feed'))

    user = get_user_by_username(username)
    if not user:
        return redirect(url_for('feed'))

    user = dict(user)

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM projects WHERE user_id = ?", (user['id'],))
    user['projects_count'] = cursor.fetchone()[0]
    conn.close()

    return render_template('profile.html', user=user)


@app.route('/<username>/refresh-token', methods=['POST'])
@login_required
def refresh_token_route(username):
    if session['username'] != username:
        return redirect(url_for('feed'))

    new_token = create_access_token(identity=username)
    session['jwt_token'] = new_token

    print(f"Токен обновлен для {username}: ...{new_token[-20:]}")
    return redirect(url_for('user_profile', username=username))





@app.route('/publications')
@login_required
def my_publications():
    pubs = get_user_publications(session['user_id'])
    return render_template('publications.html', publications=pubs)


# ПРОЕКТЫ, СВЕЧИ, КОММЕНТЫ
@app.route('/project/add', methods=['GET', 'POST'])
@login_required
def add_project_route():
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        fail_reason = request.form.get('fail_reason')
        epitaph = request.form.get('epitaph')
        tech_stack = request.form.get('tech_stack')
        fail_stage = request.form.get('fail_stage')

        if title and description:
            add_project(title, description, fail_reason, epitaph, tech_stack, fail_stage, session['user_id'])
            return redirect(url_for('feed'))

    return render_template('add_project.html')


@app.route('/project/<int:project_id>')
@login_required
def project_detail(project_id):
    project = get_project_by_id(project_id)
    if not project:
        return redirect(url_for('feed'))

    candles_count = get_candles_count(project_id)
    comments = get_comments(project_id)
    return render_template('project_detail.html', project=project, candles_count=candles_count, comments=comments)


@app.route('/project/<int:project_id>/candle', methods=['POST'])
@login_required
def press_f(project_id):
    add_candle(project_id, session['username'])
    return redirect(url_for('project_detail', project_id=project_id))


@app.route('/project/<int:project_id>/comment', methods=['POST'])
@login_required
def add_comment_route(project_id):
    message = request.form.get('message')
    if message:
        add_comment(project_id, session['username'], message, session['user_id'])
    return redirect(url_for('project_detail', project_id=project_id))




if __name__ == '__main__':
    from database import init_db
    with app.app_context():
        init_db()
    app.run(debug=True)