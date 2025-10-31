import os, logging, pymysql
from flask import Flask, g, request
from dotenv import load_dotenv

def create_app():
    load_dotenv("/opt/vpn-portal/.env")
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-not-secret")

    # Blueprints
    from .auth import bp as auth_bp
    from .web import bp as web_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(web_bp)

    # Simple session loader: puts session row (dict) in g.session if vpnsess cookie is valid & not expired/revoked
    from .db import get_conn
    import pymysql.cursors

    @app.before_request
    def load_session():
        g.session = None
        sid = request.cookies.get("vpnsess")
        if not sid:
            return
        try:
            conn = get_conn()
            with conn.cursor(cursor=pymysql.cursors.DictCursor) as cur:
                cur.execute("""
                    SELECT s.* FROM sessions s
                    WHERE s.id=%s AND s.revoked=0 AND s.expires_at > UTC_TIMESTAMP()
                """, (sid,))
                row = cur.fetchone()
                if row:
                    g.session = row
        except Exception as e:
            app.logger.warning("session load failed: %r", e)

    return app

# For gunicorn entry point
app = create_app()
