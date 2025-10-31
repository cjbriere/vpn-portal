from flask import Blueprint, render_template, redirect, url_for, g, Response

bp = Blueprint("web", __name__)

@bp.get("/readyz")
def readyz():
    return Response("ok", mimetype="text/plain")

@bp.get("/")
def home():
    # If session middleware placed a session into g, go to peers; otherwise to login
    if getattr(g, "session", None):
        return redirect(url_for("web.peers"))
    return redirect(url_for("auth.login_get"))

@bp.get("/peers/")
def peers():
    if getattr(g, "session", None) is None:
        return redirect(url_for("auth.login_get"))
    # Minimal placeholder page (200 OK) so curl -I shows 200 after login
    return render_template("peers.html")
