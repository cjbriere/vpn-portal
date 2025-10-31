## 2025-10-30
- Initial full scope and collaboration policy established.
## 2025-10-31 — Bootstrap, HTTPS, and auth redirect hotfix

### Added
- Project root at `/opt/vpn-portal` with Python venv: `/opt/vpn-portal/venv`.
- Environment file `/opt/vpn-portal/.env` with secure perms (`640`, owner `vpnportal:root`).
- Flask app factory and routes:
  - `web.home` (`/`)
  - `web.readyz` (`/readyz`)
  - `web.peers` (`/peers/`) — **auth required**
  - `auth.login_get` (GET `/login`)
  - `auth.login_post` (POST `/login`)
- Nginx reverse proxy for HTTPS:
  - `/etc/nginx/sites-available/vpn-portal.conf` → enabled via symlink
  - HTTP → HTTPS redirect
  - Security headers + CSP (report-only)
  - Optional rate limit on `/login` via `limit_req` (login_zone)
- Systemd process model:
  - `vpn-portal.service` (Gunicorn, gthread workers)
  - Unix socket: `/run/vpn-portal/vpn-portal.sock`
- Database schema created in `vpn_portal` (MariaDB):
  - Tables: `users`, `sessions`, `login_events`, `audit_log`, `deny_schedules`, `peers`, `peer_events` (optional), `sites`, `settings`, `schema_migrations`
  - Seeded superadmin `cjbriere` (bcrypt hash present, `is_superadmin=1`, `is_active=1`)

### Changed
- Login success redirect now targets `web.home` (`/`) instead of non-existent `web.dashboard`.
- Nginx site config updated to avoid duplicate default server on `:80` (disabled `/etc/nginx/sites-enabled/default`).

### Fixed
- **500 on POST /login** due to `url_for("web.dashboard")` → corrected to `url_for("web.home")`.
- **DB auth failures** traced to `.env` `DATABASE_URL` vs MariaDB user password mismatch — corrected and verified.
- **Curl tests breaking on special chars** — switched to `--data-urlencode` for credentials during CLI tests.

### Security / Ops
- Strict ownership and permissions on `/opt/vpn-portal/.env` (`vpnportal:root`, `0640`).
- HTTPS-only access enforced by Nginx redirect; HSTS enabled.
- Basic request rate limiting on `/login`.
- Service restarts cleanly; reboot sanity deemed worthwhile and performed (Gunicorn + Nginx come up healthy).

### Verification
- Healthcheck: `GET /readyz` returns `200`.
- URL map validated via `PYTHONPATH=/opt/vpn-portal python -c` inspection.
- DB connectivity confirmed with `mysql` CLI and app-level cursor test.
- Auth flow:
  - `POST /login` with valid creds → **200** then redirect to `/`.
  - Session cookie set; `HEAD /peers/` with cookie returns **200**.
- Nginx config `nginx -t` passes; service reloads without error.

### Known placeholders / TODO
- Replace minimal login placeholder UI with production template (dark, clean “CITS VPN Portal”).
- Implement MFA (TOTP) step: `/mfa` (GET/POST); issue session cookie post-TOTP.
- Lock static asset paths (`/static/...`) and add real CSS/JS.
- Admin: superadmin dashboard and user management.
- Cert lifecycle: finalize ACME issuance/renewal method for `vpn.c-itsolutions.com` and ensure post-renew `systemctl reload nginx`.
- Add peer management UI and audit views (surface `peer_events`, `login_events`).

### Files touched (high level)
- `/opt/vpn-portal/app/__init__.py`
- `/opt/vpn-portal/app/auth.py`
- `/opt/vpn-portal/app/web.py` (or equivalent blueprint file)
- `/opt/vpn-portal/templates/login.html` (placeholder)
- `/etc/nginx/sites-available/vpn-portal.conf`
- `/etc/systemd/system/vpn-portal.service`
- `/opt/vpn-portal/.env`
- MariaDB `vpn_portal` schema & seeds
