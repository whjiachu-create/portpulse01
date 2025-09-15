#!/usr/bin/env bash
set -euo pipefail

BASE="${1:-http://127.0.0.1:8090}"

echo "==> HEAD $BASE/"
curl -sI "$BASE/" | sed -n '1,20p' | tee /tmp/headers_home.txt >/dev/null

echo "==> HEAD $BASE/openapi.json"
curl -sI "$BASE/openapi.json" | sed -n '1,40p' | tee /tmp/headers_openapi.txt >/dev/null

# 断言 content-type
ctype=$(curl -sI "$BASE/openapi.json" | tr -d '\r' | awk -F': ' 'tolower($1)=="content-type"{print tolower($2)}' | head -n1)
if [[ "$ctype" != application/json* ]]; then
  echo "❌ openapi.json content-type not JSON (got: $ctype)"
  exit 1
else
  echo "✅ openapi.json content-type ok ($ctype)"
fi

# 断言缓存策略（本地静态构建为 max-age=3600，线上 CF Transform 可覆写）
grep -qi '^cache-control: .*max-age=3600' /tmp/headers_openapi.txt \
  || { echo "❌ openapi.json cache-control missing max-age=3600"; exit 1; }

# 断言 CORS 暴露头
grep -qi '^access-control-expose-headers: .*ETag' /tmp/headers_openapi.txt \
  || { echo "❌ access-control-expose-headers missing ETag"; exit 1; }

echo "✅ docs headers OK"