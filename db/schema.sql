-- vpn_portal schema
-- Engine: InnoDB, Charset: utf8mb4
-- Safe to re-run: creates if not exists

-- 0) Session SQL mode (safe defaults)
SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 1) Users (password bcrypt, optional TOTP)
CREATE TABLE IF NOT EXISTS users (
  id                BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  username          VARCHAR(64) NOT NULL,
  email             VARCHAR(190) NULL,
  password_bcrypt   VARCHAR(100) NOT NULL,
  is_active         TINYINT(1) NOT NULL DEFAULT 1,
  is_superadmin     TINYINT(1) NOT NULL DEFAULT 0,

  mfa_enabled       TINYINT(1) NOT NULL DEFAULT 0,
  mfa_secret        VARCHAR(64) NULL,          -- base32 if enabled
  mfa_backup_codes  JSON NULL,                  -- array of one-time codes

  last_login_at     DATETIME NULL,
  created_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

  UNIQUE KEY uq_users_username (username),
  UNIQUE KEY uq_users_email (email),
  PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 2) Sites (single-site POC but supports future multi-site)
CREATE TABLE IF NOT EXISTS sites (
  id                 BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  name               VARCHAR(100) NOT NULL,
  fqdn               VARCHAR(190) NOT NULL,
  endpoint_host      VARCHAR(190) NOT NULL,
  endpoint_port      INT UNSIGNED NOT NULL DEFAULT 51820,
  wg_interface       VARCHAR(32) NOT NULL DEFAULT 'wg0',
  wg_interface_ip    VARCHAR(64) NOT NULL,     -- e.g., 10.88.0.1/24
  dns_wg_ip          VARCHAR(64) NULL,         -- dnsmasq listen IP on wg
  lan_cidrs_json     JSON NOT NULL,            -- e.g., ["192.168.1.0/24"]
  timezone           VARCHAR(64) NOT NULL DEFAULT 'America/New_York',
  notes              TEXT NULL,

  created_at         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

  UNIQUE KEY uq_sites_fqdn (fqdn),
  PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 3) Peers (desired state; applied via wg set at runtime)
--    Note: runtime state (handshake, bytes) is read from `wg show` and can be synced into these fields.
CREATE TABLE IF NOT EXISTS peers (
  id                      BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  site_id                 BIGINT UNSIGNED NOT NULL,
  user_id                 BIGINT UNSIGNED NULL,   -- optional: owner mapping
  label                   VARCHAR(100) NOT NULL,  -- human-friendly device name
  public_key              VARCHAR(60) NOT NULL,   -- WireGuard pubkey
  preshared_key           VARCHAR(60) NULL,       -- optional PSK
  address_cidr            VARCHAR(64) NOT NULL,   -- e.g., 10.88.0.2/32
  allowed_ips             TEXT NOT NULL,          -- e.g., "0.0.0.0/0, ::/0"
  dns_servers             VARCHAR(255) NULL,      -- e.g., "10.88.0.1"
  persistent_keepalive_s  INT NULL,               -- seconds or NULL
  enabled                 TINYINT(1) NOT NULL DEFAULT 1,

  -- runtime sync fields (read-only from app’s perspective)
  last_handshake_at       DATETIME NULL,
  bytes_rx                BIGINT UNSIGNED NOT NULL DEFAULT 0,
  bytes_tx                BIGINT UNSIGNED NOT NULL DEFAULT 0,

  created_at              DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at              DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

  UNIQUE KEY uq_peers_pubkey (public_key),
  UNIQUE KEY uq_peers_site_addr (site_id, address_cidr),
  INDEX ix_peers_site (site_id),
  INDEX ix_peers_user (user_id),
  CONSTRAINT fk_peers_site FOREIGN KEY (site_id) REFERENCES sites(id) ON DELETE CASCADE,
  CONSTRAINT fk_peers_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,

  PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 4) Sessions (idle/absolute TTL enforcement; server-side tracking)
