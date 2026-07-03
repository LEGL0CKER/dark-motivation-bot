#!/usr/bin/env python3
"""
setup_tiktok_auth.py — One-time TikTok OAuth setup.

Run this once from your terminal:
    cd ~/Documents/dark-motivation-bot/music
    TIKTOK_CLIENT_KEY=<your_key> TIKTOK_CLIENT_SECRET=<your_secret> python3 setup_tiktok_auth.py

It will:
  1. Open TikTok OAuth in your browser
  2. Ask you to paste the code shown on the callback page
  3. Exchange the code for tokens
  4. Print the values to add as GitHub secrets
"""

import hashlib
import json
import os
import secrets
import urllib.parse
import webbrowser
from pathlib import Path

import requests

# ── Config ──────────────────────────────────────────────────────────────────
REDIRECT_URI  = "https://legl0cker.github.io/dark-motivation-bot/music/callback.html"
SCOPES        = "user.info.basic,video.publish,video.upload"
AUTH_URL      = "https://www.tiktok.com/v2/auth/authorize/"
TOKEN_URL     = "https://open.tiktokapis.com/v2/oauth/token/"
TOKENS_FILE   = Path(__file__).parent / ".tiktok_tokens.json"

# ── Credentials ─────────────────────────────────────────────────────────────
CLIENT_KEY    = os.environ.get("TIKTOK_CLIENT_KEY", "").strip()
CLIENT_SECRET = os.environ.get("TIKTOK_CLIENT_SECRET", "").strip()

if not CLIENT_KEY:
    CLIENT_KEY = input("Paste your TikTok Client Key: ").strip()
if not CLIENT_SECRET:
    CLIENT_SECRET = input("Paste your TikTok Client Secret: ").strip()

print(f"\n   Key read:    '{CLIENT_KEY}'")
print(f"   Secret read: '{CLIENT_SECRET[:6]}…'\n")
if not CLIENT_KEY or not CLIENT_SECRET:
    print("❌  One or both credentials are empty. Re-run and paste carefully.")
    raise SystemExit(1)

# ── Step 1: Build OAuth URL ──────────────────────────────────────────────────
state = secrets.token_urlsafe(16)
# PKCE
code_verifier  = secrets.token_urlsafe(64)
code_challenge = hashlib.sha256(code_verifier.encode()).hexdigest()

params = {
    "client_key":             CLIENT_KEY,
    "redirect_uri":           REDIRECT_URI,
    "response_type":          "code",
    "scope":                  SCOPES,
    "state":                  state,
    "code_challenge":         code_challenge,
    "code_challenge_method":  "S256",
}
auth_url = AUTH_URL + "?" + urllib.parse.urlencode(params)

print("\n" + "="*60)
print("  Opening TikTok authorization in your browser …")
print("="*60)
print(f"\n  URL: {auth_url}\n")
webbrowser.open(auth_url)

print("After you approve, you'll be redirected to the callback page.")
print("The page will show a big yellow authorization code.\n")
code = input("Paste the code here: ").strip()

if not code:
    print("❌  No code provided. Exiting.")
    raise SystemExit(1)

# ── Step 2: Exchange code for tokens ────────────────────────────────────────
print("\n🔄  Exchanging code for tokens …")
resp = requests.post(TOKEN_URL, data={
    "client_key":     CLIENT_KEY,
    "client_secret":  CLIENT_SECRET,
    "code":           code,
    "grant_type":     "authorization_code",
    "redirect_uri":   REDIRECT_URI,
    "code_verifier":  code_verifier,
}, headers={"Content-Type": "application/x-www-form-urlencoded"}, timeout=30)

resp.raise_for_status()
data = resp.json()

if data.get("error"):
    print(f"❌  TikTok error: {data['error']} — {data.get('error_description', '')}")
    raise SystemExit(1)

access_token   = data["access_token"]
refresh_token  = data["refresh_token"]
open_id        = data["open_id"]
expires_in     = data.get("expires_in", 86400)
refresh_expiry = data.get("refresh_expires_in", 31536000)

# ── Step 3: Save locally ─────────────────────────────────────────────────────
TOKENS_FILE.write_text(json.dumps({
    "access_token":   access_token,
    "refresh_token":  refresh_token,
    "open_id":        open_id,
    "client_key":     CLIENT_KEY,
    "client_secret":  CLIENT_SECRET,
}, indent=2))
print(f"💾  Tokens saved → {TOKENS_FILE.name}")

# ── Step 4: Print GitHub secrets ─────────────────────────────────────────────
print("\n" + "="*60)
print("  Add these as GitHub repository secrets:")
print("  (Settings → Secrets and variables → Actions → New secret)")
print("="*60)
print(f"\n  TIKTOK_CLIENT_KEY     = {CLIENT_KEY}")
print(f"  TIKTOK_CLIENT_SECRET  = {CLIENT_SECRET}")
print(f"  TIKTOK_REFRESH_TOKEN  = {refresh_token}")
print(f"  TIKTOK_OPEN_ID        = {open_id}")
print(f"\n  Access token expires in: {expires_in}s (~{expires_in//3600}h)")
print(f"  Refresh token expires in: {refresh_expiry//86400} days")
print("\n✅  Done! You won't need to run this again for ~365 days.")
