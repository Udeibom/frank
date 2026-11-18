"""
Render operations for Frank's backend (ship-it spec 13). Reads RENDER_API_KEY from backend/.env.

  python scripts/ops/render.py wait            wait until the deploy of the current git HEAD is live (or failed)
  python scripts/ops/render.py logs [minutes]  server and build logs, without health/poll noise
  python scripts/ops/render.py events          recent service events (deploys, out-of-memory kills)
  python scripts/ops/render.py env KEY=VALUE   set environment variables and redeploy
"""
from __future__ import annotations

import datetime as dt
import pathlib
import subprocess
import sys
import time

import httpx
from dotenv import dotenv_values

ROOT = pathlib.Path(__file__).resolve().parents[2]
ENV = dotenv_values(ROOT / ".env")
H = {"Authorization": f"Bearer {ENV['RENDER_API_KEY']}", "Accept": "application/json"}
SERVICE = "srv-dbtv8e0n74is73evdbdg"
OWNER = "tea-d2rince3jp1c73fkrol0"
BASE = f"https://api.render.com/v1/services/{SERVICE}"


def events(n: int = 6) -> None:
    for x in httpx.get(f"{BASE}/events?limit={n}", headers=H, timeout=30).json():
        e = x["event"]
        print("EVENT", e["timestamp"][11:19], e["type"], str(e.get("details"))[:140])


def logs(minutes: int = 15) -> None:
    start = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=minutes)).isoformat()
    params = {"ownerId": OWNER, "resource": SERVICE, "limit": 100, "direction": "forward", "startTime": start}
    for _ in range(30):
        r = httpx.get("https://api.render.com/v1/logs", headers=H, params=params, timeout=30).json()
        for line in r.get("logs", []):
            if "GET /health" not in line["message"] and "/status HTTP" not in line["message"]:
                print(line["timestamp"][11:19], line["message"][:220])
        if not r.get("hasMore"):
            break
        params["startTime"] = r["nextStartTime"]


def wait() -> None:
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip()
    status = "unknown"
    for _ in range(80):
        d = httpx.get(f"{BASE}/deploys?limit=1", headers=H, timeout=30).json()[0]["deploy"]
        status = d["status"]
        if d["commit"]["id"] == head and status in ("live", "build_failed", "update_failed", "canceled", "deactivated"):
            print(status, head[:7])
            return
        time.sleep(15)
    print("timeout", status)


def set_env(pairs: list[str]) -> None:
    for kv in pairs:
        k, v = kv.split("=", 1)
        print(k, httpx.put(f"{BASE}/env-vars/{k}", headers=H, json={"value": v}, timeout=30).status_code)
    print("deploy", httpx.post(f"{BASE}/deploys", headers=H, json={"clearCache": "do_not_clear"}, timeout=30).status_code)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "events"
    if cmd == "wait":
        wait()
    elif cmd == "logs":
        events(4)
        logs(int(sys.argv[2]) if len(sys.argv) > 2 else 15)
    elif cmd == "env":
        set_env(sys.argv[2:])
    else:
        events()