CREATE TABLE IF NOT EXISTS sessions (
  id                     CHAR(64) NOT NULL,        -- server-issued opaque ID
  user_id                BIGINT UNSIGNED NOT NULL,
  issued_at              DATETIME NOT NULL,
  expires_at             DATETIME NOT NULL,        -- absolute TTL
  last_active_at         DATETIME NOT NULL,        -- idle timeout anchor
  idle_timeout_seconds   INT NOT NULL DEFAULT 1500,  -- 25m default (scope may say 25m)
  absolute_timeout_seconds INT NOT NULL DEFAULT 1800, -- 30m default
  ip_address             VARCHAR(45) NULL,         -- IPv4/IPv6
  user_agent             VARCHAR(255) NULL,
  revoked                TINYINT(1) NOT NULL DEFAULT 0,

  INDEX ix_sessions_user (user_id),
  INDEX ix_sessions_last_active (last_active_at),
  INDEX ix_sessions_expires (expires_at),
  CONSTRAINT fk_sessions_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,

  PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 5) Login events (for lockout, auditing)
CREATE TABLE IF NOT EXISTS login_events (
  id                 BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id            BIGINT UNSIGNED NULL,    -- may be NULL if username not found
  username_attempted VARCHAR(64) NULL,
  success            TINYINT(1) NOT NULL,
  reason             VARCHAR(64) NULL,        -- e.g., "OK", "BAD_PASSWORD", "LOCKED"
  ip_address         VARCHAR(45) NULL,
  user_agent         VARCHAR(255) NULL,
  created_at         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

  INDEX ix_login_user (user_id),
  INDEX ix_login_created (created_at),
  PRIMARY KEY (id),
  CONSTRAINT fk_login_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 6) Audit log (administrative actions; 90-day retention via cron)
CREATE TABLE IF NOT EXISTS audit_log (
  id            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id       BIGINT UNSIGNED NULL,
  action        VARCHAR(64) NOT NULL,      -- e.g., "PEER_CREATE", "PEER_DISABLE"
  target_type   VARCHAR(64) NULL,          -- e.g., "peer", "site", "user"
  target_id     BIGINT UNSIGNED NULL,
  ip_address    VARCHAR(45) NULL,
  user_agent    VARCHAR(255) NULL,
  details_json  JSON NULL,                 -- structured context
  created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

  INDEX ix_audit_user (user_id),
  INDEX ix_audit_created (created_at),
  PRIMARY KEY (id),
  CONSTRAINT fk_audit_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 7) Deny schedules (optional: time windows to deny access)
CREATE TABLE IF NOT EXISTS deny_schedules (
  id            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  site_id       BIGINT UNSIGNED NOT NULL,
  user_id       BIGINT UNSIGNED NULL,       -- NULL = applies to all users at site
  label         VARCHAR(100) NOT NULL,
  policy_json   JSON NOT NULL,              -- app-defined (e.g., {"days":[1..5], "start":"22:00","end":"06:00","tz":"..."}
  active        TINYINT(1) NOT NULL DEFAULT 1,
  created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

  INDEX ix_deny_site (site_id),
  INDEX ix_deny_user (user_id),
  PRIMARY KEY (id),
  CONSTRAINT fk_deny_site FOREIGN KEY (site_id) REFERENCES sites(id) ON DELETE CASCADE,
  CONSTRAINT fk_deny_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 8) Settings (key/value for site-wide toggles, e.g., password policy)
CREATE TABLE IF NOT EXISTS settings (
  k VARCHAR(100) NOT NULL,
  v JSON NOT NULL,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (k)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 9) Migrations bookkeeping (optional)
CREATE TABLE IF NOT EXISTS schema_migrations (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  name VARCHAR(190) NOT NULL,
  applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_migration_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 10) Helpful defaults (only insert if table empty)
INSERT INTO settings (k, v)
SELECT 'session_policy', JSON_OBJECT(
  'idle_seconds', 1500,   -- 25m idle
  'absolute_seconds', 1800, -- 30m absolute
  'grace_seconds', 300
)
WHERE NOT EXISTS (SELECT 1 FROM settings WHERE k='session_policy');

INSERT INTO settings (k, v)
SELECT 'log_retention_days', JSON_OBJECT('audit', 90, 'login', 90)
WHERE NOT EXISTS (SELECT 1 FROM settings WHERE k='log_retention_days');
