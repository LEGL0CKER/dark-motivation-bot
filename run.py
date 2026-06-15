#!/usr/bin/env python3
"""
Dark Motivation / Money Mindset — Daily Video Bot
================================================
Generates a 9:16 vertical MP4 with a staggered gold-text reveal
over a dark city background, then schedules it to TikTok + Instagram
via the Publer API.

Usage:
  python run.py                         # post at next 8 AM Central
  python run.py --post-time 20:00       # post at next 8 PM Central
  python run.py --dry-run               # generate video only, no posting
  python run.py --output my_clip.mp4    # custom output filename
"""
import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytz

BASE_DIR = Path(__file__).parent


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
def load_config() -> dict:
    path = BASE_DIR / "config.json"
    if not path.exists():
        print(
            "ERROR: config.json not found.\n"
            "Copy config.template.json → config.json and fill in your API keys."
        )
        sys.exit(1)
    with open(path) as f:
        cfg = json.load(f)

    # Resolve relative paths against the project directory
    for key in ("music_dir", "font_path", "output_dir"):
        if key in cfg and not Path(cfg[key]).is_absolute():
            cfg[key] = str(BASE_DIR / cfg[key])

    return cfg


# ---------------------------------------------------------------------------
# Scheduling helper
# ---------------------------------------------------------------------------
def next_post_time(time_str: str) -> str:
    """
    Return the next future occurrence of HH:MM in US Central time
    as an ISO 8601 string (e.g. "2026-06-15T08:00:00-05:00").
    """
    central = pytz.timezone("America/Chicago")
    now = datetime.now(central)
    h, m = map(int, time_str.split(":"))
    target = now.replace(hour=h, minute=m, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return target.isoformat()


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Dark motivation video bot")
    parser.add_argument(
        "--post-time",
        default="08:00",
        help="Schedule time in Central time: 08:00 (8 AM) or 20:00 (8 PM)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate the video but do not post to social media",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output filename (saved inside output/ folder)",
    )
    args = parser.parse_args()

    config = load_config()

    # ---- lazy imports (keep startup fast) ----
    from quotes import get_quote
    from video import download_pexels_video, generate_video, pick_mood, pick_music
    from publer import upload_and_schedule

    print("\n🎬  Dark Motivation Bot — starting pipeline\n")

    # 1. Quote
    print("📝  Fetching quote …")
    quote = get_quote(config)
    display = quote[:90] + ("…" if len(quote) > 90 else "")
    print(f"    {display}\n")

    # Pick a mood that pairs background + music
    mood_name, mood = pick_mood()
    print(f"🎨  Mood: {mood_name}\n")

    # 2. Background video
    print("🌃  Downloading background video …")
    bg_path = download_pexels_video(config, mood=mood)
    print(f"    Saved to: {bg_path}\n")

    # 3. Music
    print("🎵  Selecting music …")
    music_path = pick_music(config, mood=mood)
    print()

    # 4. Generate video
    output_dir = Path(config.get("output_dir", BASE_DIR / "output"))
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.output:
        out_file = output_dir / args.output
    else:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_file = output_dir / f"dark_motivation_{ts}.mp4"

    print("🎞️   Compositing video …")
    generate_video(quote, bg_path, music_path, str(out_file), config)
    print(f"    Saved: {out_file}\n")

    # Clean up downloaded background clip
    try:
        os.unlink(bg_path)
    except OSError:
        pass

    if args.dry_run:
        print(f"✅  Dry run complete. Video at:\n    {out_file}\n")
        return

    # 5. Schedule via Publer
    print("📤  Scheduling via Publer …")
    scheduled_at = next_post_time(args.post_time)
    upload_and_schedule(str(out_file), quote, scheduled_at, config)
    print(f"    Scheduled for {scheduled_at}\n")

    print("✅  Done!\n")


if __name__ == "__main__":
    main()
