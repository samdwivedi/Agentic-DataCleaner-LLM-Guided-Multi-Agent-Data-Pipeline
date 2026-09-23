"""
AI Research Agent — Flask Application
──────────────────────────────────────
A multi-page Flask web application with:
  • User authentication (register / login / logout)
  • Search functionality
  • Shared search history across users
  • User profile page
"""

import os
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from functools import wraps

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    g,
    jsonify,
)
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from ddgs import DDGS

# ── Load environment ──────────────────────────────────────────────────────────
load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env", override=True)

# ── App setup ─────────────────────────────────────────────────────────────────
app = Flask(
    __name__,
    template_folder="templates",
    static_folder="static",
)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "super-secret-dev-key-change-me")
app.config["DATABASE"] = str(
    Path(__file__).resolve().parent / "data" / "flask_app.db"
)

# ── Database helpers ──────────────────────────────────────────────────────────

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id          TEXT PRIMARY KEY,
    username    TEXT UNIQUE NOT NULL,
    email       TEXT UNIQUE NOT NULL,
    password    TEXT NOT NULL,
    avatar_seed TEXT NOT NULL,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS search_history (
    id          TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL REFERENCES users(id),
    query       TEXT NOT NULL,
    result_count INTEGER DEFAULT 0,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS search_results (
    id          TEXT PRIMARY KEY,
    search_id   TEXT NOT NULL REFERENCES search_history(id),
    title       TEXT NOT NULL,
    snippet     TEXT,
    url         TEXT,
    position    INTEGER DEFAULT 0
);
"""


def get_db() -> sqlite3.Connection:
    """Return a per-request database connection."""
    if "db" not in g:
        db_path = app.config["DATABASE"]
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        g.db = sqlite3.connect(db_path)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA journal_mode=WAL")
        g.db.execute("PRAGMA foreign_keys=ON")
    return g.db


@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Initialise tables on first run."""
    with app.app_context():
        db = get_db()
        db.executescript(SCHEMA_SQL)
        db.commit()


# ── Auth decorator ────────────────────────────────────────────────────────────

def login_required(f):
    """Redirect to login page when not authenticated."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


# ── Context processor (make user available in every template) ─────────────────

@app.context_processor
def inject_user():
    user = None
    if "user_id" in session:
        db = get_db()
        row = db.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()
        if row:
            user = dict(row)
    return {"current_user": user}


# ══════════════════════════════════════════════════════════════════════════════
#  ROUTES
# ══════════════════════════════════════════════════════════════════════════════

# ── Landing / Home ────────────────────────────────────────────────────────────

@app.route("/")
def home():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return render_template("home.html")


# ── Register ──────────────────────────────────────────────────────────────────

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        errors = []
        if not username or len(username) < 3:
            errors.append("Username must be at least 3 characters.")
        if not email or "@" not in email:
            errors.append("Enter a valid email address.")
        if len(password) < 6:
            errors.append("Password must be at least 6 characters.")
        if password != confirm:
            errors.append("Passwords do not match.")

        db = get_db()
        if db.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone():
            errors.append("Username is already taken.")
        if db.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone():
            errors.append("Email is already registered.")

        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("register.html", username=username, email=email)

        user_id = str(uuid.uuid4())
        avatar_seed = username  # used for DiceBear avatar
        now = datetime.utcnow().isoformat()
        db.execute(
            "INSERT INTO users (id, username, email, password, avatar_seed, created_at) VALUES (?,?,?,?,?,?)",
            (user_id, username, email, generate_password_hash(password), avatar_seed, now),
        )
        db.commit()

        session["user_id"] = user_id
        flash("Account created! Welcome aboard 🚀", "success")
        return redirect(url_for("dashboard"))

    return render_template("register.html")


# ── Login ─────────────────────────────────────────────────────────────────────

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip()
        password = request.form.get("password", "")

        db = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE username = ? OR email = ?",
            (identifier, identifier.lower()),
        ).fetchone()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            flash(f"Welcome back, {user['username']}!", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid credentials. Please try again.", "danger")
            return render_template("login.html", identifier=identifier)

    return render_template("login.html")


# ── Logout ────────────────────────────────────────────────────────────────────

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("home"))


# ── Dashboard (search page) ──────────────────────────────────────────────────

@app.route("/dashboard")
@login_required
def dashboard():
    db = get_db()
    # Recent searches by current user
    my_recent = db.execute(
        "SELECT * FROM search_history WHERE user_id = ? ORDER BY created_at DESC LIMIT 5",
        (session["user_id"],),
    ).fetchall()

    # Stats
    total_searches = db.execute(
        "SELECT COUNT(*) as c FROM search_history WHERE user_id = ?", (session["user_id"],)
    ).fetchone()["c"]
    total_users = db.execute("SELECT COUNT(*) as c FROM users").fetchone()["c"]
    global_searches = db.execute("SELECT COUNT(*) as c FROM search_history").fetchone()["c"]

    return render_template(
        "dashboard.html",
        recent_searches=[dict(r) for r in my_recent],
        total_searches=total_searches,
        total_users=total_users,
        global_searches=global_searches,
    )


# ── Perform Search ────────────────────────────────────────────────────────────

@app.route("/search", methods=["POST"])
@login_required
def search():
    query = request.form.get("query", "").strip()
    if not query:
        flash("Enter a search query.", "warning")
        return redirect(url_for("dashboard"))

    db = get_db()
    search_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    # Simulated search results (replace with real API later)
    simulated_results = _real_search(query)

    db.execute(
        "INSERT INTO search_history (id, user_id, query, result_count, created_at) VALUES (?,?,?,?,?)",
        (search_id, session["user_id"], query, len(simulated_results), now),
    )
    for idx, res in enumerate(simulated_results):
        db.execute(
            "INSERT INTO search_results (id, search_id, title, snippet, url, position) VALUES (?,?,?,?,?,?)",
            (str(uuid.uuid4()), search_id, res["title"], res["snippet"], res["url"], idx),
        )
    db.commit()

    return render_template(
        "search_results.html",
        query=query,
        results=simulated_results,
        search_id=search_id,
    )


def _real_search(query: str) -> list[dict]:
    """Search DuckDuckGo and return real results with working links."""
    try:
        with DDGS() as ddgs:
            raw = list(ddgs.text(query, max_results=8))
        results = []
        for r in raw:
            results.append({
                "title": r.get("title", "Untitled"),
                "snippet": r.get("body", ""),
                "url": r.get("href", "#"),
            })
        return results if results else _fallback_results(query)
    except Exception as e:
        print(f"DuckDuckGo search error: {e}")
        return _fallback_results(query)


def _fallback_results(query: str) -> list[dict]:
    """Fallback if the live search fails."""
    return [
        {
            "title": f"{query} — Google Search",
            "snippet": f"Search Google for more results on '{query}'.",
            "url": f"https://www.google.com/search?q={query.replace(' ', '+')}",
        },
        {
            "title": f"{query} — Wikipedia",
            "snippet": f"Look up '{query}' on Wikipedia.",
            "url": f"https://en.wikipedia.org/w/index.php?search={query.replace(' ', '+')}",
        },
    ]


# ── Search History (shared) ───────────────────────────────────────────────────

@app.route("/history")
@login_required
def history():
    db = get_db()
    page = request.args.get("page", 1, type=int)
    per_page = 15
    filter_user = request.args.get("user", "all")

    if filter_user == "me":
        rows = db.execute(
            """SELECT sh.*, u.username, u.avatar_seed
               FROM search_history sh
               JOIN users u ON sh.user_id = u.id
               WHERE sh.user_id = ?
               ORDER BY sh.created_at DESC
               LIMIT ? OFFSET ?""",
            (session["user_id"], per_page, (page - 1) * per_page),
        ).fetchall()
        total = db.execute(
            "SELECT COUNT(*) as c FROM search_history WHERE user_id = ?",
            (session["user_id"],),
        ).fetchone()["c"]
    else:
        rows = db.execute(
            """SELECT sh.*, u.username, u.avatar_seed
               FROM search_history sh
               JOIN users u ON sh.user_id = u.id
               ORDER BY sh.created_at DESC
               LIMIT ? OFFSET ?""",
            (per_page, (page - 1) * per_page),
        ).fetchall()
        total = db.execute("SELECT COUNT(*) as c FROM search_history").fetchone()["c"]

    total_pages = max(1, (total + per_page - 1) // per_page)

    return render_template(
        "history.html",
        searches=[dict(r) for r in rows],
        page=page,
        total_pages=total_pages,
        filter_user=filter_user,
        total=total,
    )


# ── Search Detail ─────────────────────────────────────────────────────────────

@app.route("/history/<search_id>")
@login_required
def search_detail(search_id):
    db = get_db()
    search = db.execute(
        """SELECT sh.*, u.username
           FROM search_history sh
           JOIN users u ON sh.user_id = u.id
           WHERE sh.id = ?""",
        (search_id,),
    ).fetchone()
    if not search:
        flash("Search not found.", "danger")
        return redirect(url_for("history"))

    results = db.execute(
        "SELECT * FROM search_results WHERE search_id = ? ORDER BY position",
        (search_id,),
    ).fetchall()

    return render_template(
        "search_detail.html",
        search=dict(search),
        results=[dict(r) for r in results],
    )


# ── Profile ───────────────────────────────────────────────────────────────────

@app.route("/profile")
@login_required
def profile():
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    total_searches = db.execute(
        "SELECT COUNT(*) as c FROM search_history WHERE user_id = ?",
        (session["user_id"],),
    ).fetchone()["c"]

    recent = db.execute(
        "SELECT * FROM search_history WHERE user_id = ? ORDER BY created_at DESC LIMIT 10",
        (session["user_id"],),
    ).fetchall()

    return render_template(
        "profile.html",
        user=dict(user),
        total_searches=total_searches,
        recent_searches=[dict(r) for r in recent],
    )


# ── API: Delete search ───────────────────────────────────────────────────────

@app.route("/api/search/<search_id>", methods=["DELETE"])
@login_required
def delete_search(search_id):
    db = get_db()
    search = db.execute(
        "SELECT * FROM search_history WHERE id = ? AND user_id = ?",
        (search_id, session["user_id"]),
    ).fetchone()
    if not search:
        return jsonify({"error": "Not found"}), 404

    db.execute("DELETE FROM search_results WHERE search_id = ?", (search_id,))
    db.execute("DELETE FROM search_history WHERE id = ?", (search_id,))
    db.commit()
    return jsonify({"success": True})


# ══════════════════════════════════════════════════════════════════════════════
#  Bootstrap
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    init_db()
    app.run(debug=True, host="0.0.0.0", port=5000)
