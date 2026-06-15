#!/usr/bin/env python3
"""
Helper: print all Publer connected social account IDs.

Run this once after filling in publer_api_key and publer_workspace_id
in config.json. Copy the TikTok and Instagram account IDs into config.json.

Usage:
  python get_account_ids.py
"""
import json
import sys
from pathlib import Path

import requests

BASE_DIR = Path(__file__).parent


def main():
    cfg_path = BASE_DIR / "config.json"
    if not cfg_path.exists():
        print("ERROR: config.json not found. Copy config.template.json first.")
        sys.exit(1)

    with open(cfg_path) as f:
        config = json.load(f)

    headers = {
        "Authorization":       f"Bearer-API {config['publer_api_key']}",
        "Publer-Workspace-Id": config["publer_workspace_id"],
    }

    resp = requests.get(
        "https://app.publer.com/api/v1/accounts",
        headers=headers,
        timeout=15,
    )

    if not resp.ok:
        print(f"ERROR [{resp.status_code}]: {resp.text}")
        sys.exit(1)

    accounts = resp.json()

    if not accounts:
        print("No connected accounts found. Connect TikTok + Instagram in Publer first.")
        return

    print(f"\nFound {len(accounts)} connected account(s):\n")
    print(f"{'Platform':<20} {'Name':<30} {'ID'}")
    print("-" * 80)
    for acct in accounts:
        platform = acct.get("provider", "unknown").capitalize()
        name     = acct.get("name", "")
        acct_id  = acct.get("id", "")
        print(f"{platform:<20} {name:<30} {acct_id}")

    print(
        "\nCopy the TikTok and Instagram IDs into your config.json as:\n"
        '  "tiktok_account_id":    "<id>"\n'
        '  "instagram_account_id": "<id>"\n'
    )


if __name__ == "__main__":
    main()
