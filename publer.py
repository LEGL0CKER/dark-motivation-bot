"""
Publer API integration.
  1. Upload video file → get media_id
  2. Schedule post to TikTok and/or Instagram accounts
"""
import time
import requests
from pathlib import Path

BASE_URL = "https://app.publer.com/api/v1"

TIKTOK_HASHTAGS = (
    "#darkmotivation #moneymindset #motivation #success #grind "
    "#millionairemindset #hustle #wealthy #focusedmindset #fyp"
)


def _headers(config: dict) -> dict:
    return {
        "Authorization": f"Bearer-API {config['publer_api_key']}",
        "Publer-Workspace-Id": config["publer_workspace_id"],
    }


def build_caption(quote: str, config: dict) -> str:
    """Build TikTok caption: quote + hashtags (max 2200 chars)."""
    custom_hashtags = config.get("hashtags", TIKTOK_HASHTAGS)
    caption = f"{quote}\n\n{custom_hashtags}"
    return caption[:2200]


# ---------------------------------------------------------------------------
# Media upload
# ---------------------------------------------------------------------------
def upload_media(video_path: str, config: dict) -> dict:
    """
    Upload a video file to Publer.
    Returns the full media response dict (contains 'id', 'type', etc.).
    Max size via direct upload: 200 MB.
    """
    url = f"{BASE_URL}/media"
    headers = _headers(config)

    print(f"   Uploading {Path(video_path).name} to Publer …")
    with open(video_path, "rb") as fh:
        resp = requests.post(
            url,
            headers=headers,
            files={"file": (Path(video_path).name, fh, "video/mp4")},
            timeout=300,
        )

    if not resp.ok:
        raise RuntimeError(
            f"Publer media upload failed [{resp.status_code}]: {resp.text}"
        )
    data = resp.json()
    print(f"   [DEBUG] Media upload response: {data}")
    return data


# ---------------------------------------------------------------------------
# Job status polling
# ---------------------------------------------------------------------------
def poll_job(job_id: str, config: dict, max_wait: int = 120) -> dict:
    """Poll /job_status/{job_id} until complete or timeout."""
    url = f"{BASE_URL}/job_status/{job_id}"
    headers = _headers(config)
    for _ in range(max_wait // 3):
        time.sleep(3)
        resp = requests.get(url, headers=headers, timeout=15)
        if not resp.ok:
            raise RuntimeError(f"Job status check failed [{resp.status_code}]: {resp.text}")
        data = resp.json()
        print(f"   [DEBUG] Job status response: {data}")
        # Publer returns: {"success": true, "data": {"status": "...", "result": {"status": "...", "payload": {"failures": {}}}}}
        # or sometimes bare: {"status": "..."}
        data_block  = data.get("data") or data
        result      = data_block.get("result") or {}
        # Status can be at data level or result level
        status = data_block.get("status") or result.get("status")
        if status in ("complete", "completed"):
            # Check for failures at both levels
            payload  = result.get("payload") or data_block.get("payload") or {}
            failures = payload.get("failures")
            if failures:
                raise RuntimeError(f"Publer job completed with failures: {failures}")
            # Also check plan.locked
            plan = result.get("plan") or {}
            if plan.get("locked"):
                raise RuntimeError("Publer workspace is locked — check your plan.")
            return data
        if status == "failed":
            raise RuntimeError(f"Publer job failed: {data}")
    raise TimeoutError(f"Publer job {job_id} did not complete within {max_wait}s")


# ---------------------------------------------------------------------------
# Schedule post
# ---------------------------------------------------------------------------
def schedule_post(
    media: dict,
    caption: str,
    scheduled_at: str,
    config: dict,
) -> dict:
    """
    Schedule a video post to TikTok and/or Instagram via Publer.

    Args:
        media:        The full media object returned by upload_media().
        caption:      Post caption / description.
        scheduled_at: ISO 8601 timestamp, e.g. "2026-06-15T08:00:00-05:00"
        config:       Loaded config.json dict.
    """
    media_id = media["id"]

    # Publer media reference — just id + type
    media_obj = {"id": media_id, "type": "video"}

    tiktok_id    = config.get("tiktok_account_id", "").strip()
    instagram_id = config.get("instagram_account_id", "").strip()

    posts = []

    if tiktok_id:
        posts.append({
            "networks": {
                "tiktok": {
                    "type": "video",
                    "text": caption,
                    "media": [media_obj],
                    "details": {
                        "privacy": "PUBLIC_TO_EVERYONE",
                        "comment": True,
                        "duet": True,
                        "stitch": True,
                    },
                }
            },
            "accounts": [{"id": tiktok_id, "scheduled_at": scheduled_at}],
        })

    if instagram_id:
        posts.append({
            "networks": {
                "instagram": {
                    "type": "video",
                    "text": caption,
                    "media": [media_obj],
                }
            },
            "accounts": [{"id": instagram_id, "scheduled_at": scheduled_at}],
        })

    if not posts:
        raise ValueError(
            "No account IDs found in config.json. "
            "Run `python3 get_account_ids.py` and add tiktok_account_id to config.json."
        )

    payload = {"bulk": {"state": "scheduled", "posts": posts}}

    url = f"{BASE_URL}/posts/schedule"
    headers = _headers(config)
    headers["Content-Type"] = "application/json"

    print(f"   Scheduling post for {scheduled_at} …")
    print(f"   [DEBUG] Schedule payload: {payload}")
    resp = requests.post(url, headers=headers, json=payload, timeout=30)

    if not resp.ok:
        raise RuntimeError(
            f"Publer schedule failed [{resp.status_code}]: {resp.text}"
        )

    result = resp.json()
    print(f"   [DEBUG] Schedule response: {result}")

    # Handle async response (job_id)
    job_id = result.get("job_id")
    if job_id:
        print(f"   Waiting for Publer job {job_id} …")
        result = poll_job(job_id, config)

    print(f"   [DEBUG] Final result: {result}")
    return result


# ---------------------------------------------------------------------------
# Full flow helper
# ---------------------------------------------------------------------------
def upload_and_schedule(
    video_path: str,
    quote: str,
    scheduled_at: str,
    config: dict,
) -> dict:
    """Upload video then schedule the post. Returns Publer API response."""
    caption = build_caption(quote, config)
    media   = upload_media(video_path, config)
    print(f"   Media uploaded → id: {media['id']}")
    result  = schedule_post(media, caption, scheduled_at, config)
    return result
