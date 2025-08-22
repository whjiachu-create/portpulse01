# app/dependencies.py
from app.deps import get_db_pool  # 从 app.deps 导入 get_db_pool
__all__ = ["get_db_pool"]

async def get_db_pool(request: Request) -> Pool:
    """
    Return the asyncpg pool stored on app.state.
    main.py 应在 startup 时初始化：app.state.pool = asyncpg.create_pool(...)
    """
    pool = getattr(request.app.state, "pool", None)
    if pool is None:
        raise RuntimeError("DB pool not initialized; check startup hooks")
    return pool