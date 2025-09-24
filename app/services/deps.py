from __future__ import annotations
import os
try:
    import asyncpg
except Exception:
    asyncpg = None
_pool = None

async def init_db_pool() -> None:
    global _pool
    if _pool is not None: return
    dsn = os.getenv("DATABASE_URL") or os.getenv("DB_DSN")
    if not dsn or asyncpg is None: return
    _pool = await asyncpg.create_pool(dsn, min_size=1, max_size=5)

async def close_db_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None

async def get_db_pool():
    global _pool
    if _pool is None:
        try: await init_db_pool()
        except Exception: pass
    return _pool or _DummyPool()

class _AcquireCtx:
    async def __aenter__(self): return _DummyConn()
    async def __aexit__(self, exc_type, exc, tb): return False
class _DummyPool:
    def acquire(self): return _AcquireCtx()
    async def close(self): return None
class _DummyConn:
    async def fetch(self, *args, **kwargs): return []
    async def fetchrow(self, *args, **kwargs): return None
    async def close(self): return None
