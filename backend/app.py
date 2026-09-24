import os
import sqlite3
import uuid
from datetime import datetime, timezone, timedelta
from functools import wraps

import jwt
from flask import Flask, jsonify, request, g, send_from_directory
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DATABASE_PATH", os.path.abspath(os.path.join(BASE_DIR, '..', 'database', 'qr_dekal.db')))
SECRET_KEY = os.environ.get("SECRET_KEY", "change-this-secret-in-production")
UPLOAD_DIR = os.environ.get("UPLOAD_DIR", os.path.abspath(os.path.join(BASE_DIR, '..', 'uploads', 'ads')))
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif", "mp4", "webm", "mov", "m4v"}
IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}
VIDEO_EXTENSIONS = {"mp4", "webm", "mov", "m4v"}

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}, r"/media/*": {"origins": "*"}}, allow_headers=["Content-Type", "Authorization"])
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024


def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_error=None):
    conn = g.pop("db", None)
    if conn:
        conn.close()


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS admins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_code TEXT NOT NULL UNIQUE,
        first_seen TEXT NOT NULL,
        last_seen TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS qr_generations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_code TEXT NOT NULL,
        content TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY(user_code) REFERENCES users(user_code) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS ads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        media_url TEXT,
        media_type TEXT NOT NULL DEFAULT 'image',
        target_url TEXT,
        start_at TEXT,
        end_at TEXT,
        active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_users_last_seen ON users(last_seen);
    CREATE INDEX IF NOT EXISTS idx_qr_created_at ON qr_generations(created_at);
    """)
    # Upgrade old databases that used image_url only.
    columns = {r[1] for r in conn.execute("PRAGMA table_info(ads)").fetchall()}
    if "media_url" not in columns:
        conn.execute("ALTER TABLE ads ADD COLUMN media_url TEXT")
        if "image_url" in columns:
            conn.execute("UPDATE ads SET media_url=image_url WHERE media_url IS NULL")
    if "media_type" not in columns:
        conn.execute("ALTER TABLE ads ADD COLUMN media_type TEXT NOT NULL DEFAULT 'image'")
    conn.commit()
    conn.close()


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def user_code():
    return "USER-" + uuid.uuid4().hex[:8].upper()


def token_for(admin_id, username):
    payload = {
        "sub": str(admin_id),
        "username": username,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(days=7),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def admin_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return jsonify({"error": "Authentification requise."}), 401
        raw = header.split(" ", 1)[1].strip()
        try:
            payload = jwt.decode(raw, SECRET_KEY, algorithms=["HS256"])
            admin_id = payload.get("sub")
            if not admin_id:
                raise jwt.InvalidTokenError("sub manquant")
            row = db().execute("SELECT id, username FROM admins WHERE id=?", (int(admin_id),)).fetchone()
            if not row:
                return jsonify({"error": "Administrateur introuvable."}), 401
            g.admin = {"id": row["id"], "username": row["username"]}
        except (jwt.PyJWTError, ValueError, TypeError):
            return jsonify({"error": "Session administrateur invalide ou expirée."}), 401
        return fn(*args, **kwargs)
    return wrapped


@app.get("/api/health")
def health():
    return jsonify({"status": "ok", "service": "QR DEKAL API"})


@app.get("/api/setup/status")
def setup_status():
    row = db().execute("SELECT COUNT(*) AS n FROM admins").fetchone()
    return jsonify({"admin_exists": row["n"] > 0})


@app.post("/api/setup/admin")
def setup_admin():
    conn = db()
    if conn.execute("SELECT 1 FROM admins LIMIT 1").fetchone():
        return jsonify({"error": "Un administrateur existe déjà."}), 409
    data = request.get_json(silent=True) or {}
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))
    if len(username) < 3 or len(password) < 8:
        return jsonify({"error": "Le nom doit contenir au moins 3 caractères et le mot de passe au moins 8 caractères."}), 400
    conn.execute("INSERT INTO admins(username,password_hash,created_at) VALUES(?,?,?)", (username, generate_password_hash(password), now_iso()))
    conn.commit()
    return jsonify({"message": "Administrateur créé. Vous pouvez maintenant vous connecter."}), 201


@app.post("/api/admin/login")
def login():
    data = request.get_json(silent=True) or {}
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))
    row = db().execute("SELECT * FROM admins WHERE username = ?", (username,)).fetchone()
    if not row or not check_password_hash(row["password_hash"], password):
        return jsonify({"error": "Nom ou mot de passe incorrect."}), 401
    token = token_for(row["id"], row["username"])
    return jsonify({"token": token, "username": row["username"]})


@app.get("/api/admin/me")
@admin_required
def admin_me():
    return jsonify({"authenticated": True, "username": g.admin["username"]})


@app.post("/api/users/register")
def register_user():
    data = request.get_json(silent=True) or {}
    code = str(data.get("user_code", "")).strip()
    conn = db()
    now = now_iso()
    if not code:
        code = user_code()
        conn.execute("INSERT INTO users(user_code,first_seen,last_seen) VALUES(?,?,?)", (code, now, now))
    else:
        row = conn.execute("SELECT id FROM users WHERE user_code = ?", (code,)).fetchone()
        if row:
            conn.execute("UPDATE users SET last_seen=? WHERE user_code=?", (now, code))
        else:
            conn.execute("INSERT INTO users(user_code,first_seen,last_seen) VALUES(?,?,?)", (code, now, now))
    conn.commit()
    return jsonify({"user_code": code})


@app.post("/api/users/heartbeat")
def heartbeat():
    data = request.get_json(silent=True) or {}
    code = str(data.get("user_code", "")).strip()
    if not code:
        return jsonify({"error": "user_code requis."}), 400
    db().execute("UPDATE users SET last_seen=? WHERE user_code=?", (now_iso(), code))
    db().commit()
    return jsonify({"ok": True})


@app.post("/api/qr/generate")
def record_qr():
    data = request.get_json(silent=True) or {}
    code = str(data.get("user_code", "")).strip()
    content = str(data.get("content", "")).strip()
    if not code or not content:
        return jsonify({"error": "user_code et content sont requis."}), 400
    conn = db()
    if not conn.execute("SELECT 1 FROM users WHERE user_code=?", (code,)).fetchone():
        return jsonify({"error": "Utilisateur inconnu."}), 404
    conn.execute("INSERT INTO qr_generations(user_code,content,created_at) VALUES(?,?,?)", (code, content, now_iso()))
    conn.execute("UPDATE users SET last_seen=? WHERE user_code=?", (now_iso(), code))
    conn.commit()
    return jsonify({"ok": True})


def ad_dict(row):
    d = dict(row)
    if d.get("media_url") is None and "image_url" in d:
        d["media_url"] = d.get("image_url")
    d.pop("image_url", None)
    return d


@app.get("/api/public/ads")
def public_ads():
    now = now_iso()
    rows = db().execute("SELECT * FROM ads WHERE active=1 AND (start_at IS NULL OR start_at='' OR start_at<=?) AND (end_at IS NULL OR end_at='' OR end_at>=?) ORDER BY id DESC", (now, now)).fetchall()
    response = jsonify({"ads": [ad_dict(r) for r in rows], "count": len(rows)})
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return response


@app.get("/media/ads/<path:filename>")
def ad_media(filename):
    response = send_from_directory(UPLOAD_DIR, filename, max_age=0)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return response


@app.get("/api/admin/stats")
@admin_required
def stats():
    conn = db()
    total_users = conn.execute("SELECT COUNT(*) n FROM users").fetchone()["n"]
    since = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    active_users = conn.execute("SELECT COUNT(*) n FROM users WHERE last_seen >= ?", (since,)).fetchone()["n"]
    total_qr = conn.execute("SELECT COUNT(*) n FROM qr_generations").fetchone()["n"]
    rows = conn.execute("SELECT substr(created_at,1,10) day, COUNT(*) count FROM qr_generations WHERE created_at >= ? GROUP BY day ORDER BY day ASC", ((datetime.now(timezone.utc) - timedelta(days=30)).isoformat(),)).fetchall()
    return jsonify({"total_users": total_users, "active_users": active_users, "total_qr": total_qr, "daily_qr": [dict(r) for r in rows]})


@app.get("/api/admin/users")
@admin_required
def admin_users():
    rows = db().execute("SELECT user_code,first_seen,last_seen FROM users ORDER BY last_seen DESC LIMIT 500").fetchall()
    return jsonify({"users": [dict(r) for r in rows]})


@app.get("/api/admin/qr")
@admin_required
def admin_qr():
    rows = db().execute("SELECT id,user_code,content,created_at FROM qr_generations ORDER BY id DESC LIMIT 500").fetchall()
    return jsonify({"qr_codes": [dict(r) for r in rows]})


@app.route("/api/admin/ads", methods=["GET", "POST"])
@admin_required
def admin_ads():
    conn = db()
    if request.method == "GET":
        rows = conn.execute("SELECT * FROM ads ORDER BY id DESC").fetchall()
        return jsonify({"ads": [ad_dict(r) for r in rows]})

    title = str(request.form.get("title", "")).strip()
    target_url = str(request.form.get("target_url", "")).strip() or None
    start_at = str(request.form.get("start_at", "")).strip() or None
    end_at = str(request.form.get("end_at", "")).strip() or None
    active = 1 if request.form.get("active", "1") == "1" else 0
    media = request.files.get("media")
    if not title:
        return jsonify({"error": "Le titre est requis."}), 400
    if not media or not media.filename:
        return jsonify({"error": "Choisissez une image ou une vidéo."}), 400
    ext = media.filename.rsplit(".", 1)[-1].lower() if "." in media.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({"error": "Format non autorisé. Images: PNG/JPG/JPEG/WEBP/GIF. Vidéos: MP4/WEBM/MOV/M4V."}), 400
    media_type = "video" if ext in VIDEO_EXTENSIONS else "image"
    filename = f"{uuid.uuid4().hex}.{ext}"
    media.save(os.path.join(UPLOAD_DIR, secure_filename(filename)))
    media_url = f"/media/ads/{filename}"
    now = now_iso()
    cur = conn.execute("INSERT INTO ads(title,media_url,media_type,target_url,start_at,end_at,active,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)", (title, media_url, media_type, target_url, start_at, end_at, active, now, now))
    conn.commit()
    return jsonify({"id": cur.lastrowid, "media_url": media_url, "media_type": media_type}), 201


@app.put("/api/admin/ads/<int:ad_id>")
@admin_required
def update_ad(ad_id):
    data = request.get_json(silent=True) or {}
    conn = db()
    existing = conn.execute("SELECT * FROM ads WHERE id=?", (ad_id,)).fetchone()
    if not existing:
        return jsonify({"error": "Publicité introuvable."}), 404
    fields = {
        "title": str(data.get("title", existing["title"])).strip(),
        "media_url": data.get("media_url", existing["media_url"]),
        "media_type": data.get("media_type", existing["media_type"]),
        "target_url": data.get("target_url", existing["target_url"]),
        "start_at": data.get("start_at", existing["start_at"]),
        "end_at": data.get("end_at", existing["end_at"]),
        "active": 1 if data.get("active", bool(existing["active"])) else 0,
    }
    conn.execute("UPDATE ads SET title=?,media_url=?,media_type=?,target_url=?,start_at=?,end_at=?,active=?,updated_at=? WHERE id=?", (*fields.values(), now_iso(), ad_id))
    conn.commit()
    return jsonify({"ok": True})


@app.delete("/api/admin/ads/<int:ad_id>")
@admin_required
def delete_ad(ad_id):
    conn = db()
    row = conn.execute("SELECT media_url FROM ads WHERE id=?", (ad_id,)).fetchone()
    if row and row["media_url"] and row["media_url"].startswith("/media/ads/"):
        try:
            os.remove(os.path.join(UPLOAD_DIR, os.path.basename(row["media_url"])))
        except FileNotFoundError:
            pass
    conn.execute("DELETE FROM ads WHERE id=?", (ad_id,))
    conn.commit()
    return jsonify({"ok": True})


@app.errorhandler(413)
def too_large(_e):
    return jsonify({"error": "Fichier trop volumineux. Limite: 100 Mo."}), 413


@app.errorhandler(404)
def not_found(_e):
    return jsonify({"error": "Route introuvable."}), 404


init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
