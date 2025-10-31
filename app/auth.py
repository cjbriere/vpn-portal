import os, secrets, time, datetime, bcrypt, base64, io, json, pyotp, qrcode, pymysql, logging
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from flask import Blueprint, request, render_template, redirect, url_for, make_response, current_app, g
from .db import get_conn

bp = Blueprint("auth", __name__)
COOKIE_NAME = "vpnsess"
MFA_COOKIE = "vpnmfa"
ISSUER = "CITS VPN Portal"
log = logging.getLogger(__name__)

def _policy_defaults():
    idle  = int(os.getenv("SESSION_IDLE_SECONDS", "1500"))
    abs_  = int(os.getenv("SESSION_ABSOLUTE_SECONDS", "1800"))
    grace = int(os.getenv("SESSION_GRACE_SECONDS", "300"))
    return idle, abs_, grace

def _get_lockout_policy(conn):
    with conn.cursor(cursor=pymysql.cursors.DictCursor) as cur:
        cur.execute("SELECT v FROM settings WHERE k='lockout_policy'")
        row = cur.fetchone()
    policy = {"window_minutes": 15, "max_attempts": 5, "lock_minutes": 15}
    if row and row.get("v"):
        try: policy.update(json.loads(row["v"]))
        except Exception as e: log.warning("lockout_policy JSON parse error: %s", e)
    return policy

def _record_login_event(conn, user_id, username_attempted, success, reason, ip, ua):
    with conn.cursor(cursor=pymysql.cursors.DictCursor) as cur:
        cur.execute(
            "INSERT INTO login_events (user_id, username_attempted, success, reason, ip_address, user_agent) "
            "VALUES (%s,%s,%s,%s,%s,%s)",
            (user_id, username_attempted, 1 if success else 0, reason, ip, (ua or "")[:255])
        )

def _is_locked(conn, username, policy):
    with conn.cursor(cursor=pymysql.cursors.DictCursor) as cur:
        cur.execute(
            "SELECT COUNT(*) AS n FROM login_events "
            "WHERE username_attempted=%s AND success=0 AND created_at > NOW() - INTERVAL %s MINUTE",
            (username, int(policy["window_minutes"]))
        )
        n = (cur.fetchone() or {}).get("n", 0)
        cur.execute(
            "SELECT created_at FROM login_events "
            "WHERE username_attempted=%s AND success=0 ORDER BY created_at DESC LIMIT 1",
            (username,)
        )
        last_fail = cur.fetchone()
    return bool(n >= int(policy["max_attempts"]) and last_fail)

def _lock_until_text(conn, username, lock_minutes):
    with conn.cursor(cursor=pymysql.cursors.DictCursor) as cur:
        cur.execute(
            "SELECT created_at FROM login_events "
            "WHERE username_attempted=%s AND success=0 ORDER BY created_at DESC LIMIT 1",
            (username,)
        )
        row = cur.fetchone()
    if not row: return None
    until = row["created_at"] + datetime.timedelta(minutes=int(lock_minutes))
    return until.strftime("%Y-%m-%d %H:%M:%S")

def _create_session(conn, user_id, idle_seconds, absolute_seconds, ip, ua):
    sid = secrets.token_hex(32)
    now = datetime.datetime.utcnow()
    expires = now + datetime.timedelta(seconds=int(absolute_seconds))
    with conn.cursor(cursor=pymysql.cursors.DictCursor) as cur:
        cur.execute(
            "INSERT INTO sessions "
            "(id, user_id, issued_at, expires_at, last_active_at, idle_timeout_seconds, absolute_timeout_seconds, ip_address, user_agent) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (sid, user_id, now, expires, now, int(idle_seconds), int(absolute_seconds), ip, (ua or "")[:255])
        )
    return sid

def _get_user_by_username(conn, username):
    with conn.cursor(cursor=pymysql.cursors.DictCursor) as cur:
        cur.execute("SELECT * FROM users WHERE username=%s", (username,))
        return cur.fetchone()

def _serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="mfa")

@bp.get("/login")
def login_get():
    return render_template("login.html", title=ISSUER)

@bp.post("/login")
def login_post():
    username = (request.form.get("username") or "").strip()
    password = (request.form.get("password") or "").encode("utf-8")
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    ua = request.headers.get("User-Agent", "")

    conn = get_conn()
    policy = _get_lockout_policy(conn)

    if _is_locked(conn, username, policy):
        _record_login_event(conn, None, username, False, "LOCKED", ip, ua)
        until = _lock_until_text(conn, username, policy["lock_minutes"])
        return render_template("login.html", title=ISSUER,
                               error=f"Too many attempts. Try again later (until {until})."), 429

    user = _get_user_by_username(conn, username)
    if not user or not user.get("is_active"):
        _record_login_event(conn, user["id"] if user else None, username, False, "NO_USER_OR_INACTIVE", ip, ua)
        time.sleep(0.25)
        return render_template("login.html", title=ISSUER, error="Invalid credentials."), 401

    raw_hash = user.get("password_bcrypt")
    if not raw_hash or not isinstance(raw_hash, str) or not raw_hash.startswith("$2"):
        log.error("Bad or missing hash for user %s: %r", username, raw_hash)
        _record_login_event(conn, user["id"], username, False, "BAD_STORED_HASH", ip, ua)
        return render_template("login.html", title=ISSUER, error="Invalid credentials."), 401

    try:
        ok = bcrypt.checkpw(password, raw_hash.encode("utf-8"))
    except Exception as e:
        log.exception("bcrypt.checkpw failed for user %s", username)
        _record_login_event(conn, user["id"], username, False, "BCRYPT_ERROR", ip, ua)
        return render_template("login.html", title=ISSUER, error="Invalid credentials."), 401

    if not ok:
        _record_login_event(conn, user["id"], username, False, "BAD_PASSWORD", ip, ua)
        return render_template("login.html", title=ISSUER, error="Invalid credentials."), 401

    _record_login_event(conn, user["id"], username, True, "OK", ip, ua)
    with conn.cursor(cursor=pymysql.cursors.DictCursor) as cur:
        cur.execute("UPDATE users SET last_login_at=NOW() WHERE id=%s", (user["id"],))

    if int(user.get("mfa_enabled") or 0) == 1:
        tok = _serializer().dumps({"uid": int(user["id"]), "u": user["username"]})
        resp = make_response(redirect(url_for("auth.mfa_get")))
        resp.set_cookie(MFA_COOKIE, tok, secure=True, httponly=True, samesite=os.getenv("SESSION_COOKIE_SAMESITE","Lax"))
        return resp

    idle, abs_, _ = _policy_defaults()
    sid = _create_session(conn, user["id"], idle, abs_, ip, ua)
    resp = make_response(redirect(url_for('web.home')))
    resp.set_cookie(COOKIE_NAME, sid, secure=True, httponly=True, samesite=os.getenv("SESSION_COOKIE_SAMESITE","Lax"))
    return resp
