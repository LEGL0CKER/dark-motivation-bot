#!/usr/bin/env python3
"""
One-time migration: score + filter the existing sounds.json.
Run once from your repo root:
    python3 migrate_sounds.py
"""
import json
from pathlib import Path
from collections import Counter

SOUNDS_FILE = Path(__file__).parent / "sounds.json"

GOOD_KW = [
    "dark", "trap", "drill", "epic", "cinematic", "motivation", "hustle",
    "grind", "boss", "empire", "rise", "power", "night", "city", "cold",
    "deep", "rain", "thunder", "storm", "shadow", "silent", "alpha",
    "ruthless", "focus", "discipline", "money", "wealth", "ambition",
    "menacing", "aggressive", "intense", "hard", "savage", "beast",
]
BAD_KW = [
    "funny", "comedy", "cute", "love", "baby", "dance", "pop", "happy",
    "sunshine", "laugh", "meme", "joke", "cartoon", "kids", "silly",
    "romantic", "country", "christmas", "holiday", "birthday", "wedding",
    "anime", "kawaii", "girly", "princess",
]


def score_sound(sound: dict) -> int:
    name = (sound.get("name") or "").lower()
    for kw in BAD_KW:
        if kw in name:
            return -1
    score = 0
    for kw in GOOD_KW:
        if kw in name:
            score += 2
    if not name or "original sound" in name:
        return max(score, 0)
    return max(score, 1)


def main():
    if not SOUNDS_FILE.exists():
        print("❌  sounds.json not found — run from your dark-motivation-bot folder")
        return

    with open(SOUNDS_FILE) as f:
        sounds = json.load(f)

    print(f"📂  Loaded {len(sounds)} sounds")

    # Add score + source if missing
    for s in sounds:
        if "score" not in s:
            s["score"] = score_sound(s)
        if "source" not in s:
            s["source"] = "unknown"

    excluded = [s for s in sounds if s["score"] < 0]
    usable   = [s for s in sounds if s["score"] >= 0]

    # Stats
    dist = Counter(s["score"] for s in usable)
    print(f"\n📊  Score breakdown:")
    for sc in sorted(dist):
        label = {0: "unknown (no name/original sound)", 1: "named, no keyword match"}.get(sc, f"good keyword match (score {sc})")
        print(f"   score={sc:2d}: {dist[sc]:4d} sounds — {label}")

    print(f"\n🚫  Excluded (bad keywords): {len(excluded)}")
    if excluded:
        for s in excluded[:10]:
            print(f"   {s['name']}")
        if len(excluded) > 10:
            print(f"   … and {len(excluded) - 10} more")

    top = sorted(usable, key=lambda s: s["score"], reverse=True)
    print(f"\n🎯  Top 20 sounds by score:")
    for s in top[:20]:
        print(f"   [{s['score']:2d}] {s['name'] or '(no name)':45s}  {s['id']}")

    print(f"\n✅  Keeping {len(usable)} usable sounds (was {len(sounds)})")
    confirm = input("   Save filtered sounds.json? [y/N] ").strip().lower()
    if confirm == "y":
        with open(SOUNDS_FILE, "w") as f:
            json.dump(usable, f, indent=2, ensure_ascii=False)
        print(f"💾  Saved {len(usable)} sounds → sounds.json")
        print("   Run: git add sounds.json && git commit -m 'Filter and score sounds' && git push")
    else:
        print("   Cancelled — sounds.json unchanged.")


if __name__ == "__main__":
    main()
