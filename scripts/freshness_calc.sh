#!/usr/bin/env bash
set -euo pipefail

: "${BASE:?BASE not set}"
: "${API_KEY:?API_KEY not set}"

# 输出目录（与验收脚本一致）
: "${OUT:=backups/$(date -u +%Y%m%dT%H%M%SZ)}"
mkdir -p "$OUT"/{openapi,metrics,data}
fresh_csv="$OUT/metrics/freshness.csv"
echo "port,delta_sec,ts" > "$fresh_csv"

# 端内小函数：稳健解析“秒差”
py_delta() {
  # $1 = ISO8601 或 YYYY-MM-DD
  python3 - "$1" <<'PY' || true
import sys, re, datetime as dt
def fail(): print(999999); raise SystemExit(0)
s = (sys.argv[1] if len(sys.argv)>1 else "").strip()
if not s or s=="null": fail()

# 归一化：Z -> +0000；+HH:MM -> +HHMM
if s.endswith('Z'):
    s = s[:-1] + '+0000'
else:
    s = re.sub(r'([+-]\d{2}):(\d{2})$', r'\1\2', s)

try:
    if 'T' not in s:
        t = dt.datetime.strptime(s, '%Y-%m-%d').replace(tzinfo=dt.timezone.utc)
    else:
        t = None
        for f in ('%Y-%m-%dT%H:%M:%S.%f%z','%Y-%m-%dT%H:%M:%S%z'):
            try:
                t = dt.datetime.strptime(s, f)
                break
            except Exception:
                pass
        if t is None:
            fail()
    now = dt.datetime.now(dt.timezone.utc)
    print(int((now - t).total_seconds()))
except Exception:
    fail()
PY
}

# 端口集合（与验收脚本一致）
PORTS=(USLAX USLGB USNYC USSAV USCHS USORF USHOU USSEA USOAK USMIA NLRTM BEANR DEHAM DEBRV FRLEH GBFXT GBLGP ESVLC ESALG GRPIR CNSHA CNNGB CNSZX CNTAO KRPUS SGSIN MYTPP THLCH INNSA INMUN)

TH=7200   # 2 小时
fail_fresh=0

echo "[G] freshness <=2h..."
for p in "${PORTS[@]}"; do
  # 轻微退避重试防 429（本地你已 DISABLE_RATELIMIT=1，但留着更健壮）
  body=""
  for attempt in 1 2 3; do
    code=$(curl -s -w "%{http_code}" -H "X-API-Key: $API_KEY" \
      "$BASE/v1/ports/$p/trend?days=30" -o /tmp/pp.$p.json || echo 000)
    if [ "$code" = "200" ]; then
      body=$(cat /tmp/pp.$p.json); break
    elif [ "$code" = "429" ]; then
      sleep $((attempt*1))
    else
      echo "  -> $p ❌ http=$code"; body=""; break
    fi
  done

  ts=$(printf '%s' "$body" | jq -r '(.as_of // ._as_of_bucket // (.points|sort_by(.date)|last.date // empty)) // empty')
  if [ -z "$ts" ] || [ "$ts" = "null" ]; then
    echo "  -> $p ❌ no as_of/_as_of_bucket/date"
    echo "$p,999999," >> "$fresh_csv"
    fail_fresh=$((fail_fresh+1))
    continue
  fi

  delta=$(py_delta "$ts")
  printf "%-6s freshness=%ss %s (ts=%s)\n" "$p" "$delta" $([ "$delta" -le "$TH" ] && echo "✅" || echo "❌") "$ts"
  echo "$p,$delta,$ts" >> "$fresh_csv"
  [ "$delta" -le "$TH" ] || fail_fresh=$((fail_fresh+1))
  sleep 0.1
done

# 统计 p95（排除 999999 的错误样本）
p95=$(awk -F, 'NR>1 && $2!="" && $2!=999999 {print $2}' "$fresh_csv" \
      | sort -n | awk 'NF{a[NR]=$1} END{if(NR==0){print 999999}else{idx=int(0.95*NR+0.999); if(idx<1) idx=1; print a[idx]}}')

echo "freshness p95 (sec)=$p95"

if [ "$p95" -le "$TH" ]; then
  echo "✅ freshness OK (p95=$p95)"
  exit 0
else
  echo "❌ freshness failed (p95=$p95)"
  exit 6
fi
