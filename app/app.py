from flask import Flask, render_template, request, redirect, url_for, send_file, flash, jsonify
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
from PIL import Image, ImageOps
from pathlib import Path
import os, sqlite3, yaml, io, zipfile

app = Flask(__name__)
app.secret_key = 'change-this-secret-key'
CONFIG_PATH = '/app/config.yaml'
PHOTO_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
VIDEO_EXTENSIONS = {'.mp4', '.mov', '.avi', '.mkv'}
ALL_EXTENSIONS = PHOTO_EXTENSIONS | VIDEO_EXTENSIONS
THUMB_SIZE = (400, 400)

login_manager = LoginManager(app)
login_manager.login_view = 'login'

def load_config():
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)

def get_db():
    conn = sqlite3.connect('/data/users.db')
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn

def init_db():
    os.makedirs('/data', exist_ok=True)
    os.makedirs('/photos/thumbnails', exist_ok=True)
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
            uploaded_by TEXT,
            media_type TEXT DEFAULT 'photo'
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
        CREATE TABLE IF NOT EXISTS albums (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            created_by TEXT,
            created_at REAL
        );
        CREATE TABLE IF NOT EXISTS album_photos (
            album_id INTEGER,
            photo_id INTEGER,
            PRIMARY KEY (album_id, photo_id),
            FOREIGN KEY (album_id) REFERENCES albums(id) ON DELETE CASCADE,
            FOREIGN KEY (photo_id) REFERENCES photos(id) ON DELETE CASCADE
        );
    ''')
    if not conn.execute('SELECT * FROM users WHERE username = "grisho"').fetchone():
        conn.execute('INSERT INTO users (username, password, is_admin) VALUES (?, ?, ?)',
                     ('grisho', generate_password_hash('admin123'), 1))
    conn.commit()
    conn.close()

def get_thumbnail_path(photo_path):
    p = Path(photo_path)
    thumb_dir = Path('/photos/thumbnails')
    thumb_dir.mkdir(parents=True, exist_ok=True)
    return thumb_dir / f"{p.stem}_{abs(hash(photo_path))}.jpg"

def generate_thumbnail(photo_path):
    thumb_path = get_thumbnail_path(photo_path)
    if thumb_path.exists():
        return str(thumb_path)
    ext = Path(photo_path).suffix.lower()
    if ext in VIDEO_EXTENSIONS:
        return None
    try:
        with Image.open(photo_path) as img:
            img = ImageOps.exif_transpose(img)
            img.thumbnail(THUMB_SIZE)
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            img.save(str(thumb_path), 'JPEG', quality=75)
        return str(thumb_path)
    except Exception:
        return None

def sync_photos():
    cfg = load_config()
    sources = cfg.get('photo_sources', [])
    conn = get_db()
    for source in sources:
        if not os.path.isdir(source):
            continue
        for f in Path(source).iterdir():
            ext = f.suffix.lower()
            if ext in ALL_EXTENSIONS:
                media_type = 'video' if ext in VIDEO_EXTENSIONS else 'photo'
                stat = f.stat()
                conn.execute('''INSERT OR IGNORE INTO photos (path, filename, ctime, uploaded_by, media_type)
                                VALUES (?, ?, ?, ?, ?)''',
                             (str(f), f.name, stat.st_ctime, 'system', media_type))
    conn.commit()
    conn.close()

def get_photos(sort='newest', people=None, place=None, date_from=None,
               date_to=None, favorites_only=False, album_id=None, media_filter='all'):
    conn = get_db()
    query = '''SELECT DISTINCT p.*,
               GROUP_CONCAT(DISTINCT pp.person) as people_tags,
               GROUP_CONCAT(DISTINCT pl.place) as place_tags,
               EXISTS(SELECT 1 FROM favorites f WHERE f.photo_id = p.id AND f.user_id = ?) as is_favorite
               FROM photos p
               LEFT JOIN photo_people pp ON pp.photo_id = p.id
               LEFT JOIN photo_places pl ON pl.photo_id = p.id
               LEFT JOIN favorites fv ON fv.photo_id = p.id
               LEFT JOIN album_photos ap ON ap.photo_id = p.id
               WHERE 1=1'''
    params = [current_user.id]

    if people:
        placeholders = ','.join(['?' for _ in people])
        query += f''' AND p.id IN (
            SELECT photo_id FROM photo_people WHERE person IN ({placeholders})
            GROUP BY photo_id HAVING COUNT(DISTINCT person) = ?)'''
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

    if album_id:
        query += ' AND ap.album_id = ?'
        params.append(album_id)

    if media_filter == 'photos':
        query += " AND p.media_type = 'photo'"
    elif media_filter == 'videos':
        query += " AND p.media_type = 'video'"

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

def is_allowed_source(path):
    cfg = load_config()
    sources = cfg.get('photo_sources', [])
    upload_root = cfg.get('upload_root', '/photos/uploads')
    all_roots = sources + [upload_root, '/photos/thumbnails']
    return any(path.startswith(s) for s in all_roots)

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
    album_id = request.args.get('album_id', '')
    media_filter = request.args.get('media_filter', 'all')
    cfg = load_config()

    photos = get_photos(sort, people or None, place or None,
                        date_from or None, date_to or None,
                        favorites_only, int(album_id) if album_id else None,
                        media_filter)

    conn = get_db()
    places = [r[0] for r in conn.execute(
        'SELECT DISTINCT place FROM photo_places ORDER BY place').fetchall()]
    albums = conn.execute('SELECT * FROM albums ORDER BY created_at DESC').fetchall()
    conn.close()

    return render_template('index.html', photos=photos, sort=sort,
                           people_list=cfg['people'], places=places,
                           selected_people=people, selected_place=place,
                           date_from=date_from, date_to=date_to,
                           favorites_only=favorites_only, albums=albums,
                           selected_album=album_id, media_filter=media_filter)

@app.route('/thumb')
@login_required
def thumb():
    path = request.args.get('path')
    if not is_allowed_source(path):
        return 'Forbidden', 403
    ext = Path(path).suffix.lower()
    if ext in VIDEO_EXTENSIONS:
        return 'No thumbnail', 404
    thumb_path = generate_thumbnail(path)
    if thumb_path:
        return send_file(thumb_path, mimetype='image/jpeg')
    return send_file(path)

@app.route('/photo')
@login_required
def photo():
    path = request.args.get('path')
    if not is_allowed_source(path):
        return 'Forbidden', 403
    return send_file(path)

@app.route('/download')
@login_required
def download():
    path = request.args.get('path')
    if not is_allowed_source(path):
        return 'Forbidden', 403
    return send_file(path, as_attachment=True)

@app.route('/download-zip')
@login_required
def download_zip():
    sort = request.args.get('sort', 'newest')
    people = request.args.getlist('people')
    place = request.args.get('place', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    favorites_only = request.args.get('favorites') == '1'
    album_id = request.args.get('album_id', '')
    media_filter = request.args.get('media_filter', 'all')

    photos = get_photos(sort, people or None, place or None,
                        date_from or None, date_to or None,
                        favorites_only, int(album_id) if album_id else None,
                        media_filter)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for p in photos:
            if os.path.exists(p['path']):
                zf.write(p['path'], p['filename'])
    buf.seek(0)
    return send_file(buf, mimetype='application/zip',
                     as_attachment=True, download_name='gallery.zip')

@app.route('/tag/<int:photo_id>', methods=['POST'])
@login_required
def tag_photo(photo_id):
    people = request.form.getlist('people')
    place = request.form.get('place', '').strip()
    conn = get_db()
    conn.execute('DELETE FROM photo_people WHERE photo_id = ?', (photo_id,))
    conn.execute('DELETE FROM photo_places WHERE photo_id = ?', (photo_id,))
    for person in people:
        conn.execute('INSERT OR IGNORE INTO photo_people (photo_id, person) VALUES (?, ?)',
                     (photo_id, person))
    if place:
        conn.execute('INSERT OR IGNORE INTO photo_places (photo_id, place) VALUES (?, ?)',
                     (photo_id, place))
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
    conn = get_db()
    photo = conn.execute('SELECT * FROM photos WHERE id = ?', (photo_id,)).fetchone()
    if not photo:
        return redirect(url_for('index'))
    if not current_user.is_admin and photo['uploaded_by'] != current_user.username:
        flash('Permission denied')
        return redirect(url_for('index'))
    if os.path.exists(photo['path']):
        os.remove(photo['path'])
    thumb = get_thumbnail_path(photo['path'])
    if thumb.exists():
        thumb.unlink()
    conn.execute('DELETE FROM photos WHERE id = ?', (photo_id,))
    conn.commit()
    conn.close()
    return redirect(request.referrer or url_for('index'))

@app.route('/albums', methods=['GET', 'POST'])
@login_required
def albums():
    conn = get_db()
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'create':
            name = request.form.get('name', '').strip()
            desc = request.form.get('description', '').strip()
            if name:
                conn.execute('INSERT INTO albums (name, description, created_by, created_at) VALUES (?, ?, ?, ?)',
                             (name, desc, current_user.username, datetime.now().timestamp()))
                conn.commit()
                flash('Album created')
        elif action == 'delete':
            album_id = request.form.get('album_id')
            album = conn.execute('SELECT * FROM albums WHERE id = ?', (album_id,)).fetchone()
            if album and (current_user.is_admin or album['created_by'] == current_user.username):
                conn.execute('DELETE FROM albums WHERE id = ?', (album_id,))
                conn.commit()
                flash('Album deleted')
    all_albums = conn.execute(
        'SELECT a.*, COUNT(ap.photo_id) as photo_count FROM albums a LEFT JOIN album_photos ap ON ap.album_id = a.id GROUP BY a.id ORDER BY a.created_at DESC'
    ).fetchall()
    conn.close()
    return render_template('albums.html', albums=all_albums)

@app.route('/album/<int:album_id>/add', methods=['POST'])
@login_required
def add_to_album(album_id):
    photo_id = request.form.get('photo_id')
    conn = get_db()
    conn.execute('INSERT OR IGNORE INTO album_photos (album_id, photo_id) VALUES (?, ?)',
                 (album_id, photo_id))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})

@app.route('/album/<int:album_id>/remove', methods=['POST'])
@login_required
def remove_from_album(album_id):
    photo_id = request.form.get('photo_id')
    conn = get_db()
    conn.execute('DELETE FROM album_photos WHERE album_id = ? AND photo_id = ?',
                 (album_id, photo_id))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})

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
            if file and Path(file.filename).suffix.lower() in ALL_EXTENSIONS:
                filename = secure_filename(file.filename)
                dest = os.path.join(user_folder, filename)
                if os.path.exists(dest):
                    base, ext = os.path.splitext(filename)
                    filename = f"{base}_{int(datetime.now().timestamp())}{ext}"
                    dest = os.path.join(user_folder, filename)
                file.save(dest)
                ext = Path(dest).suffix.lower()
                media_type = 'video' if ext in VIDEO_EXTENSIONS else 'photo'
                stat = Path(dest).stat()
                conn = get_db()
                conn.execute('''INSERT OR IGNORE INTO photos (path, filename, ctime, uploaded_by, media_type)
                                VALUES (?, ?, ?, ?, ?)''',
                             (dest, filename, stat.st_ctime, current_user.username, media_type))
                conn.commit()
                conn.close()
                if media_type == 'photo':
                    generate_thumbnail(dest)
                uploaded += 1
        flash(f'{uploaded} file(s) uploaded successfully')
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
            conn.execute('DELETE FROM users WHERE id = ? AND is_admin = 0',
                         (request.form['user_id'],))
            conn.commit()
    users = conn.execute('SELECT * FROM users').fetchall()
    conn.close()
    return render_template('users.html', users=users)

@app.route('/admin/users/edit/<int:user_id>', methods=['GET', 'POST'])
@login_required
def edit_user(user_id):
    if not current_user.is_admin:
        return redirect(url_for('index'))
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    if not user:
        flash('User not found')
        return redirect(url_for('manage_users'))
    if request.method == 'POST':
        new_username = request.form.get('username').strip()
        new_password = request.form.get('password').strip()
        try:
            if new_password:
                conn.execute('UPDATE users SET username = ?, password = ? WHERE id = ?',
                             (new_username, generate_password_hash(new_password), user_id))
            else:
                conn.execute('UPDATE users SET username = ? WHERE id = ?',
                             (new_username, user_id))
            conn.commit()
            flash('User updated')
            return redirect(url_for('manage_users'))
        except:
            flash('Username already exists')
    conn.close()
    return render_template('edit_user.html', user=user)

# ── ADD THESE IMPORTS at the top of app.py (alongside existing imports) ──────
# import urllib.request
# import urllib.error
# import json as json_module  # only if 'json' not already imported

# ── ADD THESE ROUTES before the `if __name__ == '__main__':` line ─────────────

MCP_SERVER_URL = os.environ.get('MCP_SERVER_URL', 'http://mcp-server.mcp-server.svc.cluster.local:8000')
OLLAMA_URL     = os.environ.get('OLLAMA_URL',     'http://192.168.0.155:11434')  # your Windows PC IP
OLLAMA_MODEL   = os.environ.get('OLLAMA_MODEL',   'qwen2.5:14b')


def mcp_call(tool: str, params: dict = {}) -> str:
    """Call a tool on the MCP server and return the result string."""
    import urllib.request, urllib.error, json as _json
    payload = _json.dumps({"tool": tool, "parameters": params}).encode()
    req = urllib.request.Request(
        f"{MCP_SERVER_URL}/call",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = _json.loads(resp.read())
            return data.get("result", "No result")
    except urllib.error.URLError as e:
        return f"MCP ERROR: {e}"


def ollama_chat(messages: list) -> str:
    """Send messages to Ollama and return the assistant reply."""
    import urllib.request, urllib.error, json as _json
    payload = _json.dumps({
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": False
    }).encode()
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = _json.loads(resp.read())
            return data["message"]["content"]
    except urllib.error.URLError as e:
        return f"OLLAMA ERROR: {e}"


SYSTEM_PROMPT = """You are a Kubernetes cluster assistant with access to a live k3s cluster running on a Raspberry Pi.
You have already retrieved real-time data from the cluster tools. Use it to answer the user's question clearly and concisely.
Format tabular data as plain text tables. Highlight any unhealthy or concerning items.
Be direct and technical. You are talking to a senior DevOps/Platform Engineer."""


@app.route('/chat')
@login_required
def chat_page():
    return render_template('chat.html')


@app.route('/chat/health')
@login_required
def chat_health():
    import urllib.request, urllib.error
    mcp_ok, ollama_ok = False, False
    try:
        urllib.request.urlopen(f"{MCP_SERVER_URL}/health", timeout=3)
        mcp_ok = True
    except Exception:
        pass
    try:
        urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=3)
        ollama_ok = True
    except Exception:
        pass
    return jsonify({"mcp_ok": mcp_ok, "ollama_ok": ollama_ok})


@app.route('/chat', methods=['POST'])
@login_required
def chat_api():
    import json as _json
    data = request.get_json()
    user_message = data.get('message', '').strip()
    history      = data.get('history', [])

    if not user_message:
        return jsonify({"error": "Empty message"}), 400

    # ── Step 1: gather cluster context based on what the user is asking ──────
    context_parts = []
    try:
        msg_lower = user_message.lower()
        always_fetch = any(w in msg_lower for w in ['health', 'status', 'overview', 'cluster'])
        wants_pods   = any(w in msg_lower for w in ['pod', 'container', 'crash', 'fail', 'restart', 'running', 'deploy'])
        wants_nodes  = any(w in msg_lower for w in ['node', 'cpu', 'memory', 'resource', 'metric', 'usage'])
        wants_argo   = any(w in msg_lower for w in ['argo', 'sync', 'app', 'deploy', 'gitops'])
        wants_svc    = any(w in msg_lower for w in ['service', 'port', 'endpoint', 'svc'])
        wants_metrics= any(w in msg_lower for w in ['cpu', 'memory', 'metric', 'usage', 'resource', 'top'])
        if always_fetch or wants_pods or not any([wants_nodes, wants_argo, wants_svc, wants_metrics]):
            context_parts.append(("POD STATUS", mcp_call("get_pods")))
        if wants_nodes or always_fetch:
            context_parts.append(("NODE STATUS", mcp_call("get_nodes")))
        if wants_metrics or always_fetch:
            context_parts.append(("RESOURCE METRICS", mcp_call("get_metrics")))
        if wants_argo or always_fetch:
            context_parts.append(("ARGOCD APPLICATIONS", mcp_call("get_argocd_apps")))
        if wants_svc:
            context_parts.append(("SERVICES", mcp_call("get_services")))
    except Exception as e:
        context_parts = [("MCP STATUS", f"MCP server unavailable: {e} - answering without live cluster data")]

    # Check if user is asking about a specific pod
    # Simple heuristic: if message contains a known pod keyword + describe
    msg_lower = user_message.lower()
    if 'describe' in msg_lower or 'detail' in msg_lower or 'log' in msg_lower:
        # Try to extract pod name from message - grab anything after 'pod ' or 'describe '
        words = user_message.split()
        for i, w in enumerate(words):
            if w.lower() in ('pod', 'describe') and i + 1 < len(words):
                pod_name = words[i + 1]
                ns = 'default'
                if 'argocd' in msg_lower:
                    ns = 'argocd'
                elif 'kube' in msg_lower:
                    ns = 'kube-system'
                context_parts.append((f"POD DETAIL: {pod_name}", mcp_call("describe_pod", {"name": pod_name, "namespace": ns})))
                break

    # ── Step 2: build context string ─────────────────────────────────────────
    context_str = ""
    for label, result in context_parts:
        context_str += f"\n\n=== {label} ===\n{result}"

    # ── Step 3: build messages for Ollama ────────────────────────────────────
    system_with_context = SYSTEM_PROMPT
    if context_str:
        system_with_context += f"\n\nCURRENT CLUSTER DATA (fetched live):{context_str}"

    messages = [{"role": "system", "content": system_with_context}]

    # Add conversation history (last 6 turns)
    for h in history[-6:]:
        if h.get("role") in ("user", "assistant"):
            messages.append({"role": h["role"], "content": h["content"]})

    # Add current user message
    messages.append({"role": "user", "content": user_message})

    # ── Step 4: call Ollama ───────────────────────────────────────────────────
    reply = ollama_chat(messages)

    if reply.startswith("OLLAMA ERROR"):
        return jsonify({"error": reply}), 502

    return jsonify({"response": reply})

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000)
