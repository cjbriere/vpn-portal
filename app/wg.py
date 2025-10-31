import ipaddress, subprocess, json, os, re
from .db import get_conn

WG_BIN = os.getenv("WG_BIN", "/usr/bin/wg")
WG_IF  = os.getenv("WG_INTERFACE", "wg0")

def _sudo(*args):
    # All calls use full paths; sudo is NOPASSWD for allowed subcommands.
    cmd = ["sudo", WG_BIN] + list(args)
    p = subprocess.run(cmd, text=True, capture_output=True)
    if p.returncode != 0:
        raise RuntimeError(f"wg error: {' '.join(cmd)} :: {p.stderr.strip() or p.stdout.strip()}")
    return p.stdout

def show():
    return _sudo("show")

def show_json():
    # Parse "wg show" into a dict (minimal fields we care about)
    out = _sudo("show")
    data = {"peers": {}}
    cur_peer = None
    for line in out.splitlines():
        if line.startswith("peer: "):
            cur_peer = line.split("peer: ",1)[1].strip()
            data["peers"][cur_peer] = {}
        elif cur_peer:
            if "endpoint:" in line: data["peers"][cur_peer]["endpoint"] = line.split("endpoint:",1)[1].strip()
            if "allowed ips:" in line: data["peers"][cur_peer]["allowed_ips"] = line.split("allowed ips:",1)[1].strip()
            if "latest handshake:" in line: data["peers"][cur_peer]["latest_handshake"] = line.split("latest handshake:",1)[1].strip()
            if "transfer:" in line: data["peers"][cur_peer]["transfer"] = line.split("transfer:",1)[1].strip()
    return data

def add_peer(public_key:str, allowed_ips:str, preshared_key:str|None=None, keepalive:int|None=None):
    args = ["set", WG_IF, "peer", public_key, "allowed-ips", allowed_ips]
    if keepalive is not None:
        args += ["persistent-keepalive", str(keepalive)]
    # NOTE: preshared_key can be set later if desired; skipping for now.
    _sudo(*args)
    return True

def remove_peer(public_key:str):
    _sudo("set", WG_IF, "peer", public_key, "remove")
    return True

def genkeypair():
    # wg genkey/pubkey do not require root; run without sudo
    p = subprocess.run([WG_BIN, "genkey"], text=True, capture_output=True)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.strip() or p.stdout.strip())
    priv = p.stdout.strip()
    p2 = subprocess.run([WG_BIN, "pubkey"], text=True, input=priv, capture_output=True)
    if p2.returncode != 0:
        raise RuntimeError(p2.stderr.strip() or p2.stdout.strip())
    pub = p2.stdout.strip()
    return priv, pub

def _site_cidr_and_base(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT id, wg_interface_ip FROM sites ORDER BY id ASC LIMIT 1")
        row = cur.fetchone()
    if not row:
        raise RuntimeError("No site configured in 'sites' table")
    # e.g., '10.88.0.1/24'
    net = ipaddress.ip_network(row["wg_interface_ip"], strict=False)
    gw  = ipaddress.ip_interface(row["wg_interface_ip"]).ip
    return row["id"], net, gw

def next_available_address_cidr(conn)->str:
    site_id, net, gw = _site_cidr_and_base(conn)
    used = set()
    with conn.cursor() as cur:
        cur.execute("SELECT address_cidr FROM peers WHERE site_id=%s", (site_id,))
        for r in cur.fetchall():
            try:
                used.add(ipaddress.ip_interface(r["address_cidr"]).ip)
            except Exception:
                pass
    # reserve the gateway
    used.add(gw)
    # start at .2 (skip .1 gw)
    for host in net.hosts():
        if int(host) <= int(gw):  # skip .1
            continue
        if host not in used:
            return f"{str(host)}/32"
    raise RuntimeError("No free addresses left in pool")
