# app/auth.py
from __future__ import annotations

import base64
import hmac
import os
import struct
import time
from hashlib import sha1
from io import BytesIO
from typing import Any, Optional
from urllib.parse import urlparse, unquote

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    session,
    abort,
    send_file,
    current_app,
)
from werkzeug.security import check_password_hash

# Import project db module; we'll still be resilient if it lacks helpers.
from . import db as db

# Optional QR generator. If not present, we fallback to showing the otpauth URI.
try:
    import qrcode  # type: ignore
except Exception:  # pragma: no cover
    qrcode = None  # type: ignore

bp = Blueprint("auth", __name__)

# --------------------
# DB connection helper
# --------------------
def _conn():
    """
    Prefer a connection from app.db; otherwise open one from DATABASE_URL.
    Checked, in order:
      - db.get_db()
      - db.connect()
      - db.connect_db()
      - db.db()                (callable)
      - db.connection         (connection handle)
      - os.environ["DATABASE_URL"] or
