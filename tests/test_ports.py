# tests/test_ports.py
import os, pytest, httpx

BASE = os.getenv("BASE_URL", "https://api.useportpulse.com")
API_KEY = os.getenv("API_KEY", "dev_key_123")

HDRS = {"X-API-Key": API_KEY, "Accept": "application/json"}

@pytest.mark.parametrize("unlocode", ["USLAX", "USNYC"])
def test_snapshot(unlocode):
    r = httpx.get(f"{BASE}/v1/ports/{unlocode}/snapshot", headers=HDRS, timeout=20)
    r.raise_for_status()
    j = r.json()
    assert j["unlocode"] == unlocode
    assert "snapshot" in j  # 允许为 None，但键必须存在

def test_dwell_never_500():
    r = httpx.get(f"{BASE}/v1/ports/USLAX/dwell?days=14", headers=HDRS, timeout=20)
    r.raise_for_status()
    j = r.json()
    assert j["unlocode"] == "USLAX"
    assert isinstance(j["points"], list)

def test_overview_csv():
    r = httpx.get(f"{BASE}/v1/ports/USLAX/overview?format=csv", headers={"X-API-Key": API_KEY}, timeout=20)
    r.raise_for_status()
    text = r.text.strip().splitlines()
    assert text[0].startswith("unlocode,as_of,vessels,avg_wait_hours,congestion_score")

def test_alerts_window_ok():
    r = httpx.get(f"{BASE}/v1/ports/USNYC/alerts?window=14d", headers=HDRS, timeout=20)
    r.raise_for_status()
    j = r.json()
    assert j["unlocode"] == "USNYC"
    assert "alerts" in j

def test_trend_fields_subset():
    r = httpx.get(f"{BASE}/v1/ports/USLAX/trend?days=30&fields=vessels,avg_wait_hours&limit=30&offset=0", headers=HDRS, timeout=20)
    r.raise_for_status()
    j = r.json()
    assert j["unlocode"] == "USLAX"
    assert all(set(p.keys()) >= {"date","src","vessels","avg_wait_hours"} for p in j.get("points", []))