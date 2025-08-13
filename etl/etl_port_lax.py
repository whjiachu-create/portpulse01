# etl/etl_port_lax.py  —— 用随机数插一条 LAX 快照（仅用于联调）
import os, datetime as dt, random
import psycopg
from dotenv import load_dotenv
load_dotenv()
DB = os.getenv("DATABASE_URL")

def insert_snapshot(unloc="USLAX", ts=None):
    ts = ts or dt.datetime.utcnow().replace(minute=0, second=0, microsecond=0)
    vessels_in_port = random.randint(10, 20)
    within_40 = max(0, int(random.gauss(12, 3)))
    # 三档占比：和≈1
    a = max(0, random.uniform(0.35, 0.55))
    b = max(0, random.uniform(0.25, 0.45))
    c = max(0, 1 - a - b)
    s = a + b + c
    a, b, c = a/s, b/s, c/s
    gate_fill = min(1, max(0, random.uniform(0.55, 0.85)))

    sql = """
    insert into fact_port_ops(port_unlocode, ts_bucket, vessels_in_port, vessels_within_40nm,
        dwell_0_4_share, dwell_5_8_share, dwell_9p_share, gate_appointment_fill_rate, estimated)
    values (%s,%s,%s,%s,%s,%s,%s,%s,true)
    on conflict (port_unlocode, ts_bucket) do update
      set vessels_in_port=excluded.vessels_in_port,
          vessels_within_40nm=excluded.vessels_within_40nm,
          dwell_0_4_share=excluded.dwell_0_4_share,
          dwell_5_8_share=excluded.dwell_5_8_share,
          dwell_9p_share=excluded.dwell_9p_share,
          gate_appointment_fill_rate=excluded.gate_appointment_fill_rate,
          src_loaded_at=now(),
          estimated=true;
    """
    with psycopg.connect(DB) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (unloc, ts, vessels_in_port, within_40, a, b, c, gate_fill))
            conn.commit()
    print("OK, inserted mock snapshot", ts.isoformat(), unloc)

if __name__ == "__main__":
    insert_snapshot("USLAX")