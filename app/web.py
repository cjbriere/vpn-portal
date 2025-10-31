# app/web.py
from flask import Blueprint, session, redirect, url_for, render_template_string

bp = Blueprint("web", __name__)

@bp.route("/")
def home():
    # If not logged in, send to login
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))

    # Minimal placeholder for now (redirect target after MFA)
    return render_template_string(
        "<!doctype html><title>CITS VPN Portal — Home</title>"
        "<body style='background:#0b0f14;color:#e6eef8;font-family:system-ui;'>"
        "<div style='max-width:720px;margin:10vh auto;padding:24px;"
        "background:#111825;border:1px solid #1f2a3b;border-radius:14px;'>"
        "<h1 style='color:#cfe3ff;margin:0 0 12px;'>Welcome</h1>"
        "<p>You are logged in. This is <strong>web.home</strong>.</p>"
        "</div></body>"
    )
