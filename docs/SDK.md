import requests
class PortPulseClient:
    def __init__(self, api_key, base="https://api.useportpulse.com"):
        self.base, self.h = base, {"X-API-Key": api_key}
    def health(self): return requests.get(f"{self.base}/v1/health").json()
    def trend(self, u, days=7):
        r=requests.get(f"{self.base}/v1/ports/{u}/trend",params={"days":days},headers=self.h); r.raise_for_status(); return r.json()
    def trend_csv(self, u, days=7, etag=None):
        h=dict(self.h)
        if etag: h["If-None-Match"]=etag
        r=requests.get(f"{self.base}/v1/ports/{u}/trend",params={"days":days,"format":"csv"},headers=h)
        return r.status_code, r.text, r.headers.get("etag")

c=PortPulseClient("dev_demo_123")
print("health:", c.health())
t=c.trend("USLAX", 7); print("last3:", t["points"][-3:])
status,csv,et=c.trend_csv("USLAX",7); print("csv status:", status, "etag:", et)
class PortPulse {
  constructor({apiKey, baseUrl="https://api.useportpulse.com"}){ this.apiKey=apiKey; this.baseUrl=baseUrl; }
  async _f(path,{params={},...init}={}) {
    const u=new URL(this.baseUrl+path); Object.entries(params).forEach(([k,v])=>v!=null&&u.searchParams.set(k,v));
    const h=Object.assign({"X-API-Key":this.apiKey,"Accept":"application/json"}, init.headers||{});
    const r=await fetch(u,{...init,headers:h}); if(!r.ok && r.status!==304) throw new Error(`HTTP ${r.status}`);
    return r;
  }
  async health(){ return this._f("/v1/health").then(r=>r.json()); }
  async trend(u,{days=7}={}){ return this._f(`/v1/ports/${u}/trend`,{params:{days}}).then(r=>r.json()); }
  async trendCsv(u,{days=7,etag=null}={}){ 
    const r=await this._f(`/v1/ports/${u}/trend`,{params:{days,format:"csv"},headers:etag?{"If-None-Match":etag}:{}}); 
    return {status:r.status,csv:await r.text(),etag:r.headers.get("etag")}; 
  }
}
// Usage:
// const c = new PortPulse({ apiKey: "dev_demo_123" });
// console.log(await c.health());
// const t = await c.trend("USLAX", {days:7}); console.log("last3", t.points.slice(-3));
// const r = await c.trendCsv("USLAX", {days:7}); console.log("csv status", r.status, "etag:", r.etag);
