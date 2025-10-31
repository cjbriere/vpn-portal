import os, secrets, time, datetime, bcrypt, base64, io, json
import pyotp, qrcode
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from flask import Blueprint, request, render_template, redirect, url_for, make_response, current_app, g
from .db import get_conn

bp = Blueprint("auth", __name__)
COOKIE_NAME = "vpnsess"
MFA_COOKIE = "vpnmfa"
ISSUER = "CITS VPN Portal"

def _policy_defaults():
    idle  = int(os.getenv("SESSION_IDLE_SECONDS", "1500"))       # 25m default
    abs_  = int(os.getenv("SESSION_ABSOLUTE_SECONDS", "1800"))   # 30m default
    grace = int(os.getenv("SESSION_GRACE_SECONDS", "300"))       # 5m default
    return idle, abs_, grace

def _get_lockout_policy(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT v FROM settings WHERE k='lockout_policy'")
        row = cur.fetchone()
    policy = {"window_minutes": 15, "max_attempts": 5, "lock_minutes": 15}
    if row and row.get("v"):
        try:
            policy.update(json.loads(row["v"]))
        except Exception:
            pass
    return policy

def _record_login_event(conn, user_id, username_attempted, success, reason, ip, ua):
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO login_events (user_id, username_attempted, success, reason, ip_address, user_agent) "
            "VALUES (%s,%s,%s,%s,%s,%s)",
            (user_id, username_attempted, 1 if success else 0, reason, ip, ua[:255] if ua else None)
        )

def _is_locked(conn, username, policy):
    with conn.cursor() as cur:
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
    with conn.cursor() as cur:
        cur.execute(
            "SELECT created_at FROM login_events "
            "WHERE username_attempted=%s AND success=0 ORDER BY created_at DESC LIMIT 1",
            (username,)
        )
        row = cur.fetchone()
    if not row:
        return None
    until = row["created_at"] + datetime.timedelta(minutes=int(lock_minutes))
    return until.strftime("%Y-%m-%d %H:%M:%S")

def _create_session(conn, user_id, idle_seconds, absolute_seconds, ip, ua):
    sid = secrets.token_hex(32)  # 64-char
    now = datetime.datetime.utcnow()
    expires = now + datetime.timedelta(seconds=int(absolute_seconds))
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO sessions "
            "(id, user_id, issued_at, expires_at, last_active_at, idle_timeout_seconds, absolute_timeout_seconds, ip_address, user_agent) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (sid, user_id, now, expires, now, int(idle_seconds), int(absolute_seconds), ip, ua[:255] if ua else None)
        )
    return sid

def _get_user_by_username(conn, username):
    with conn.cursor() as cur:
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
        time.sleep(0.3)
        return render_template("login.html", title=ISSUER, error="Invalid credentials."), 401

    try:
        ok = bcrypt.checkpw(password, user["password_bcrypt"].encode("utf-8"))
    except Exception:
        ok = False

    if not ok:
        _record_login_event(conn, user["id"], username, False, "BAD_PASSWORD", ip, ua)
        return render_template("login.html", title=ISSUER, error="Invalid credentials."), 401

    # Password OK
    _record_login_event(conn, user["id"], username, True, "OK", ip, ua)
    with conn.cursor() as cur:
        cur.execute("UPDATE users SET last_login_at=NOW() WHERE id=%s", (user["id"],))

    # If MFA is enabled → go to /mfa. Else issue full session now.
    if int(user.get("mfa_enabled") or 0) == 1:
        tok = _serializer().dumps({"uid": int(user["id"]), "u": user["username"]})
        resp = make_response(redirect(url_for("auth.mfa_get")))
        resp.set_cookie(MFA_COOKIE, tok, secure=True, httponly=True, samesite=os.getenv("SESSION_COOKIE_SAMESITE","Lax"))
        return resp

    idle, abs_, _ = _policy_defaults()
    sid = _create_session(conn, user["id"], idle, abs_, ip, ua)
    resp = make_response(redirect(url_for("web.dashboard")))
    resp.set_cookie(COOKIE_NAME, sid, secure=True, httponly=True, samesite=os.getenv("SESSION_COOKIE_SAMESITE","Lax"))
    return resp

@bp.get("/logout")
def logout():
    sid = request.cookies.get(COOKIE_NAME)
    if sid:
        conn = get_conn()
        with conn.cursor() as cur:
            cur.execute("UPDATE sessions SET revoked=1 WHERE id=%s", (sid,))
    resp = make_response(redirect(url_for("auth.login_get")))
    resp.delete_cookie(COOKIE_NAME)
    resp.delete_cookie(MFA_COOKIE)
    return resp

# ---------- MFA VERIFY (for users with mfa_enabled=1) ----------

