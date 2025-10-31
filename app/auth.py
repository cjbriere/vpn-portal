# app/auth.py
from flask import Blueprint, render_template, request, redirect, url_for, session
from werkzeug.security import check_password_hash

# Import the project's db module; we'll fall back to DATABASE_URL if needed.
from . import db as db

# --- Fallback connector (DATABASE_URL -> PyMySQL) ---
import os
from urllib.parse import urlparse, unquote
import pymysql
from pymysql.cursors import DictCursor

bp = Blueprint("auth", __name__)

def _conn():
    """
    Prefer a connection from app.db; otherwise open one from DATABASE_URL.
    Supported app.db exports (in order): get_db(), connect(), connect_db(), db() (callable), connection (handle).
    Fallback: parse DATABASE_URL (mysql+pymysql://user:pass@host:port/db).
    """
    # Try project-provided helpers first
    if hasattr(db, "get_db"):
        return db.get_db()
    if hasattr(db, "connect"):
        return db.connect()
    if hasattr(db, "connect_db"):
        return db.connect_db()
    if hasattr(db, "db") and callable(getattr(db, "db")):
        return db.db()
    if hasattr(db, "connection"):
        return getattr(db, "connection")

    # Fallback via env
    dsn = os.getenv("DATABASE_URL", "").strip()
    if not dsn:
        raise RuntimeError(
            "No database connector found in app.db and DATABASE_URL is not set."
        )

    # Accept mysql:// or mysql+pymysql://
    u = urlparse(dsn)
    if u.scheme not in ("mysql", "mysql+pymysql"):
        raise RuntimeError(f"Unsupported DATABASE_URL scheme: {u.scheme}")

    user = unquote(u.username or "")
    pwd = unquote(u.password or "")
    host = u.hostname or "localhost"
    port = u.port or 3306
    dbname = (u.path or "/").lstrip("/") or None

    return pymysql.connect(
        host=host,
        port=port,
        user=user,
        password=pwd,
        database=dbname,
        charset="utf8mb4",
        cursorclass=DictCursor,
        autocommit=False,
    )

@bp.route("/login", methods=["GET", "POST"])
def login():
    # GET: render placeholder login page (in repo)
    if request.method == "GET":
        return render_template("login.html", title="CITS VPN Portal — Login")

    # POST: verify username/password
    username = (request.form.get("username") or "").strip()
    password = request.form.get("password") or ""

    if not username or not password:
        return render_template(
            "login.html",
            title="CITS VPN Portal — Login",
            error="Invalid username or password.",
        ), 400

    conn = _conn()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, username, password_hash, mfa_enabled, totp_secret "
            "FROM users WHERE username=%s",
            (username,),
        )
        user = cur.fetchone()

    if not user or not check_password_hash(user["password_hash"], password):
        # Generic message to avoid account enumeration
        return render_template(
            "login.html",
            title="CITS VPN Portal — Login",
            error="Invalid username or password.",
        ), 401

    # Stage user for MFA; final session promotion happens after MFA pass
    session.pop("user_id", None)
    session["pending_user_id"] = user["id"]

    # Policy: always send to /mfa next (verify or setup), then we redirect to web.home
    return redirect(url_for("mfa.mfa"))

@bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
