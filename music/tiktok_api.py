"""
tiktok_api.py — Post videos directly to TikTok via Content Posting API.

Replaces publer.py. Called from main.py.

Environment variables required (set as GitHub secrets):
    TIKTOK_CLIENT_KEY
    TIKTOK_CLIENT_SECRET
    TIKTOK_REFRESH_TOKEN
    TIKTOK_OPEN_ID
"""

import json
import math
import os
import time
from pathlib import Path

import requests

TOKEN_URL   = "https://open.tiktokapis.com/v2/oauth/token/"
INIT_URL    = "https://open.tiktokapis.com/v2/post/publish/video/init/"
STATUS_URL  = "https://open.tiktokapis.com/v2/post/publish/status/fetch/"

CHUNK_SIZE  = 10 * 1024 * 1024   # 10 MB


# ── Token management ─────────────────────────────────────────────────────────

def refresh_access_token(client_key: str, client_secret: str, refresh_token: str) -> str:
    """Exchange refresh_token for a fresh access_token."""
    resp = requests.post(TOKEN_URL, data={
        "client_key":     client_key,
        "client_secret":  client_secret,
        "grant_type":     "refresh_token",
        "refresh_token":  refresh_token,
    }, headers={"Content-Type": "application/x-www-form-urlencoded"}, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if data.get("error"):
        raise RuntimeError(f"Token refresh failed: {data['error']} — {data.get('error_description','')}")
    print(f"   ✅  Token refreshed (expires in {data.get('expires_in', '?')}s)")
    return data["access_token"]


def get_credentials() -> tuple[str, str, str, str]:
    """Return (client_key, client_secret, refresh_token, open_id) from env or local token file."""
    client_key     = os.environ.get("TIKTOK_CLIENT_KEY", "").strip()
    client_secret  = os.environ.get("TIKTOK_CLIENT_SECRET", "").strip()
    refresh_token  = os.environ.get("TIKTOK_REFRESH_TOKEN", "").strip()
    open_id        = os.environ.get("TIKTOK_OPEN_ID", "").strip()

    # Fall back to local token file (for development)
    if not all([client_key, client_secret, refresh_token, open_id]):
        token_file = Path(__file__).parent / ".tiktok_tokens.json"
        if token_file.exists():
            t = json.loads(token_file.read_text())
            client_key    = client_key    or t.get("client_key", "")
            client_secret = client_secret or t.get("client_secret", "")
            refresh_token = refresh_token or t.get("refresh_token", "")
            open_id       = open_id       or t.get("open_id", "")

    missing = [k for k, v in {
        "TIKTOK_CLIENT_KEY": client_key,
        "TIKTOK_CLIENT_SECRET": client_secret,
        "TIKTOK_REFRESH_TOKEN": refresh_token,
        "TIKTOK_OPEN_ID": open_id,
    }.items() if not v]
    if missing:
        raise EnvironmentError(f"Missing TikTok credentials: {', '.join(missing)}")

    return client_key, client_secret, refresh_token, open_id


# ── Sound selection ──────────────────────────────────────────────────────────

def pick_sound_id(sounds_file: str | Path | None = None) -> str | None:
    """
    Return a weighted-random sound ID from sounds.json, or None to let
    TikTok use the video's original audio.
    """
    import random

    if sounds_file is None:
        sounds_file = Path(__file__).parent / "sounds.json"

    sounds_file = Path(sounds_file)
    if not sounds_file.exists():
        return None

    sounds = json.loads(sounds_file.read_text())
    pool = [s for s in sounds if s.get("score", 0) >= 0 and s.get("id")]
    if not pool:
        return None

    weights = [max(s.get("score", 1), 1) for s in pool]
    chosen  = random.choices(pool, weights=weights, k=1)[0]
    print(f"   🎵  Sound: {chosen.get('name') or chosen['id']} (score={chosen.get('score', '?')})")
    return chosen["id"]


# ── Video upload + post ──────────────────────────────────────────────────────

def _init_post(access_token: str, video_path: str, caption: str, sound_id: str | None) -> tuple[str, str]:
    """
    Call /v2/post/publish/video/init/ → returns (publish_id, upload_url).
    """
    size        = Path(video_path).stat().st_size
    chunk_count = math.ceil(size / CHUNK_SIZE)

    post_info: dict = {
        "title":            caption[:150],   # TikTok max caption length
        "privacy_level":    "PUBLIC_TO_EVERYONE",
        "disable_duet":     False,
        "disable_comment":  False,
        "disable_stitch":   False,
        "video_cover_timestamp_ms": 1000,
    }
    if sound_id:
        post_info["music_id"] = sound_id

    payload = {
        "post_info":   post_info,
        "source_info": {
            "source":            "FILE_UPLOAD",
            "video_size":        size,
            "chunk_size":        CHUNK_SIZE,
            "total_chunk_count": chunk_count,
        },
    }

    resp = requests.post(
        INIT_URL,
        json=payload,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type":  "application/json; charset=UTF-8",
        },
        timeout=30,
    )
    resp.raise_for_status()
    body = resp.json()

    if body.get("error", {}).get("code") not in (None, "ok"):
        raise RuntimeError(f"TikTok init failed: {body['error']}")

    data       = body["data"]
    publish_id = data["publish_id"]
    upload_url = data["upload_url"]
    print(f"   📋  publish_id: {publish_id}")
    return publish_id, upload_url


