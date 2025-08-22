from fastapi import Request

def get_db_pool(request: Request):
    """
    Return the global async DB pool created in app lifespan.
    Routers can use: pool = Depends(get_db_pool)
    """
    pool = getattr(request.app.state, "db_pool", None)
    if pool is None:
        # 明确报错，便于排查启动阶段未初始化连接池的问题
        raise RuntimeError("DB pool is not initialized on app.state.db_pool")
    return pool