import os
import datetime
from flask import Flask, request, redirect, url_for, g
from dotenv import load_dotenv
from .db import get_conn

def create_app():
    # Load .env early
    load_dotenv(dotenv_path=os.path.join("/opt/vpn-portal", ".env"), override=False)

    # Optionally load extra env fragments (e.g., .env.d/*)
    envd = os.path.join("/opt/vpn-portal", ".env.d")
    if os.path.isdir(envd):
        for name in sorted(os.listdir(envd)):
            p = os.path.join(envd, name)
            if os.path.isfile(p):
                load_dotenv(dotenv_path=p, override=True)

    app = Flask(
        __name__,
        template_folder="/opt/vpn-portal/templates",
        static_folder="/opt/vpn-portal/static",
    )

    # Core secrets / cookies
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "CHANGE_ME_DEV_ONLY")
    app.config["SESSION_COOKIE_SECURE"]   = os.getenv("SESSION_COOKIE_SECURE", "true").lower() == "true"
    app.config["SESSION_COOKIE_HTTPONLY"] = os.getenv("SESSION_COOKIE_HTTPONLY", "true").lower() == "true"
    app.config["SESSION_COOKIE_SAMESITE"] = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")

    # Blueprints
    from .auth import bp as auth_bp
    from .routes import bp as web_bp
    app.register_blueprint(auth_bp)   # /login, /logout
    app.register_blueprint(web_bp)    # /, /dashboard, healthz, readyz

    # --- Session enforcement (idle + absolute TTL) ---
    from .auth import COOKIE_NAME
    @app.before_request
    def _enforce_session_ttl():
        # Public endpoints (extend as needed)
        if request.endpoint in ("auth.login_get", "auth.login_post", "static", None):
            return
        sid = request.cookies.get(COOKIE_NAME)
        if not sid:
            return redirect(url_for("auth.login_get"))

        conn = get_conn()
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM sessions WHERE id=%s AND revoked=0", (sid,))
            s = cur.fetchone()
        if not s:
            return redirect(url_for("auth.login_get"))

        now = datetime.datetime.utcnow()

        # Absolute expiry
        if now > s["expires_at"]:
            with conn.cursor() as cur:
                cur.execute("UPDATE sessions SET revoked=1 WHERE id=%s", (sid,))
            return redirect(url_for("auth.login_get"))

        # Idle timeout
        idle_secs = int(s.get("idle_timeout_seconds") or 1500)
        if (now - s["last_active_at"]).total_seconds() > idle_secs:
            with conn.cursor() as cur:
                cur.execute("UPDATE sessions SET revoked=1 WHERE id=%s", (sid,))
            return redirect(url_for("auth.login_get"))

        # Touch last_active
        with conn.cursor() as cur:
            cur.execute("UPDATE sessions SET last_active_at=%s WHERE id=%s", (now, sid))
        g.session = s

    return app

# Also expose `app` for wsgi:app usage if gunicorn imports module directly
app = create_app()
