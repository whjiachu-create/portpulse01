# SDK Samples（Python / JS）

## Python（pip 安装 requests）

```python
import requests

class PortPulseClient:
    def __init__(self, api_key, base_url="https://api.useportpulse.com"):
        self.base = base_url
        self.key  = api_key
        self.h    = {"X-API-Key": api_key}

    def health(self):
        return requests.get(f"{self.base}/v1/health").json()

    def trend(self, unlocode, days=7):
        r = requests.get(f"{self.base}/v1/ports/{unlocode}/trend",
                         params={"days": days}, headers=self.h)
        r.raise_for_status()
        return r.json()

    def trend_csv(self, unlocode, days=7, etag=None):
        headers = dict(self.h)
        if etag: headers["If-None-Match"] = etag
        r = requests.get(f"{self.base}/v1/ports/{unlocode}/trend",
                         params={"days": days, "format": "csv"},
                         headers=headers)
        return r.status_code, r.text, r.headers.get("etag")

if __name__ == "__main__":
    c = PortPulseClient("dev_demo_123")
    print("health:", c.health())
    t = c.trend("USLAX", 7); print("last3:", t["points"][-3:])
    status, csv, et = c.trend_csv("USLAX", 7); print("csv status:", status, "etag:", et)
class PortPulse {
  constructor({ apiKey, baseUrl="https://api.useportpulse.com" }) {
    this.apiKey  = apiKey;
    this.baseUrl = baseUrl;
  }
  async _fetch(path, { params={}, ...init }={}) {
    const url = new URL(this.baseUrl + path);
    Object.entries(params).forEach(([k,v]) => v!=null && url.searchParams.set(k, v));
    const headers = Object.assign(
      {"X-API-Key": this.apiKey, "Accept": "application/json"},
      init.headers||{}
    );
    const res = await fetch(url, { ...init, headers });
    if (!res.ok && res.status !== 304) {
      throw new Error(`HTTP ${res.status}: ${await res.text().catch(()=>"...")}`);
    }
    return res;
  }
  async health() {
    const r = await this._fetch("/v1/health");
    return r.json();
  }
  async trend(unlocode, { days=7 }={}) {
    const r = await this._fetch(`/v1/ports/${unlocode}/trend`, { params:{days} });
    return r.json();
  }
  async trendCsv(unlocode, { days=7, etag=null }={}) {
    const r = await this._fetch(`/v1/ports/${unlocode}/trend`,
      { params:{days, format:"csv"}, headers: etag ? {"If-None-Match": etag} : {} });
    return { status: r.status, csv: await r.text(), etag: r.headers.get("etag") };
  }
}

// 使用示例：
// const c = new PortPulse({ apiKey: "dev_demo_123" });
// console.log(await c.health());
// const t = await c.trend("USLAX", {days:7}); console.log("last3", t.points.slice(-3));
// const r = await c.trendCsv("USLAX", {days:7}); console.log("csv status", r.status, "etag:", r.etag);
