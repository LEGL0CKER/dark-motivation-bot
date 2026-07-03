#!/usr/bin/env python3
"""
Publer API diagnostic script.
Run: python3 debug_publer.py
"""
import json, requests, time, sys
from pathlib import Path

# ── load config ──────────────────────────────────────────────────────────────
cfg_path = Path(__file__).parent / "config.json"
if not cfg_path.exists():
    sys.exit("config.json not found — run from your dark-motivation-bot folder")
with open(cfg_path) as f:
    config = json.load(f)

BASE = "https://app.publer.com/api/v1"
headers = {
    "Authorization": f"Bearer-API {config['publer_api_key']}",
    "Publer-Workspace-Id": config["publer_workspace_id"],
}

def get(path, params=None):
    r = requests.get(f"{BASE}{path}", headers=headers, params=params, timeout=15)
    print(f"GET {path} → {r.status_code}")
    return r.json()

def post(path, payload):
    h = {**headers, "Content-Type": "application/json"}
    r = requests.post(f"{BASE}{path}", headers=h, json=payload, timeout=30)
    print(f"POST {path} → {r.status_code}")
    return r.json(), r.status_code


# ── 1. Verify accounts ────────────────────────────────────────────────────────
print("\n=== 1. Connected accounts ===")
accounts = get("/accounts")
print(json.dumps(accounts, indent=2))

tiktok_id = config.get("tiktok_account_id", "").strip()
print(f"\nConfig tiktok_account_id: {tiktok_id!r}")


# ── 2. Check existing posts (all states) ─────────────────────────────────────
print("\n=== 2. All posts (last 7 days) ===")
posts_resp = get("/posts", {"state": "all", "from": "2026-06-10", "to": "2026-06-20"})
print(json.dumps(posts_resp, indent=2))


# ── 3. Try creating a DRAFT (no scheduling) to see if post creation works ────
print("\n=== 3. Creating a test DRAFT post ===")
draft_payload = {
    "bulk": {
        "state": "draft",
        "posts": [{
            "networks": {
                "tiktok": {
                    "type": "status",
                    "text": "DEBUG TEST DRAFT — safe to delete",
                }
            },
            "accounts": [{"id": tiktok_id}],
        }]
    }
}
result, status_code = post("/posts/schedule", draft_payload)
print(json.dumps(result, indent=2))

# Poll if we got a job_id
job_id = result.get("job_id") or (result.get("data") or {}).get("job_id")
if job_id:
    print(f"\nPolling job {job_id} …")
    for i in range(10):
        time.sleep(3)
        r = get(f"/job_status/{job_id}")
        print(json.dumps(r, indent=2))
        status = (r.get("data") or r).get("status")
        if status in ("complete", "completed", "failed"):
            break

# ── 4. Check posts again to see if draft appeared ────────────────────────────
print("\n=== 4. Posts after draft attempt ===")
posts_resp2 = get("/posts", {"state": "draft", "from": "2026-06-10", "to": "2026-06-20"})
print(json.dumps(posts_resp2, indent=2))

print("\n=== 5. Failed posts ===")
failed = get("/posts", {"state": "failed", "from": "2026-06-10", "to": "2026-06-20"})
print(json.dumps(failed, indent=2))
