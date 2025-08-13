# etl/etl_uncomtrade.py —— 稳定版：按“年”取月度数据，JSON 解析，含退避重试
import os, sys, time, requests, datetime as dt
import psycopg
from dotenv import load_dotenv

load_dotenv()
DB = os.getenv("DATABASE_URL")

HS_LIST = ["4202", "9401"]
COUNTRY_ISO3 = "US"
REPORTER = 842          # US
FLOW = 1                # imports
PARTNER = 0             # world
BASE = "https://comtrade.un.org/api/get"

def years_between(frm: str, to: str):
    y0 = dt.date.fromisoformat(frm).year
    y1 = dt.date.fromisoformat(to).year
    return list(range(y0, y1 + 1))

def fetch_year_json(hs: str, year: int):
    params = {
        "max": 50000, "type": "C", "freq": "M", "px": "HS",
        "ps": str(year),            # 关键点：用“年份”而不是具体月份
        "r": REPORTER, "p": PARTNER, "rg": FLOW,
        "cc": hs, "fmt": "json"
    }
    # 简单退避：最多 3 次
    for i in range(3):
        r = requests.get(BASE, params=params, timeout=60)
        if r.status_code == 429:      # 限流就等待后重试
            time.sleep(2 * (i + 1));  continue
        if r.ok:
            try:
                data = r.json()
                ds = data.get("dataset") or data.get("Dataset") or []
                return ds
            except Exception:
                pass
        # 非 ok/解析失败，短暂等待再试
        time.sleep(1.5)
    return []  # 最终失败

def upsert_rows(rows):
    sql = """
      insert into fact_trade_monthly(country_iso3, hs_code, period, value_usd, src)
      values (%s,%s,%s,%s,'un_comtrade')
      on conflict (country_iso3, hs_code, period)
      do update set value_usd=excluded.value_usd, src_loaded_at=now();
    """
    with psycopg.connect(DB) as conn:
        with conn.cursor() as cur:
            cur.executemany(sql, rows)
            conn.commit()

def run(frm="2024-01-01", to="2024-12-01"):
    years = years_between(frm, to)
    total = 0
    for hs in HS_LIST:
        for y in years:
            ds = fetch_year_json(hs, y)
            if not ds:
                print(f"⚠️ {hs} {y} 无数据（或接口限制）");  continue
            rows = []
            for rec in ds:
                try:
                    # Period 形如 "202401" → 月度
                    per = str(rec.get("Period") or rec.get("period") or "")
                    if len(per) != 6: 
                        continue
                    y_, m_ = int(per[:4]), int(per[4:])
                    period = dt.date(y_, m_, 1)
                    val = float(rec.get("TradeValue") or rec.get("tradeValue") or 0)
                    rows.append((COUNTRY_ISO3, hs, period, val))
                except Exception:
                    continue
            if rows:
                upsert_rows(rows); total += len(rows)
            time.sleep(1)  # 友好点
    print(f"✅ upsert rows: {total}") if total else print("⚠️ 无任何入库")

if __name__ == "__main__":
    frm = sys.argv[1] if len(sys.argv) > 1 else "2024-01-01"
    to  = sys.argv[2] if len(sys.argv) > 2 else "2024-12-01"
    run(frm, to)