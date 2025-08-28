export class PortPulseClient {
  constructor({ baseUrl="https://api.useportpulse.com", apiKey="dev_demo_123", timeout=15000 } = {}) {
    this.baseUrl = baseUrl.replace(/\/$/, "");
    this.apiKey  = apiKey;
    this.timeout = timeout;
  }
  async _fetch(path, { params={}, headers={}, accept="application/json" } = {}) {
    const u = new URL(this.baseUrl + path);
    for (const [k,v] of Object.entries(params)) if (v != null) u.searchParams.set(k, v);
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), this.timeout);
    const res = await fetch(u, { headers: { "X-API-Key": this.apiKey, "Accept": accept, ...headers }, signal: ctrl.signal });
    clearTimeout(t);
    if (res.status >= 400 && res.status !== 304) throw new Error(`HTTP ${res.status}`);
    return res;
  }
  async health() {
    const r = await fetch(this.baseUrl + "/v1/health");
    return r.json();
  }
  async trend(unlocode, { days=7 } = {}) {
    const r = await this._fetch(`/v1/ports/${unlocode}/trend`, { params: { days } });
    return r.json();
  }
  async trendCsv(unlocode, { days=7, etag } = {}) {
    const r = await this._fetch(`/v1/ports/${unlocode}/trend`, {
      params: { days, format: "csv" },
      headers: etag ? { "If-None-Match": etag } : {},
      accept: "text/csv",
    });
    return { status: r.status, csv: await r.text(), etag: r.headers.get("etag") };
  }
}
