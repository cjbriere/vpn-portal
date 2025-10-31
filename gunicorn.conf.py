import multiprocessing, os
bind = "unix:/run/vpn-portal/vpn-portal.sock"
workers = max(2, multiprocessing.cpu_count() * 2 + 1)
threads = 2
worker_class = "gthread"
timeout = 30
graceful_timeout = 30
keepalive = 5
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("LOG_LEVEL", "info").lower()
