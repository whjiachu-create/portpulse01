#!/usr/bin/env node
import http from "http";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const buildDir = path.resolve(__dirname, "..", "build");
const port = process.env.DOCS_PORT || 8090;

const server = http.createServer((req, res) => {
  // 301 -> /openapi
  if (req.url === "/redoc.html") {
    res.statusCode = 200;
    res.setHeader("Content-Type", "text/html; charset=UTF-8");
    res.end('<meta http-equiv="refresh" content="0; url=/openapi">');
    return;
  }
  // 为 /openapi.json 注入响应头
  if (req.url === "/openapi.json") {
    const p = path.join(buildDir, "openapi.json");
    if (!fs.existsSync(p)) { res.statusCode = 404; return res.end("Not Found"); }
    const stat = fs.statSync(p);
    const body = fs.readFileSync(p);
    res.statusCode = 200;
    res.setHeader("Content-Type", "application/json; charset=UTF-8");
    res.setHeader("Cache-Control", "public, max-age=3600, must-revalidate");
    res.setHeader("ETag", `W/"${stat.ino}-${stat.size}-${stat.mtime.toISOString()}"`);
    res.setHeader("Access-Control-Allow-Origin", "*");
    res.setHeader("Access-Control-Expose-Headers", "ETag, Content-Length, Content-Type");
    res.end(body);
    return;
  }
  // 静态文件
  let filePath = path.join(buildDir, req.url === "/" ? "index.html" : req.url);
  if (!fs.existsSync(filePath) && !path.extname(filePath)) {
    filePath = path.join(buildDir, req.url, "index.html"); // 支持目录
  }
  if (fs.existsSync(filePath) && fs.statSync(filePath).isFile()) {
    const ext = path.extname(filePath).toLowerCase();
    const type = ext === ".html" ? "text/html; charset=UTF-8"
      : ext === ".json" ? "application/json; charset=UTF-8"
      : ext === ".js" ? "application/javascript; charset=UTF-8"
      : ext === ".css" ? "text/css; charset=UTF-8"
      : "application/octet-stream";
    res.statusCode = 200;
    res.setHeader("Content-Type", type);
    if (ext !== ".html") res.setHeader("Cache-Control", "max-age=3600");
    res.end(fs.readFileSync(filePath));
  } else {
    res.statusCode = 404; res.end("Not Found");
  }
});

server.listen(port, () => {
  console.log(`Docs dev server -> http://127.0.0.1:${port}`);
});