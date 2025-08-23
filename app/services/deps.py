from __future__ import annotations
import os

try:
    import asyncpg  # 线上有数据库时用
except Exception:
    asyncpg = None  # 本地没装也不阻塞

_pool = None  # 全局连接池

async def init_db_pool() -> None:
    """按需初始化 asyncpg 连接池（未配置 DSN 时跳过，不抛错）"""
    global _pool
    if _pool is not None:
        return
    dsn = os.getenv("DATABASE_URL") or os.getenv("DB_DSN")
    if not dsn or asyncpg is None:
        return
    _pool = await asyncpg.create_pool(dsn, min_size=1, max_size=5)

async def close_db_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None

async def get_db_pool():
    """
    FastAPI 依赖用：
    - 若已初始化，返回真实 pool；
    - 否则返回 DummyPool（fetch/fetchrow 返回空，保证接口不 500）。
    """
    global _pool
    if _pool is None:
        try:
            await init_db_pool()
        except Exception:
            pass
    return _pool or _DummyPool()

# -------- Dummy 实现，保证没有数据库也不炸 --------
class _AcquireCtx:
    async def __aenter__(self):
        return _DummyConn()
    async def __aexit__(self, exc_type, exc, tb):
        return False

class _DummyPool:
    def acquire(self):
        return _AcquireCtx()
    async def close(self):
        return None

class _DummyConn:
    async def fetch(self, *args, **kwargs):
        return []
    async def fetchrow(self, *args, **kwargs):
        return None
    async def close(self):
        return None