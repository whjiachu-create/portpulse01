"""
Minimal sample client for PortPulse API (for demos/tests).
No external deps except 'requests'. MIT-like usage.
"""
from __future__ import annotations
import os, typing as t, requests

class PortPulseClient:
    def __init__(self, api_key: str, base_url: str="https://api.useportpulse.com", timeout: int=15):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({"X-API-Key": api_key, "Accept": "application/json"})
        self.timeout = timeout

    def health(self) -> dict:
        r = self.session.get(f"{self.base_url}/v1/health", timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def trend(self, unlocode: str, days: int = 7, fields: t.Optional[str] = None) -> dict:
        params = {"days": days}
        if fields:
            params["fields"] = fields
        r = self.session.get(f"{self.base_url}/v1/ports/{unlocode}/trend", params=params, timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def trend_csv(self, unlocode: str, days: int = 7, etag: t.Optional[str] = None) -> tuple[int, t.Optional[str], t.Optional[str]]:
        """
        Returns (status, csv_or_none, etag_or_none). If 304, csv is None.
        """
        headers = {"Accept": "text/csv"}
        if etag:
            headers["If-None-Match"] = etag
        r = self.session.get(
            f"{self.base_url}/v1/ports/{unlocode}/trend",
            params={"days": days, "format": "csv"},
            headers=headers, timeout=self.timeout,
        )
        if r.status_code == 304:
            return 304, None, etag
        r.raise_for_status()
        return 200, r.text, r.headers.get("ETag")
