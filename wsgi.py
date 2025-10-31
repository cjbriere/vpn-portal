import os, sys, importlib
BASE = "/opt/vpn-portal"
if BASE not in sys.path:
    sys.path.insert(0, BASE)

candidates = ("app", "vpn_portal", "portal")
last_err = None
app = None

for name in candidates:
    try:
        mod = importlib.import_module(name)
        if hasattr(mod, "create_app"):
            app = mod.create_app()
            break
        if hasattr(mod, "app"):
            app = getattr(mod, "app")
            break
    except Exception as e:
        last_err = e

if app is None:
    raise RuntimeError(
        f"Could not locate Flask application in {candidates}. "
        f"Ensure your package exposes create_app() or app. Last error: {last_err!r}"
    )
