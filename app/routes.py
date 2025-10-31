import os, time
from flask import Blueprint, render_template, jsonify

bp = Blueprint("web", __name__)

START_TS = time.time()

@bp.get("/")
def index():
    return render_template("index.html")

@bp.get("/login")
def login_placeholder():
    # Placeholder page; real auth will replace this route later
    return render_template("login.html")

@bp.get("/healthz")
def healthz():
    # Liveness: process is up
    return jsonify(status="ok", uptime_seconds=round(time.time() - START_TS, 1))

@bp.get("/readyz")
def readyz():
    # Readiness: basic app readiness (extend with DB check later)
    return jsonify(status="ready")
