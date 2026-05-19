from flask import Flask, render_template, request, redirect, url_for, send_file, flash, jsonify
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
import os, sqlite3, yaml
from pathlib import Path

app = Flask(__name__)
app.secret_key = 'change-this-secret-key'
CONFIG_PATH = '/app/config.yaml'
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}

login_manager = LoginManager(app)
login_manager.login_view = 'login'

def load_config():
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)

def get_db():
    conn = sqlite3.connect('/data/users.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    os.makedirs('/data', exist_ok=True)
    conn = get_db()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT UNIQUE,
            password TEXT,
            is_admin INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS photos (
            id INTEGER PRIMARY KEY,
            path TEXT UNIQUE,
            filename TEXT,
            ctime REAL,
            uploaded_by TEXT
        );
        CREATE TABLE IF NOT EXISTS photo_people (
            photo_id INTEGER,
            person TEXT,
            PRIMARY KEY (photo_id, person),
            FOREIGN KEY (photo_id) REFERENCES photos(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS photo_places (
            photo_id INTEGER,
            place TEXT,
            PRIMARY KEY (photo_id, place),
            FOREIGN KEY (photo_id) REFERENCES photos(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS favorites (
            photo_id INTEGER,
            user_id INTEGER,
            PRIMARY KEY (photo_id, user_id),
            FOREIGN KEY (photo_id) REFERENCES photos(id) ON DELETE CASCADE
        );
    ''')
    if not conn.execute('SELECT * FROM users WHERE username = "grisho"').fetchone():
        conn.execute('INSERT INTO users (username, password, is_admin) VALUES (?, ?, ?)',
                     ('grisho', generate_password_hash('admin123'), 1))
    conn.commit()
    conn.close()

def sync_photos():
    cfg = load_config()
    sources = cfg.get('photo_sources', [])
    conn = get_db()
    for source in sources:
        if not os.path.isdir(source):
            continue
        for f in Path(source).iterdir():
            if f.suffix.lower() in ALLOWED_EXTENSIONS:
                stat = f.stat()
                conn.execute('''INSERT OR IGNORE INTO photos (path, filename, ctime, uploaded_by)
                                VALUES (?, ?, ?, ?)''',
                             (str(f), f.name, stat.st_ctime, 'system'))
    conn.commit()
    conn.close()

def get_photos(sort='newest', people=None, place=None, date_from=None, date_to=None, favorites_only=False):
    conn = get_db()
    query = '''SELECT DISTINCT p.*, 
               GROUP_CONCAT(DISTINCT pp.person) as people_tags,
               GROUP_CONCAT(DISTINCT pl.place) as place_tags,
               EXISTS(SELECT 1 FROM favorites f WHERE f.photo_id = p.id AND f.user_id = ?) as is_favorite
               FROM photos p
               LEFT JOIN photo_people pp ON pp.photo_id = p.id
               LEFT JOIN photo_places pl ON pl.photo_id = p.id
               LEFT JOIN favorites fv ON fv.photo_id = p.id
               WHERE 1=1'''
    params = [current_user.id]

    if people:
        placeholders = ','.join(['?' for _ in people])
        query += f''' AND p.id IN (
            SELECT photo_id FROM photo_people WHERE person IN ({placeholders})
            GROUP BY photo_id HAVING COUNT(DISTINCT person) = ?
        )'''
        params.extend(people)
        params.append(len(people))

    if place:
        query += ' AND pl.place LIKE ?'
        params.append(f'%{place}%')

    if date_from:
        query += ' AND p.ctime >= ?'
        params.append(datetime.strptime(date_from, '%Y-%m-%d').timestamp())

    if date_to:
        query += ' AND p.ctime <= ?'
        params.append(datetime.strptime(date_to, '%Y-%m-%d').timestamp() + 86400)

    if favorites_only:
        query += ' AND fv.user_id = ?'
        params.append(current_user.id)

    query += ' GROUP BY p.id'

    if sort == 'newest':
        query += ' ORDER BY p.ctime DESC'
    elif sort == 'oldest':
        query += ' ORDER BY p.ctime ASC'
    elif sort == 'name':
        query += ' ORDER BY p.filename ASC'

    photos = conn.execute(query, params).fetchall()
    conn.close()
    return photos

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
    return datetime.fromtimestamp(value).strftime('%d %b %Y')

@app.route('/')
@login_required
def index():
    sync_photos()
    sort = request.args.get('sort', 'newest')
    people = request.args.getlist('people')
    place = request.args.get('place', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    favorites_only = request.args.get('favorites') == '1'
    cfg = load_config()

    photos = get_photos(sort, people or None, place or None,
                        date_from or None, date_to or None, favorites_only)

    # Get all unique places for filter dropdown
    conn = get_db()
    places = [r[0] for r in conn.execute('SELECT DISTINCT place FROM photo_places ORDER BY place').fetchall()]
    conn.close()

    return render_template('index.html', photos=photos, sort=sort,
                           people_list=cfg['people'], places=places,
                           selected_people=people, selected_place=place,
                           date_from=date_from, date_to=date_to,
                           favorites_only=favorites_only)

@app.route('/photo')
@login_required
def photo():
    path = request.args.get('path')
    cfg = load_config()
    sources = cfg.get('photo_sources', []) + [cfg.get('upload_root', '')]
    if not any(path.startswith(s) for s in sources):
        return 'Forbidden', 403
    return send_file(path)

@app.route('/tag/<int:photo_id>', methods=['POST'])
@login_required
def tag_photo(photo_id):
    people = request.form.getlist('people')
    place = request.form.get('place', '').strip()
    conn = get_db()
    conn.execute('DELETE FROM photo_people WHERE photo_id = ?', (photo_id,))
    conn.execute('DELETE FROM photo_places WHERE photo_id = ?', (photo_id,))
    for person in people:
        conn.execute('INSERT OR IGNORE INTO photo_people (photo_id, person) VALUES (?, ?)', (photo_id, person))
    if place:
        conn.execute('INSERT OR IGNORE INTO photo_places (photo_id, place) VALUES (?, ?)', (photo_id, place))
    conn.commit()
    conn.close()
    return redirect(request.referrer or url_for('index'))

@app.route('/favorite/<int:photo_id>', methods=['POST'])
@login_required
def toggle_favorite(photo_id):
    conn = get_db()
    existing = conn.execute('SELECT 1 FROM favorites WHERE photo_id = ? AND user_id = ?',
                            (photo_id, current_user.id)).fetchone()
    if existing:
        conn.execute('DELETE FROM favorites WHERE photo_id = ? AND user_id = ?',
                     (photo_id, current_user.id))
    else:
        conn.execute('INSERT INTO favorites (photo_id, user_id) VALUES (?, ?)',
                     (photo_id, current_user.id))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})

@app.route('/delete/<int:photo_id>', methods=['POST'])
@login_required
def delete(photo_id):
    if not current_user.is_admin:
        flash('Permission denied')
        return redirect(url_for('index'))
    conn = get_db()
    photo = conn.execute('SELECT * FROM photos WHERE id = ?', (photo_id,)).fetchone()
    if photo and os.path.exists(photo['path']):
        os.remove(photo['path'])
    conn.execute('DELETE FROM photos WHERE id = ?', (photo_id,))
    conn.commit()
    conn.close()
    return redirect(request.referrer or url_for('index'))

@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    cfg = load_config()
    upload_root = cfg.get('upload_root', '/photos/uploads')
    user_folder = os.path.join(upload_root, current_user.username.lower())
    os.makedirs(user_folder, exist_ok=True)

    if request.method == 'POST':
        files = request.files.getlist('photos')
        uploaded = 0
        for file in files:
            if file and Path(file.filename).suffix.lower() in ALLOWED_EXTENSIONS:
                filename = secure_filename(file.filename)
                dest = os.path.join(user_folder, filename)
                # Avoid overwriting
                if os.path.exists(dest):
                    base, ext = os.path.splitext(filename)
                    filename = f"{base}_{int(datetime.now().timestamp())}{ext}"
                    dest = os.path.join(user_folder, filename)
                file.save(dest)
                uploaded += 1
        flash(f'{uploaded} photo(s) uploaded successfully')
        return redirect(url_for('upload'))

    return render_template('upload.html')

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

@app.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current = request.form.get('current_password')
        new = request.form.get('new_password')
        confirm = request.form.get('confirm_password')
        conn = get_db()
        u = conn.execute('SELECT * FROM users WHERE id = ?', (current_user.id,)).fetchone()
        if not check_password_hash(u['password'], current):
            flash('Current password is incorrect')
        elif new != confirm:
            flash('New passwords do not match')
        elif len(new) < 6:
            flash('Password must be at least 6 characters')
        else:
            conn.execute('UPDATE users SET password = ? WHERE id = ?',
                         (generate_password_hash(new), current_user.id))
            conn.commit()
            flash('Password changed successfully')
        conn.close()
    return render_template('change_password.html')

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
                conn.execute('INSERT INTO users (username, password, is_admin) VALUES (?, ?, ?)',
                             (request.form['username'],
                              generate_password_hash(request.form['password']), 0))
                conn.commit()
                flash('User added')
            except:
                flash('Username already exists')
        elif action == 'delete':
            conn.execute('DELETE FROM users WHERE id = ? AND is_admin = 0', (request.form['user_id'],))
            conn.commit()
    users = conn.execute('SELECT * FROM users').fetchall()
    conn.close()
    return render_template('users.html', users=users)

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000)
