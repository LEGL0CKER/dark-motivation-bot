#!/usr/bin/env python3
"""
update_sounds.py — scrape sound IDs from trending dark motivation TikTok videos.

Run once a month:
    cd ~/Documents/dark-motivation-bot && python3 update_sounds.py

What it does:
  1. Opens TikTok search results for dark motivation / money mindset hashtags.
  2. Extracts the sound IDs being used by trending videos in your niche.
  3. Saves to sounds.json and pushes to GitHub.
"""

import json, re, subprocess, sys, time
from pathlib import Path

SOUNDS_FILE = Path(__file__).parent / "sounds.json"
REPO_DIR    = Path(__file__).parent

# Hashtags to search — niche + general viral
SEARCH_TERMS = [
    # Your niche
    "darkmotivation",
    "moneymindset",
    "motivationquotes",
    "successmindset",
    "grindmotivation",
    # General viral
    "fyp",
    "viral",
    "trending",
    "foryou",
    "tiktoktrending",
]


def _ensure_playwright():
    try:
        import playwright  # noqa: F401
    except ImportError:
        print("📦  Installing Playwright …")
        subprocess.run([sys.executable, "-m", "pip", "install", "playwright",
                        "--break-system-packages", "-q"], check=True)
    subprocess.run([sys.executable, "-m", "playwright", "install", "chromium", "--with-deps"],
                   capture_output=True)

_ensure_playwright()
from playwright.sync_api import sync_playwright  # noqa: E402


def scrape_sounds() -> list[dict]:
    all_sounds: list[dict] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False, slow_mo=30)
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()

        # Intercept TikTok API responses for sound/music data
        def on_response(response):
            url = response.url
            if response.status == 200 and "tiktok.com" in url and (
                "music" in url or "sound" in url or "item_list" in url
                or "search" in url or "tag" in url
            ):
                try:
                    body = response.json()
                    _dig(body, all_sounds)
                except Exception:
                    pass

        page.on("response", on_response)

        # First: open TikTok and let user log in if needed
        print("\n🌐  Opening TikTok …")
        page.goto("https://www.tiktok.com", wait_until="domcontentloaded", timeout=20_000)
        time.sleep(3)

        print("\n" + "="*55)
        print("  TikTok is open in the browser window.")
        print("  If you see a login prompt, dismiss it (click X).")
        print("  You do NOT need to be logged in for this to work.")
        print("="*55)
        input("\n  Press Enter when TikTok has loaded ▶ ")

        # Search each hashtag
        for term in SEARCH_TERMS:
            url = f"https://www.tiktok.com/tag/{term}"
            print(f"\n🔍  Scraping #{term} …")
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=20_000)
                time.sleep(3)
                # Scroll to load videos
                for _ in range(4):
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    time.sleep(1.5)
                # Extract sound links from page
                _extract_from_page(page, all_sounds)
            except Exception as e:
                print(f"   Error on #{term}: {e}")

        browser.close()

    return all_sounds


def _dig(obj, out: list):
    """Recursively find music/sound objects in TikTok API responses."""
    if isinstance(obj, dict):
        # TikTok API shape: music.id or music.playUrl
        music = obj.get("music") or obj.get("sound") or {}
        if isinstance(music, dict):
            sid  = str(music.get("id") or "")
            name = str(music.get("title") or music.get("authorName") or "")
            if sid.isdigit() and len(sid) >= 10:
                if not any(s["id"] == sid for s in out):
                    out.append({"id": sid, "name": name.strip()})
        # Also check direct id fields
        sid  = str(obj.get("id") or "")
        name = str(obj.get("title") or obj.get("name") or "")
        if sid.isdigit() and len(sid) >= 15 and "title" in obj:
            if not any(s["id"] == sid for s in out):
                out.append({"id": sid, "name": name.strip()})
        for v in obj.values():
            _dig(v, out)
    elif isinstance(obj, list):
        for item in obj:
            _dig(item, out)


def _extract_from_page(page, out: list):
    """Extract sound IDs from TikTok video cards on a hashtag page."""
    try:
        # Method 1: look for sound links in page HTML
        content = page.content()
        # TikTok sound URLs: /music/title-1234567890123
        for m in re.finditer(r'/music/[^"\'?\s]+-(\d{10,})', content):
            sid = m.group(1)
            if not any(s["id"] == sid for s in out):
                out.append({"id": sid, "name": ""})

        # Method 2: look for musicId in page data
        for m in re.finditer(r'"musicId"\s*:\s*"(\d{10,})"', content):
            sid = m.group(1)
            if not any(s["id"] == sid for s in out):
                out.append({"id": sid, "name": ""})

        # Method 3: NEXT_DATA embedded JSON
        m = re.search(r'<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__"[^>]*>(.*?)</script>', content, re.DOTALL)
        if m:
            try:
                data = json.loads(m.group(1))
                _dig(data, out)
            except Exception:
                pass

    except Exception as e:
        print(f"   Page extract error: {e}")


def main():
    print("🎵  TikTok Trending Sounds Updater (niche scraper)")
    print("=" * 50)

    sounds = scrape_sounds()

    # Deduplicate
    seen, unique = set(), []
    for s in sounds:
        if s["id"] not in seen:
            seen.add(s["id"])
            unique.append(s)
    sounds = unique

    if not sounds:
        print("\n❌  No sounds found.")
        print("   TikTok may have changed their page structure.")
        sys.exit(1)

    print(f"\n✅  Found {len(sounds)} sounds:")
    for s in sounds[:15]:
        print(f"   {s['name'] or '(no name)':40s}  {s['id']}")
    if len(sounds) > 15:
        print(f"   … and {len(sounds) - 15} more")

    with open(SOUNDS_FILE, "w") as f:
        json.dump(sounds, f, indent=2, ensure_ascii=False)
    print(f"\n💾  Saved {len(sounds)} sounds → {SOUNDS_FILE.name}")

    try:
        subprocess.run(["git", "add", "sounds.json"], cwd=REPO_DIR, check=True)
        r = subprocess.run(
            ["git", "commit", "-m", f"Update trending sounds ({len(sounds)} tracks)"],
            cwd=REPO_DIR, capture_output=True, text=True,
        )
        if "nothing to commit" in r.stdout + r.stderr:
            print("ℹ️   sounds.json unchanged.")
        else:
            subprocess.run(["git", "push"], cwd=REPO_DIR, check=True)
            print("🚀  Pushed to GitHub!")
    except subprocess.CalledProcessError as e:
        print(f"⚠️   Git error: {e}")


if __name__ == "__main__":
    main()
