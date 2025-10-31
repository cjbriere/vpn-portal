# app/mfa.py
from flask import Blueprint, render_template, request, redirect, url_for, session, abort, send_file, Response
from io import BytesIO
import time

from .totp import generate_base32_secret, verify_totp, build_otpauth_uri
from . import db as db  # import module; we add the same fallback as auth.py

# --- Fallback connector (DATABASE_URL -> PyMySQL) ---
import os
from urllib.parse import urlparse, unquote
import pymysql
from pymysql.cursors import DictCursor

bp = Blueprint("mfa", __name__)

# Simple per-session attempt throttling
MAX_ATTEMPTS_WINDOW = 5   # attempts
WINDOW_SECONDS = 300      # 5 minutes

def _conn():
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

def _rate_check():
    now = int(time.time())
    bucket = session.get("mfa_attempt_bucket", {"t": now, "n": 0})
    if now - bucket.get("t", now) > WINDOW_SECONDS:
        bucket = {"t": now, "n": 0}
    bucket["n"] = int(bucket.get("n", 0)) + 1
    session["mfa_attempt_bucket"] = bucket
    session.modified = True
    return bucket["n"] <= MAX_ATTEMPTS_WINDOW

def _require_pending_login():
    return "pending_user_id" in session

def _fetch_user(uid):
    conn = _conn()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, username, email, mfa_enabled, totp_secret "
            "FROM users WHERE id=%s",
            (uid,),
        )
        row = cur.fetchone()
    return row

def _update_user_secret(uid, secret, enable=False):
    conn = _conn()
    with conn.cursor() as cur:
        if enable:
            cur.execute(
                "UPDATE users SET totp_secret=%s, mfa_enabled=1 WHERE id=%s",
                (secret, uid),
            )
        else:
            cur.execute(
                "UPDATE users SET totp_secret=%s WHERE id=%s",
                (secret, uid),
            )
    conn.commit()

def _disable_mfa(uid):
    conn = _conn()
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE users SET mfa_enabled=0, totp_secret=NULL WHERE id=%s",
            (uid,),
        )
    conn.commit()

def _finalize_login(uid):
    session["user_id"] = uid
    session.pop("pending_user_id", None)
    return redirect(url_for("web.home"))

@bp.route("/mfa", methods=["GET", "POST"])
def mfa():
    if not _require_pending_login():
        return redirect(url_for("auth.login"))

    uid = session["pending_user_id"]
    user = _fetch_user(uid)
    if not user:
        return redirect(url_for("auth.login"))

    issuer = "CITS VPN Portal"
    account_label = user.get("username") or user.get("email") or f"user{user['id']}@vpn.c-itsolutions.com"

    if request.method == "GET":
        if user["mfa_enabled"] and user.get("totp_secret"):
            return render_template("mfa_verify.html", title="CITS VPN Portal — MFA", username=user["username"])
        else:
            # Ensure a secret exists (do NOT log secrets)
            secret = user.get("totp_secret")
            if not secret:
                secret = generate_base32_secret()
                _update_user_secret(uid, secret, enable=False)
            otpauth_uri = build_otpauth_uri(secret, account_label, issuer)
            return render_template("mfa_setup.html", title="CITS VPN Portal — MFA Setup",
                                   username=user["username"], secret=secret, otpauth_uri=otpauth_uri)

    # POST: verify code for setup or verify
    if not _rate_check():
        return render_template("mfa_verify.html", title="CITS VPN Portal — MFA",
                               username=user["username"],
                               error="Too many attempts. Please wait a few minutes and try again."), 429

    code = (request.form.get("code") or "").strip().replace(" ", "")
    if not code:
        if user["mfa_enabled"]:
            return render_template("mfa_verify.html", title="CITS VPN Portal — MFA",
                                   username=user["username"], error="Invalid code."), 400
        else:
            return render_template("mfa_setup.html", title="CITS VPN Portal — MFA Setup",
                                   username=user["username"], error="Invalid code."), 400

    secret = user.get("totp_secret")
    if not secret:
        secret = generate_base32_secret()
        _update_user_secret(uid, secret, enable=False)

    ok = verify_totp(secret, code, window=1)  # tolerate +/-1 step drift
    if not ok:
        if user["mfa_enabled"]:
            return render_template("mfa_verify.html", title="CITS VPN Portal — MFA",
                                   username=user["username"], error="Invalid code."), 401
        else:
            return render_template("mfa_setup.html", title="CITS VPN Portal — MFA Setup",
                                   username=user["username"], error="Invalid code."), 401

    if not user["mfa_enabled"]:
        _update_user_secret(uid, secret, enable=True)

    return _finalize_login(uid)

@bp.route("/mfa/qr.png")
def mfa_qr_png():
    if not _require_pending_login():
        return redirect(url_for("auth.login"))
    uid = session["pending_user_id"]
    user = _fetch_user(uid)
    if not user:
        return redirect(url_for("auth.login"))

    issuer = "CITS VPN Portal"
    account_label = user.get("username") or user.get("email") or f"user{user['id']}@vpn.c-itsolutions.com"
    secret = user.get("totp_secret")
    if not secret:
        abort(404)
    uri = build_otpauth_uri(secret, account_label, issuer)

    try:
        import qrcode  # optional dependency
        img = qrcode.make(uri)
        buf = BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return send_file(buf, mimetype="image/png", max_age=0)
    except Exception:
        # Fallback: return otpauth:// URI as plain text (mobile copy/tap)
        return Response(uri, mimetype="text/plain")

@bp.route("/mfa/disable", methods=["POST"])
def mfa_disable():
    current_uid = session.get("user_id")
    if not current_uid:
        return redirect(url_for("auth.login"))

    target_uid = request.form.get("user_id")
    if target_uid and str(target_uid) != str(current_uid):
        abort(403)

    _disable_mfa(current_uid)
    return redirect(url_for("web.home"))
