# CITS VPN Portal — Project Scope (PoC, Single-Site, Finalized)

## 0) Executive Summary
A Flask-based WireGuard portal for Raspberry Pi 5 enabling admin-managed users with password + 2FA, on-demand device creation, and runtime WireGuard peer control. Split tunneling with no Internet through VPN. No dnsmasq; clients use explicit DNS and explicit routes via AllowedIPs. Admin defines LAN subnets and DNS resolvers; the system embeds them in each peer’s .conf. Enforced idle timeout (25m), absolute TTL (30m), and per-user schedules via a lightweight worker.

## 1) Platform / Environment
Target: Raspberry Pi 5, Raspberry Pi OS Lite (64-bit)
Stack: Python 3.11 (venv), Flask, Gunicorn (WSGI), Nginx (TLS), MariaDB (local)
Services:
- vpn-portal.service — Flask app via Gunicorn (runs as vpnportal)
- vpn-portal-worker.service — background scheduler/enforcer (runs as vpnportal)
System user: vpnportal (passwordless, limited sudo)
Network:
- WireGuard interface: wg0 (10.88.0.1/24)
- Public FQDN: vpn.c-itsolutions.com
- Local access: static LAN IP

## 2) WireGuard Control
/etc/wireguard/wg0.conf contains only [Interface] (no peers).
Peer management is runtime-only:
- Activate: wg set wg0 peer <pubkey> allowed-ips <client_ip>/32
- Deactivate: wg set wg0 peer <pubkey> remove
Reboot → zero peers.
IP Pool: 10.88.0.10–10.88.0.254 (/24)
Per-peer IP assignment: random
Full intra-VPN reachability by default.

## 3) Split-Tunnel + DNS
Split-tunnel enforced: only defined subnets routed.
No dnsmasq service.
Per-peer .conf includes both DNS and AllowedIPs.
Default LAN: 192.168.1.0/24
Example peer .conf:
[Interface]
PrivateKey = <client_private_key>
Address = <assigned_ip>/32
DNS = 192.168.1.10, 192.168.1.11, 8.8.8.8
[Peer]
PublicKey = <server_public_key>
Endpoint = vpn.c-itsolutions.com:51820
AllowedIPs = 10.88.0.0/24, 192.168.1.0/24
PersistentKeepalive = 25

## 4) Authentication & Authorization
Login: username + password + 2FA (TOTP, RFC 6238, 30s ±1 step)
2FA policy: forced enrollment if none; admin can delete; user cannot delete own.
Password policy: ≥8 chars, ≥1 upper, ≥1 lower, ≥1 digit, ≥1 special.
Backup codes: 8 hashed codes per user.
Lockout: 5 failed attempts → 15 min lockout.
Roles: admin, user
Admins see all; users see own only.

## 5) Session Policy & Enforcement
Idle timeout: 25m
Absolute TTL: 30m
On logout/timeout/schedule_end → deactivate peer, audit log.
Cookies Secure + HttpOnly; CSRF on forms.

## 6) User Features
Login, force 2FA enrollment, add device, download .conf/QR, activate/deactivate, delete device, change password, device list, view schedule (read-only).

## 7) Admin Features
Users: list/search/create/reset/enable/disable/unlock/delete 2FA
Devices: list, download, activate/deactivate, delete
Schedules: weekly per-user grid (Mon–Sun, multiple ranges/day)
Logs: filter/search/export CSV, 90-day retention
Site Config: site_name, public_fqdn, wg_port, lan_subnets_json, dns_ipv4_json
Change triggers banner for re-download.

## 8) Schedules & Worker
Default always allowed.
Model: {"mon":[["09:00","17:00"],["19:00","21:00"]]}
Worker every 30s: enforce schedule, idle, TTL, log tunnel_started/ended.
Merged log stream.

## 9) Database Schema
Schema: vpn_portal
Tables: users, devices, device_state, schedules, audit_logs, site_config
Retention: 90d purge via cron or SQL event.
Importer: db/schema.sql

## 10) Security / Privilege Model
App runs as vpnportal.
sudoers:
Cmnd_Alias CITS_WG = /usr/bin/wg show wg0, /usr/bin/wg set wg0 *
vpnportal ALL=(root) NOPASSWD: CITS_WG
Secrets: /etc/vpn-portal/secret (0600), AES-GCM encrypted keys.
CSRF enabled.
UFW/nftables: UDP 51820 open, wg0<->wg0 allowed, wg0->eth0 allowed to LAN only, no Internet NAT.

## 11) UI / UX
Tailwind dark-only.
Palette: #202123, #343541, #ECECF1/#AEB0B4, #3B82F6, #EF4444.
Layout: User topbar, Admin sidebar.
Polling 5s for handshake state.

## 12) Deployment & Ops
Python venv: /opt/vpn-portal/venv
App structure under /opt/vpn-portal
Systemd services: vpn-portal.service, vpn-portal-worker.service
Nginx reverse proxy to Gunicorn socket.
MariaDB local; DB vpn_portal; user vpn_admin.
Backups optional, logs purge >90d.

## 13) Site Configuration
Global config: site_name, public_fqdn, wg_port, lan_subnets_json, dns_ipv4_json.
Behavior: AllowedIPs always include 10.88.0.0/24 and LANs.
DNS in peer conf = dns_ipv4_json.
On change: mark configs stale, banner prompt re-download.

## 14) One-Command Installer
/usr/local/sbin/cits-install.sh (idempotent)
Prompts for SITE_FQDN, STATIC_IP, GATEWAY, HOST_DNS, CERTBOT_EMAIL, DB creds, admin creds.
Actions: installs deps, sets TZ, configures wg0, creates vpnportal user, venv, secret, DB+user, seeds admin, installs systemd units, Nginx vhost, TLS setup.
Outputs: /var/log/cits-install.log, printed secrets.
--remove disables services, restores configs, keeps DB.

## 15) Logging & Retention
Audit logs 90d retention, CSV export, combined filters.

## 16) Health & Ops
/healthz endpoint returns 200 JSON.
Chrony sync; UFW open UDP 51820 + web ports; intra-VPN unrestricted.

## 17) Files, Paths, Names
/opt/vpn-portal, /etc/vpn-portal/secret, /run/vpn-portal/fg.sock, vpn_portal DB, wg0 interface, default LAN 192.168.1.0/24.

## 18) Deliverables
PROJECT_SCOPE.md, COLLABORATION_POLICY.md, README.md, CHANGELOG.md, db/schema.sql, scripts/cits-install.sh, systemd units, nginx conf, sudoers entry, Flask app, templates, static.

## 19) Hard Requirements Checklist
No dnsmasq. Split-tunnel. AllowedIPs = 10.88.0.0/24 + LAN. DNS = site-config. No email. Admin-only users. 2FA mandatory. Runtime peers. 90-day logs. vpnportal user + minimal sudo.

## 20) Example SQL
[Full schema as previously defined.]

## 21) CHANGELOG & Thread Bootstrap
Maintain CHANGELOG.md and paste last 10–15 lines at new thread start.
