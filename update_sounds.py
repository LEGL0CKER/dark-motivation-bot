#!/usr/bin/env python3
"""
update_sounds.py — fetch trending TikTok sounds from Creative Center.

Run once a month:
    cd ~/Documents/dark-motivation-bot && python3 update_sounds.py

What it does:
  1. Opens TikTok Creative Center in a real browser window.
  2. If you're not logged in, it waits while you log in.
  3. Intercepts the API response that loads the trending music list.
  4. Saves the sound IDs to sounds.json and pushes to GitHub.
"""

import json
import subprocess
import sys
import time
from pathlib import Path

SOUNDS_FILE = Path(__file__).parent / "sounds.json"
REPO_DIR    = Path(__file__).parent

CC_URL = (
    "https://ads.tiktok.com/business/creativecenter/"
    "inspiration/popular/music/pc/en"
)

# Keywords that fit the dark motivation / money mindset niche.
# Sounds whose titles contain any of these are kept; all others still kept
# but ranked lower (we just dump everything and let run.py pick randomly).
NICHE_KEYWORDS = [
    "dark", "trap", "drill", "motivat", "hustle", "grind", "money",
    "empire", "epic", "cinematic", "power", "rise", "king", "boss",
    "night", "city", "rain", "cold", "deep", "mystery", "shadow",
]


# ---------------------------------------------------------------------------
# Auto-install Playwright if missing
# ---------------------------------------------------------------------------
def _ensure_playwright():
    try:
        import playwright  # noqa: F401
    except ImportError:
        print("📦  Installing Playwright …")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "playwright",
             "--break-system-packages", "-q"],
            check=True,
        )
    # Ensure Chromium binary exists
    result = subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium", "--with-deps"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        # Already installed is fine
        pass


_ensure_playwright()
from playwright.sync_api import sync_playwright  # noqa: E402


# ---------------------------------------------------------------------------
# Scrape
# ---------------------------------------------------------------------------
def fetch_sounds() -> list[dict]:
    captured: list[dict] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False, slow_mo=50)
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()

        # ── Intercept Creative Center music API responses ──────────────────
        def handle_response(response):
            url = response.url
            if (
                "creativecenter" in url
                and ("music" in url or "song" in url or "audio" in url)
                and response.status == 200
            ):
                try:
                    body = response.json()
                    _extract_sounds(body, captured)
                except Exception:
                    pass

        page.on("response", handle_response)

        # ── Navigate ───────────────────────────────────────────────────────
        print("\n🌐  Opening TikTok Creative Center …")
        page.goto(CC_URL, wait_until="domcontentloaded", timeout=30_000)

        # Wait to see if login is required
        time.sleep(4)

        # If redirected to a login page, pause for the user
        if any(kw in page.url for kw in ("login", "signup", "passport")):
            print("\n🔐  Please log in to TikTok in the browser window.")
            print("    Press Enter here once you're logged in …")
            input()
            page.goto(CC_URL, wait_until="domcontentloaded", timeout=30_000)
            time.sleep(4)

        print("⏳  Loading sounds (scrolling page) …")

        # Scroll a few times to trigger more API calls / lazy-load
        for _ in range(6):
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(1.5)

        # Also try clicking "Load more" buttons if present
        for selector in ["text=Load more", "text=See more", "[data-e2e='load-more']"]:
            try:
                btn = page.locator(selector).first
                if btn.is_visible():
                    btn.click()
                    time.sleep(2)
            except Exception:
                pass

        # Give a moment for any final API calls to complete
        time.sleep(3)

        # ── Fallback: extract from DOM if API interception got nothing ─────
        if not captured:
            print("ℹ️   API interception empty — trying DOM extraction …")
            captured = _dom_extract(page)

        browser.close()

    return captured


def _extract_sounds(body: dict, out: list):
    """Recursively hunt for sound/music objects in an API response."""
    if isinstance(body, dict):
        # Common Creative Center response shapes
        for key in ("data", "music_list", "list", "items", "result", "music"):
            if key in body:
                _extract_sounds(body[key], out)
        # A leaf node that looks like a sound
        if "music_id" in body or "song_id" in body or "id" in body:
            sid = (
                str(body.get("music_id") or body.get("song_id") or body.get("id", ""))
            )
            name = (
                body.get("music_title")
                or body.get("song_name")
                or body.get("title")
                or body.get("name")
                or ""
            )
            if sid.isdigit() and len(sid) >= 10:
                if not any(s["id"] == sid for s in out):
                    out.append({"id": sid, "name": str(name).strip()})
    elif isinstance(body, list):
        for item in body:
            _extract_sounds(item, out)


def _dom_extract(page) -> list[dict]:
    """Last-resort: pull music IDs out of anchor hrefs on the page."""
    sounds = []
    try:
        hrefs = page.eval_on_selector_all(
            "a[href*='/music/']",
            "els => els.map(e => ({href: e.href, text: e.innerText}))",
        )
        for item in hrefs:
            href = item.get("href", "")
            # TikTok music URLs end with a numeric ID: /music/title-1234567890
            parts = href.rstrip("/").split("-")
            sid = parts[-1].split("?")[0] if parts else ""
            if sid.isdigit() and len(sid) >= 10:
                name = item.get("text", "").strip()
                if not any(s["id"] == sid for s in sounds):
                    sounds.append({"id": sid, "name": name})
    except Exception as e:
        print(f"   DOM extract error: {e}")
    return sounds


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("🎵  TikTok Trending Sounds Updater")
    print("=" * 40)

    sounds = fetch_sounds()

    if not sounds:
        print("\n❌  No sounds found.")
        print("   The Creative Center page structure may have changed.")
        print("   Keeping existing sounds.json unchanged.")
        sys.exit(1)

    # Score: niche-relevant sounds first
    def score(s):
        name_lower = s["name"].lower()
        return sum(1 for kw in NICHE_KEYWORDS if kw in name_lower)

    sounds.sort(key=score, reverse=True)

    print(f"\n✅  Found {len(sounds)} sounds. Top matches:")
    for s in sounds[:10]:
        print(f"   [{score(s)} pts] {s['name']}  (id: {s['id']})")

    # Save
    with open(SOUNDS_FILE, "w") as f:
        json.dump(sounds, f, indent=2, ensure_ascii=False)
    print(f"\n💾  Saved {len(sounds)} sounds → {SOUNDS_FILE.name}")

    # Git push
    try:
        subprocess.run(["git", "add", "sounds.json"], cwd=REPO_DIR, check=True)
        result = subprocess.run(
            ["git", "commit", "-m", f"Update trending sounds ({len(sounds)} tracks)"],
            cwd=REPO_DIR, capture_output=True, text=True,
        )
        if "nothing to commit" in result.stdout + result.stderr:
            print("ℹ️   sounds.json unchanged — nothing to push.")
        else:
            subprocess.run(["git", "push"], cwd=REPO_DIR, check=True)
            print("🚀  Pushed to GitHub!")
    except subprocess.CalledProcessError as e:
        print(f"⚠️   Git error: {e} — sounds.json saved locally but not pushed.")
        print("    Run `git add sounds.json && git commit -m 'Update sounds' && git push` manually.")


if __name__ == "__main__":
    main()