@bp.get("/mfa")
def mfa_get():
    tok = request.cookies.get(MFA_COOKIE)
    if not tok:
        return redirect(url_for("auth.login_get"))
    try:
        data = _serializer().loads(tok, max_age=600)  # 10 minutes
    except (BadSignature, SignatureExpired):
        resp = make_response(redirect(url_for("auth.login_get")))
        resp.delete_cookie(MFA_COOKIE)
        return resp
    return render_template("mfa.html", title=ISSUER)

@bp.post("/mfa")
def mfa_post():
    tok = request.cookies.get(MFA_COOKIE)
    if not tok:
        return redirect(url_for("auth.login_get"))
    try:
        data = _serializer().loads(tok, max_age=600)
    except (BadSignature, SignatureExpired):
        resp = make_response(redirect(url_for("auth.login_get")))
        resp.delete_cookie(MFA_COOKIE)
        return resp

    code = (request.form.get("code") or "").strip().replace(" ", "")
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    ua = request.headers.get("User-Agent", "")
    uid = int(data["uid"])

    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT id, username, mfa_secret FROM users WHERE id=%s AND is_active=1", (uid,))
        user = cur.fetchone()

    if not user or not user.get("mfa_secret"):
        resp = make_response(redirect(url_for("auth.login_get")))
        resp.delete_cookie(MFA_COOKIE)
        return resp

    totp = pyotp.TOTP(user["mfa_secret"])
    if not (code.isdigit() and len(code) in (6, 7)) or not totp.verify(code, valid_window=1):
        # don’t log as a failed password; this is an MFA failure
        return render_template("mfa.html", title=ISSUER, error="Invalid code."), 401

    # MFA OK → issue session
    idle, abs_, _ = _policy_defaults()
    sid = _create_session(conn, user["id"], idle, abs_, ip, ua)
    resp = make_response(redirect(url_for("web.dashboard")))
    resp.set_cookie(COOKIE_NAME, sid, secure=True, httponly=True, samesite=os.getenv("SESSION_COOKIE_SAMESITE","Lax"))
    resp.delete_cookie(MFA_COOKIE)
    return resp

# ---------- MFA SETUP (for logged-in users without MFA) ----------

def _qr_png_data_uri(otpauth_uri: str) -> str:
    img = qrcode.make(otpauth_uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"

@bp.get("/mfa/setup")
def mfa_setup_get():
    # require a logged-in session (enforced by app.before_request in __init__.py)
    if getattr(g, "session", None) is None:
        return redirect(url_for("auth.login_get"))

    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT id, username, mfa_enabled, mfa_secret FROM users WHERE id=%s", (g.session["user_id"],))
        user = cur.fetchone()

    # If already enabled, just show info
    if int(user.get("mfa_enabled") or 0) == 1 and user.get("mfa_secret"):
        return render_template("mfa_setup.html", title=ISSUER, already=True)

    # Generate secret if missing
    secret = user.get("mfa_secret") or pyotp.random_base32()
    if user.get("mfa_secret") != secret:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET mfa_secret=%s WHERE id=%s", (secret, user["id"]))

    label = f"{ISSUER}:{user['username']}"
    otpauth = pyotp.totp.TOTP(secret).provisioning_uri(name=label, issuer_name=ISSUER)
    qr_data_uri = _qr_png_data_uri(otpauth)
    return render_template("mfa_setup.html", title=ISSUER, secret=secret, qr_data_uri=qr_data_uri, already=False)

@bp.post("/mfa/setup")
def mfa_setup_post():
    if getattr(g, "session", None) is None:
        return redirect(url_for("auth.login_get"))

    code = (request.form.get("code") or "").strip().replace(" ", "")
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT id, username, mfa_secret FROM users WHERE id=%s", (g.session["user_id"],))
        user = cur.fetchone()

    if not user or not user.get("mfa_secret"):
        return redirect(url_for("web.dashboard"))

    totp = pyotp.TOTP(user["mfa_secret"])
    if not (code.isdigit() and len(code) in (6, 7)) or not totp.verify(code, valid_window=1):
        label = f"{ISSUER}:{user['username']}"
        otpauth = pyotp.totp.TOTP(user["mfa_secret"]).provisioning_uri(name=label, issuer_name=ISSUER)
        qr_data_uri = _qr_png_data_uri(otpauth)
        return render_template("mfa_setup.html", title=ISSUER, secret=user["mfa_secret"], qr_data_uri=qr_data_uri,
                               error="Invalid code. Try again.", already=False), 401

    # Success → enable MFA
    with conn.cursor() as cur:
        cur.execute("UPDATE users SET mfa_enabled=1 WHERE id=%s", (user["id"],))
    return redirect(url_for("web.dashboard"))
