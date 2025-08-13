import os, asyncio, asyncpg
from dotenv import load_dotenv

load_dotenv()  # 读取项目根目录的 .env
DATABASE_URL = os.getenv("DATABASE_URL")

async def main():
    if not DATABASE_URL:
        print("❌ Missing DATABASE_URL in .env")
        return
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        row = await conn.fetchrow("select current_database() as db, now() as ts;")
        await conn.close()
        print("✅ DB OK:", dict(row))
    except Exception as e:
        print("❌ DB FAIL:", repr(e))

if __name__ == "__main__":
    asyncio.run(main())