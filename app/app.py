from flask import Flask, render_template, request, redirect, url_for, send_file, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os, sqlite3, yaml
from pathlib import Path

app = Flask(__name__)
app.secret_key = 'change-this-secret-key'
CONFIG_PATH = '/app/config.yaml'

login_manager = LoginManager(app)
login_manager.login_view = 'login'

def load_sources():
    with open(CONFIG_PATH) as f:
        cfg = yaml.safe_load(f)
    return cfg.get('photo_sources', [])

def get_all_photos(sort='newest'):
    sources = load_sources()
    extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
    photos = []
    for source in sources:
        if not os.path.isdir(source):
            continue
        for f in Path(source).iterdir():
            if f.suffix.lower() in extensions:
                stat = f.stat()
                photos.append({
                    'filename': f.name,
                    'path': str(f),
                    'source': source,
                    'ctime': stat.st_ctime,
                    'size': stat.st_size
                })
    if sort == 'newest':
        photos.sort(key=lambda x: x['ctime'], reverse=True)
    elif sort == 'oldest':
        photos.sort(key=lambda x: x['ctime'])
    elif sort == 'name':
        photos.sort(key=lambda x: x['filename'].lower())
    return photos

def get_db():
    conn = sqlite3.connect('/data/users.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    os.makedirs('/data', exist_ok=True)
    conn = get_db()
    conn.execute('''CREATE TABLE IF NOT EXISTS users
                    (id INTEGER PRIMARY KEY, username TEXT UNIQUE,
                     password TEXT, is_admin INTEGER)''')
    if not conn.execute('SELECT * FROM users WHERE username = "admin"').fetchone():
        conn.execute('INSERT INTO users (username, password, is_admin) VALUES (?, ?, ?)',
                     ('admin', generate_password_hash('admin123'), 1))
    conn.commit()
    conn.close()

class User(UserMixin):
    def __init__(self, id, username, is_admin):
        self.id = id
        self.username = username
        self.is_admin = bool(is_admin)

@login_manager.user_loader
def load_user(user_id):
    conn = get_db()
    u = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    if u:
        return User(u['id'], u['username'], u['is_admin'])

@app.template_filter('datetimeformat')
def datetimeformat(value):
    return datetime.fromtimestamp(value).strftime('%d %b %Y, %H:%M')

@app.route('/')
@login_required
def index():
    sort = request.args.get('sort', 'newest')
    photos = get_all_photos(sort)
    return render_template('index.html', photos=photos, sort=sort)

@app.route('/photo')
@login_required
def photo():
    path = request.args.get('path')
    sources = load_sources()
    if not any(path.startswith(s) for s in sources):
        return 'Forbidden', 403
    return send_file(path)

@app.route('/delete', methods=['POST'])
@login_required
def delete():
    if not current_user.is_admin:
        flash('Permission denied')
        return redirect(url_for('index'))
    path = request.form.get('path')
    sources = load_sources()
    if not any(path.startswith(s) for s in sources):
        return 'Forbidden', 403
    if os.path.exists(path):
        os.remove(path)
    return redirect(url_for('index', sort=request.form.get('sort', 'newest')))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        conn = get_db()
        u = conn.execute('SELECT * FROM users WHERE username = ?',
                         (request.form['username'],)).fetchone()
        conn.close()
        if u and check_password_hash(u['password'], request.form['password']):
            login_user(User(u['id'], u['username'], u['is_admin']))
            return redirect(url_for('index'))
        flash('Invalid credentials')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/admin/users', methods=['GET', 'POST'])
@login_required
def manage_users():
    if not current_user.is_admin:
        return redirect(url_for('index'))
    conn = get_db()
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            try:
                conn.execute(
                    'INSERT INTO users (username, password, is_admin) VALUES (?, ?, ?)',
                    (request.form['username'],
                     generate_password_hash(request.form['password']), 0))
                conn.commit()
                flash('User added')
            except:
                flash('Username already exists')
        elif action == 'delete':
            conn.execute('DELETE FROM users WHERE id = ? AND is_admin = 0',
                         (request.form['user_id'],))
            conn.commit()
    users = conn.execute('SELECT * FROM users').fetchall()
    conn.close()
    return render_template('users.html', users=users)

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000)
