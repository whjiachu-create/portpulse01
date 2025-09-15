// fetch-openapi.mjs (Node 18+ 有全局 fetch)
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SITE_DIR   = path.resolve(__dirname, '..');
const STATIC_DIR = path.join(SITE_DIR, 'static');
const OUT        = path.join(STATIC_DIR, 'openapi.json');

// 可通过环境变量覆盖
const OPENAPI_URL = process.env.OPENAPI_URL || 'https://api.useportpulse.com/openapi.json';

(async () => {
  try {
    fs.mkdirSync(STATIC_DIR, {recursive: true});
    const res = await fetch(OPENAPI_URL, {headers: {'Accept': 'application/json'}});
    if (!res.ok) throw new Error(`Fetch failed: ${res.status} ${res.statusText}`);
    const text = await res.text();
    // 基本校验：必须是合法 JSON
    JSON.parse(text);
    fs.writeFileSync(OUT, text);
    console.log(`✅ Saved OpenAPI to ${path.relative(SITE_DIR, OUT)} (${text.length} bytes)`);
  } catch (err) {
    console.error('❌ fetch-openapi failed:', err?.message || err);
    process.exit(1);
  }
})();
