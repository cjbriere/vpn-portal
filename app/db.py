import os, urllib.parse, pymysql

def _parse_mysql_url(url: str):
    # mysql+pymysql://user:pass@host:3306/dbname
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    if url.startswith("mysql+pymysql://"):
        url = url[len("mysql+pymysql://"):]
    parsed = urllib.parse.urlparse("scheme://" + url)
    user = urllib.parse.unquote(parsed.username or "")
    pw   = urllib.parse.unquote(parsed.password or "")
    host = parsed.hostname or "localhost"
    port = parsed.port or 3306
    db   = (parsed.path or "/").lstrip("/") or None
    if not db:
        raise RuntimeError("DATABASE_URL missing database name")
    return dict(host=host, user=user, password=pw, database=db, port=port)

def get_conn(autocommit=True):
    cfg = _parse_mysql_url(os.getenv("DATABASE_URL"))
    return pymysql.connect(
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=autocommit,
        **cfg
    )
