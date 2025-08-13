import os, datetime as dt
import psycopg
from dotenv import load_dotenv
from etl.etl_port_lax import insert_snapshot

load_dotenv()
DB = os.getenv("DATABASE_URL")

def run():
    # 1) 插入一条 USLAX 快照（mock）
    insert_snapshot("USLAX")
    # 2) 刷新物化视图，产出 congestion_score
    with psycopg.connect(DB) as conn:
        with conn.cursor() as cur:
            cur.execute("refresh materialized view agg_port_congestion;")
            conn.commit()
    print("OK port_lax_job", dt.datetime.utcnow().isoformat()+"Z")

if __name__ == "__main__":
    run()