=== PortPulse Database Index Verification ===
DATABASE_URL: postgresql://postgres.lufiwgntwnhbnblzlkxp:Yrds116118!!@aws-1-ap-southeast-1.pooler.supabase.com:6543/postgres?sslmode=require&connect_timeout=10
UNLOCODE    : USLAX

Checking: Latest port snapshot
Expected index: idx_snapshots_unloc_ts_cover (Index Only Scan ideal)
SQL:

SELECT snapshot_ts, vessels, avg_wait_hours, congestion_score
FROM port_snapshots
WHERE unlocode = 'USLAX'
ORDER BY snapshot_ts DESC
LIMIT 1;

--- EXPLAIN ANALYZE ---
                                                                        QUERY PLAN                                                                        
----------------------------------------------------------------------------------------------------------------------------------------------------------
 Limit  (cost=0.14..0.26 rows=1 width=24) (actual time=6.070..6.070 rows=1 loops=1)
   Buffers: shared hit=2
   ->  Index Only Scan using idx_snapshots_unloc_ts_cover on port_snapshots  (cost=0.14..2.71 rows=21 width=24) (actual time=6.068..6.068 rows=1 loops=1)
         Index Cond: (unlocode = 'USLAX'::text)
         Heap Fetches: 0
         Buffers: shared hit=2
 Planning Time: 13.575 ms
 Execution Time: 6.689 ms
(8 rows)


Checking: Dwell recent 14d
Expected index: idx_dwell_unloc_date_cover (Index Only Scan ideal)
SQL:

SELECT date, dwell_hours
FROM port_dwell
WHERE unlocode = 'USLAX'
ORDER BY date DESC
LIMIT 14;

--- EXPLAIN ANALYZE ---
                                                                      QUERY PLAN                                                                      
------------------------------------------------------------------------------------------------------------------------------------------------------
 Limit  (cost=0.27..0.77 rows=14 width=10) (actual time=3.217..3.221 rows=14 loops=1)
   Buffers: shared hit=3
   ->  Index Only Scan using idx_dwell_unloc_date_cover on port_dwell  (cost=0.27..6.72 rows=180 width=10) (actual time=3.216..3.218 rows=14 loops=1)
         Index Cond: (unlocode = 'USLAX'::text)
         Heap Fetches: 0
         Buffers: shared hit=3
 Planning:
   Buffers: shared hit=12 read=1
 Planning Time: 14.938 ms
 Execution Time: 3.258 ms
(10 rows)


✅ Done. 观察上面的 'Index Only Scan using ...' 或 'Index Scan using ...' 行与执行时间。
