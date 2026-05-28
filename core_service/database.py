import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash

DB_NAME = 'database.db'


def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)


    cursor.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            fail_reason TEXT,
            epitaph TEXT,
            tech_stack TEXT,
            fail_stage TEXT,
            user_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
        )
    """)


    cursor.execute("""
        CREATE TABLE IF NOT EXISTS candles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            username TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        )
    """)


    cursor.execute("""
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            user_id INTEGER,
            username TEXT,
            message TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS publications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            author TEXT,
            author_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (author_id) REFERENCES users(id) ON DELETE SET NULL
        )
    """)

    conn.commit()
    conn.close()


# ФУНКЦИИ ДЛЯ ПОЛЬЗОВАТЕЛЕЙ
def register_user(name, username, password):
    conn = get_db()
    cursor = conn.cursor()
    try:
        hashed_pw = generate_password_hash(password)
        cursor.execute(
            "INSERT INTO users (name, username, password_hash) VALUES (?, ?, ?)",
            (name, username, hashed_pw)
        )
        conn.commit()
        return {"id": cursor.lastrowid, "username": username}
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()


def login_user(username, password):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
    user = cursor.fetchone()
    conn.close()

    if user and check_password_hash(user['password_hash'], password):
        return {"id": user['id'], "username": user['username'], "name": user['name']}
    return None


def get_user_by_id(user_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, created_at FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user


def get_user_by_username(username):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, username, created_at FROM users WHERE username = ?", (username,))
    user = cursor.fetchone()
    conn.close()
    return user


def get_user_candles(username):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.*, c.created_at as candle_date
        FROM candles c
        JOIN projects p ON c.project_id = p.id
        WHERE c.username = ?
        ORDER BY c.created_at DESC
    """, (username,))
    projects = cursor.fetchall()
    conn.close()
    return projects


def get_user_publications(user_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM projects
        WHERE user_id = ?
        ORDER BY created_at DESC
    """, (user_id,))
    publications = cursor.fetchall()
    conn.close()
    return publications


#ФУНКЦИИ ДЛЯ ПРОЕКТОВ
def add_project(title, description, fail_reason, epitaph, tech_stack, fail_stage, user_id=None):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO projects 
           (title, description, fail_reason, epitaph, tech_stack, fail_stage, user_id) 
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (title, description, fail_reason, epitaph, tech_stack, fail_stage, user_id)
    )
    conn.commit()
    project_id = cursor.lastrowid
    conn.close()
    return project_id


def get_all_projects(page=1, per_page=10, order_by="created_at", sort="DESC"):
    conn = get_db()
    cursor = conn.cursor()
    offset = (page - 1) * per_page
    cursor.execute(f"""
        SELECT p.*, u.username as author_name
        FROM projects p
        LEFT JOIN users u ON p.user_id = u.id
        ORDER BY p.{order_by} {sort.upper()}
        LIMIT ? OFFSET ?
    """, (per_page, offset))

    projects = cursor.fetchall()
    conn.close()
    return projects


def update_project(project_id, title, description, fail_reason, epitaph, tech_stack, fail_stage):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE projects 
        SET title=?, description=?, fail_reason=?, epitaph=?, tech_stack=?, fail_stage=? 
        WHERE id=?
    """, (title, description, fail_reason, epitaph, tech_stack, fail_stage, project_id))
    conn.commit()
    conn.close()


def delete_project(project_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    conn.commit()
    conn.close()


def get_project_by_id(project_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.*, u.username as author_name
        FROM projects p
        LEFT JOIN users u ON p.user_id = u.id
        WHERE p.id = ?
    """, (project_id,))
    project = cursor.fetchone()
    conn.close()
    return project


def search_projects(query="", stage="", tech="", page=1, per_page=10):
    conn = get_db()
    cursor = conn.cursor()
    sql = """
        SELECT p.*, u.username as author_name
        FROM projects p
        LEFT JOIN users u ON p.user_id = u.id
        WHERE 1=1
    """
    params = []

    if query:
        sql += " AND (p.title LIKE ? OR p.description LIKE ? OR p.tech_stack LIKE ?)"
        params.extend([f"%{query}%", f"%{query}%", f"%{query}%"])

    if stage and stage != "all":
        sql += " AND p.fail_stage = ?"
        params.append(stage)

    if tech:
        sql += " AND p.tech_stack LIKE ?"
        params.append(f"%{tech}%")

    offset = (page - 1) * per_page
    sql += f" ORDER BY p.created_at DESC LIMIT ? OFFSET ?"
    params.extend([per_page, offset])

    cursor.execute(sql, params)
    projects = cursor.fetchall()
    conn.close()
    return projects


#ФУНКЦИИ ДЛЯ СВЕЧЕЙ

def has_user_candle(project_id, username):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM candles WHERE project_id = ? AND username = ?",
        (project_id, username)
    )
    count = cursor.fetchone()[0]
    conn.close()
    return count > 0


def add_candle(project_id, username):
    if has_user_candle(project_id, username):
        return False

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO candles (project_id, username) VALUES (?, ?)",
            (project_id, username)
        )
        conn.commit()
        return True
    finally:
        conn.close()


def get_candles_count(project_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM candles WHERE project_id = ?",
        (project_id,)
    )
    count = cursor.fetchone()[0]
    conn.close()
    return count

def add_comment(project_id, username, message, user_id=None):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO comments (project_id, username, message, user_id) VALUES (?, ?, ?, ?)",
        (project_id, username, message, user_id)
    )
    conn.commit()
    conn.close()

def get_comments(project_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT c.*, u.username as author_name
        FROM comments c
        LEFT JOIN users u ON c.user_id = u.id
        WHERE c.project_id = ?
        ORDER BY c.created_at DESC
    """, (project_id,))
    comments = cursor.fetchall()
    conn.close()
    return comments


# ФУНКЦИИ ДЛЯ ПУБЛИКАЦИЙ
def add_publication(title, content, author, author_id=None):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO publications (title, content, author, author_id) VALUES (?, ?, ?, ?)",
        (title, content, author, author_id)
    )
    conn.commit()
    pub_id = cursor.lastrowid
    conn.close()
    return pub_id

def get_publications(page=1, per_page=10):
    conn = get_db()
    cursor = conn.cursor()
    offset = (page - 1) * per_page
    cursor.execute("""
        SELECT p.*, u.username as author_name
        FROM publications p
        LEFT JOIN users u ON p.author_id = u.id
        ORDER BY p.created_at DESC
        LIMIT ? OFFSET ?
    """, (per_page, offset))
    publications = cursor.fetchall()
    conn.close()
    return publications

def get_publication_by_id(pub_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.*, u.username as author_name
        FROM publications p
        LEFT JOIN users u ON p.author_id = u.id
        WHERE p.id = ?
    """, (pub_id,))
    pub = cursor.fetchone()
    conn.close()
    return pub

def get_stats():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM projects")
    projects_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM candles")
    candles_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM comments")
    comments_count = cursor.fetchone()[0]

    conn.close()

    return {
        "projects": projects_count,
        "candles": candles_count,
        "comments": comments_count,
    }




