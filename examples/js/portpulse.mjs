// Minimal sample client for PortPulse API (ESM). No deps.
export class PortPulseClient {
  constructor({ apiKey, baseUrl = "https://api.useportpulse.com", timeoutMs = 15000 } = {}) {
    this.baseUrl = baseUrl.replace(/\/$/, "");
    this.apiKey = apiKey;
    this.timeoutMs = timeoutMs;
  }
  async _fetch(path, { params = {}, headers = {}, accept = "application/json" } = {}) {
    const url = new URL(this.baseUrl + path);
    for (const [k, v] of Object.entries(params)) if (v != null) url.searchParams.set(k, v);
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), this.timeoutMs);
    const res = await fetch(url, { headers: { "X-API-Key": this.apiKey, "Accept": accept, ...headers }, signal: ctrl.signal });
    clearTimeout(timer);
    if (res.status >= 400 && res.status !== 304) throw new Error(`HTTP ${res.status}: ${await res.text().catch(()=> "")}`);
    return res;
  }
  async health() {
    const r = await this._fetch("/v1/health");
    return r.json();
  }
  async trend(unlocode, { days = 7, fields } = {}) {
    const r = await this._fetch(`/v1/ports/${unlocode}/trend`, { params: { days, ...(fields ? { fields } : {}) } });
    return r.json();
  }
  async trendCsv(unlocode, { days = 7, etag } = {}) {
    const r = await this._fetch(`/v1/ports/${unlocode}/trend`, {
      params: { days, format: "csv" },
      headers: etag ? { "If-None-Match": etag } : {},
      accept: "text/csv"
    });
    if (r.status === 304) return { status: 304, csv: null, etag };
    return { status: 200, csv: await r.text(), etag: r.headers.get("etag") };
  }
}
