# app/__init__.py
import os
from flask import Flask

def create_app():
    app = Flask(__name__, template_folder=os.path.join(os.path.dirname(__file__), "..", "templates"))
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-me-in-prod")

    # --- Register blueprints (keep names/paths) ---
    from .auth import bp as auth_bp
    app.register_blueprint(auth_bp)

    # web blueprint should already exist and provide `home`
    from .web import bp as web_bp
    app.register_blueprint(web_bp)

    # new mfa blueprint
    from .mfa import bp as mfa_bp
    app.register_blueprint(mfa_bp)

    return app

# Gunicorn/wsgi entrypoint convenience
app = create_app()
