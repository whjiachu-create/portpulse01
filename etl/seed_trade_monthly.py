# etl/seed_trade_monthly.py  —— 只用于开发联调的示例数据
import os, datetime as dt
import psycopg
from dotenv import load_dotenv

load_dotenv()
DB = os.getenv("DATABASE_URL")

def gen_rows():
    rows = []
    # 造 2024 年 12 个月：4202/9401 两个 HS
    for hs, base in [("4202", 120_000_000), ("9401", 90_000_000)]:
        for m in range(1, 12 + 1):
            period = dt.date(2024, m, 1)
            # 简单的递增趋势（仅为演示用）
            val = base + m * 1_000_000
            rows.append(("US", hs, period, float(val)))
    return rows

def run():
    rows = gen_rows()
    sql = """
    insert into fact_trade_monthly(country_iso3, hs_code, period, value_usd, src)
    values (%s,%s,%s,%s,'seed')
    on conflict (country_iso3, hs_code, period)
    do update set value_usd=excluded.value_usd, src=excluded.src, src_loaded_at=now();
    """
    with psycopg.connect(DB) as conn:
        with conn.cursor() as cur:
            cur.executemany(sql, rows)
            conn.commit()
    print(f"✅ seed rows inserted: {len(rows)}")

if __name__ == "__main__":
    run()