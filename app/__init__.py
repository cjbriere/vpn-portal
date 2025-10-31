import os
from flask import Flask
from dotenv import load_dotenv

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

    app = Flask(__name__, template_folder="/opt/vpn-portal/templates", static_folder="/opt/vpn-portal/static")
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "CHANGE_ME_DEV_ONLY")
    app.config["SESSION_COOKIE_SECURE"]   = os.getenv("SESSION_COOKIE_SECURE", "true").lower() == "true"
    app.config["SESSION_COOKIE_HTTPONLY"] = os.getenv("SESSION_COOKIE_HTTPONLY", "true").lower() == "true"
    app.config["SESSION_COOKIE_SAMESITE"] = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")

    # Minimal blueprints/routes
    from .routes import bp as web_bp
    app.register_blueprint(web_bp)

    return app

# Support "from app import app" pattern as well
try:
    app = create_app()
except Exception as e:
    # Let gunicorn show the error but avoid hiding stack
    raise
