#!/usr/bin/env python3
"""
Run this to find your correct Publer workspace ID.
Usage: python3 get_workspace_id.py
"""
import json, sys, requests
from pathlib import Path

BASE_DIR = Path(__file__).parent

with open(BASE_DIR / "config.json") as f:
    config = json.load(f)

headers = {"Authorization": f"Bearer-API {config['publer_api_key']}"}

resp = requests.get("https://app.publer.com/api/v1/workspaces", headers=headers, timeout=15)

if not resp.ok:
    print(f"ERROR [{resp.status_code}]: {resp.text}")
    sys.exit(1)

workspaces = resp.json()
print(f"\nFound {len(workspaces)} workspace(s):\n")
for w in workspaces:
    print(f"  Name: {w.get('name', '')}")
    print(f"  ID:   {w.get('id', '')}\n")

print("Copy the correct ID into config.json as \"publer_workspace_id\"")
