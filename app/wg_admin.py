import os, json
from flask import Blueprint, render_template, request, redirect, url_for, g, abort, flash
from .db import get_conn
from .wg import show_json, genkeypair, add_peer, remove_peer, next_available_address_cidr

bp = Blueprint("wgadmin", __name__, url_prefix="/peers")

def _require_superadmin():
    # g.session is set by before_request in app/__init__.py
    if not getattr(g, "session", None):
        abort(403)
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT is_superadmin FROM users WHERE id=%s", (g.session["user_id"],))
        row = cur.fetchone()
    if not row or int(row.get("is_superadmin") or 0) != 1:
        abort(403)

@bp.get("/")
def list_peers():
    _require_superadmin()
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("""
            SELECT p.id, p.label, p.public_key, p.address_cidr, p.allowed_ips, p.enabled, u.username
            FROM peers p LEFT JOIN users u ON p.user_id=u.id
            ORDER BY p.id DESC
        """)
        peers = cur.fetchall()
    live = show_json()
    return render_template("peers.html", peers=peers, live=live)

@bp.get("/new")
def new_peer_form():
    _require_superadmin()
    return render_template("peer_new.html")

@bp.post("/new")
def create_peer():
    _require_superadmin()
    label = (request.form.get("label") or "").strip() or "Device"
    allowed = (request.form.get("allowed_ips") or "0.0.0.0/0, ::/0").strip()
    keepalive = request.form.get("keepalive")
    keepalive_i = int(keepalive) if keepalive and keepalive.isdigit() else None

    conn = get_conn()
    # generate keys & find next /32
    priv, pub = genkeypair()
    addr_cidr = next_available_address_cidr(conn)

    try:
        # 1) write to DB first (desired state)
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO peers (site_id, user_id, label, public_key, preshared_key, address_cidr, allowed_ips, dns_servers, persistent_keepalive_s, enabled)
                VALUES ((SELECT id FROM sites ORDER BY id ASC LIMIT 1), NULL, %s, %s, NULL, %s, %s, NULL, %s, 1)
            """, (label, pub, addr_cidr, allowed, keepalive_i))
        # 2) apply live
        add_peer(public_key=pub, allowed_ips=addr_cidr, preshared_key=None, keepalive=keepalive_i)
    except Exception as e:
        # rollback DB entry on failure
        with conn.cursor() as cur:
            cur.execute("DELETE FROM peers WHERE public_key=%s", (pub,))
        raise

    # Show private key once for admin to build client config later
    return redirect(url_for("wgadmin.list_peers"))

@bp.post("/delete/<int:peer_id>")
def delete_peer(peer_id: int):
    _require_superadmin()
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT public_key FROM peers WHERE id=%s", (peer_id,))
        row = cur.fetchone()
    if not row:
        return redirect(url_for("wgadmin.list_peers"))
    pub = row["public_key"]
    # live remove first (if it fails, keep DB to retry)
    try:
        remove_peer(pub)
    except Exception:
        pass
    with conn.cursor() as cur:
        cur.execute("DELETE FROM peers WHERE id=%s", (peer_id,))
    return redirect(url_for("wgadmin.list_peers"))
