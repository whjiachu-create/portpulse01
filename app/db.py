import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine

# 读取环境变量（本地默认走 SQLite）
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./dev.db").strip()

# SQLAlchemy 2.x 风格的异步引擎
engine: AsyncEngine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,  # 探活
    future=True,
)
