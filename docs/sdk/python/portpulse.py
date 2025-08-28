import os, requests

class PortPulseClient:
    def __init__(self, base_url="https://api.useportpulse.com", api_key=None, timeout=15):
        self.base = base_url.rstrip("/")
        self.key  = api_key or os.getenv("PP_KEY", "dev_demo_123")
        self.s = requests.Session()
        if self.key:
            self.s.headers.update({"X-API-Key": self.key})

    def health(self):
        return requests.get(f"{self.base}/v1/health", timeout=10).json()

    def trend(self, unlocode, days=7):
        r = self.s.get(f"{self.base}/v1/ports/{unlocode}/trend",
                       params={"days": days}, timeout=10)
        r.raise_for_status()
        return r.json()

    def trend_csv(self, unlocode, days=7, etag=None):
        headers = {}
        if etag: headers["If-None-Match"] = etag
        r = self.s.get(f"{self.base}/v1/ports/{unlocode}/trend",
                       params={"days": days, "format": "csv"},
                       headers=headers, timeout=10)
        return r.status_code, r.text, r.headers.get("etag")
