from app.main import app as _app
try:
    from app.errors import register_exception_handlers
    register_exception_handlers(_app)
except Exception:
    pass
app = _app