def _upload_chunks(upload_url: str, video_path: str) -> None:
    """Upload the video in chunks to TikTok's upload URL."""
    size   = Path(video_path).stat().st_size
    chunks = math.ceil(size / CHUNK_SIZE)

    with open(video_path, "rb") as f:
        for i in range(chunks):
            start = i * CHUNK_SIZE
            end   = min(start + CHUNK_SIZE, size) - 1
            data  = f.read(CHUNK_SIZE)

            resp = requests.put(
                upload_url,
                data=data,
                headers={
                    "Content-Range":  f"bytes {start}-{end}/{size}",
                    "Content-Length": str(len(data)),
                    "Content-Type":   "video/mp4",
                },
                timeout=120,
            )
            if resp.status_code not in (200, 201, 206):
                raise RuntimeError(f"Upload chunk {i+1}/{chunks} failed: {resp.status_code} {resp.text[:300]}")
            print(f"   ⬆️   Chunk {i+1}/{chunks} uploaded")


def _wait_for_publish(access_token: str, publish_id: str, max_wait: int = 120) -> None:
    """Poll publish status until PUBLISH_COMPLETE or error."""
    deadline = time.time() + max_wait
    while time.time() < deadline:
        resp = requests.post(
            STATUS_URL,
            json={"publish_id": publish_id},
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type":  "application/json; charset=UTF-8",
            },
            timeout=30,
        )
        resp.raise_for_status()
        body   = resp.json()
        status = body.get("data", {}).get("status", "")
        print(f"   ⏳  Status: {status}")

        if status == "PUBLISH_COMPLETE":
            print("   ✅  Published!")
            return
        if status in ("FAILED", "PUBLISH_FAILED"):
            fail_reason = body.get("data", {}).get("fail_reason", "unknown")
            raise RuntimeError(f"TikTok publish failed: {fail_reason}")

        time.sleep(5)

    raise RuntimeError(f"TikTok publish timed out after {max_wait}s (last status: {status})")


# ── Public entry point ────────────────────────────────────────────────────────

def post_video(video_path: str, caption: str, sounds_file: str | Path | None = None) -> str:
    """
    Full pipeline: refresh token → init → upload → wait for publish.
    Returns the publish_id.
    """
    print("🚀  Posting to TikTok …")

    client_key, client_secret, refresh_token, open_id = get_credentials()
    access_token = refresh_access_token(client_key, client_secret, refresh_token)
    sound_id     = pick_sound_id(sounds_file)

    publish_id, upload_url = _init_post(access_token, video_path, caption, sound_id)
    _upload_chunks(upload_url, video_path)
    _wait_for_publish(access_token, publish_id)

    return publish_id
