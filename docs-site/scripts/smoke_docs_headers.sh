#!/usr/bin/env bash
set -euo pipefail

BASE="${1:-http://127.0.0.1:8090}"

echo "==> HEAD $BASE/"
curl -sI "$BASE/" | sed -n '1,20p' | tee /tmp/headers_home.txt >/dev/null

echo "==> HEAD $BASE/openapi.json"
curl -sI "$BASE/openapi.json" | sed -n '1,40p' | tee /tmp/headers_openapi.txt >/dev/null

# 断言 content-type 为 JSON
grep -qi '^content-type: application/json' /tmp/headers_openapi.txt \
  || { echo "❌ openapi.json content-type not JSON"; exit 1; }

# 断言缓存策略（本地构建 max-age=3600；线上由 CF Transform Rule 覆盖）
grep -qi '^cache-control: .*max-age=3600' /tmp/headers_openapi.txt \
  || { echo "❌ openapi.json cache-control missing max-age=3600"; exit 1; }

# 断言 CORS 暴露头（便于工具读取 ETag/长度/类型）
grep -qi '^access-control-expose-headers: .*ETag' /tmp/headers_openapi.txt \
  || { echo "❌ access-control-expose-headers missing ETag"; exit 1; }

echo "✅ docs headers OK"
