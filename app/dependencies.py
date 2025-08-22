from fastapi import Request

def get_db_pool(request: Request):
    """
    Return the global async DB pool created in app lifespan.
    Usage in routers: pool = Depends(get_db_pool)
    """
    # 修改: 将 "db_pool" 改为 "pool" 以匹配 main.py 中的实际属性名
    pool = getattr(request.app.state, "pool", None)
    if pool is None:
        raise RuntimeError("DB pool is not initialized on app.state.pool")
    return pool