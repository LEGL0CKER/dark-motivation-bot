#!/usr/bin/env python3
"""
Run this once from Terminal to fill your music/ folder with
royalty-free dark trap / cinematic beats from Mixkit.

Usage:  cd ~/Documents/dark-motivation-bot/music && python3 download_tracks.py
"""
import os
import urllib.request

TRACKS = [
    # --- Dark cinematic & atmospheric (rain mood) ---
    ("echoes-dark-cinematic.mp3",         "https://assets.mixkit.co/music/188/188.mp3"),
    ("cyberpunk-city-eerie.mp3",          "https://assets.mixkit.co/music/140/140.mp3"),
    ("vampires-in-the-city.mp3",          "https://assets.mixkit.co/music/892/892.mp3"),
    ("torn-threads-mysterious.mp3",       "https://assets.mixkit.co/music/573/573.mp3"),
    ("complicated-tension.mp3",           "https://assets.mixkit.co/music/281/281.mp3"),
    ("dark-mystery-suspense.mp3",         "https://assets.mixkit.co/music/470/470.mp3"),
    ("black-hole-cinematic.mp3",          "https://assets.mixkit.co/music/502/502.mp3"),
    ("cold-night-atmospheric.mp3",        "https://assets.mixkit.co/music/556/556.mp3"),
    ("deep-urban-mystery.mp3",            "https://assets.mixkit.co/music/620/620.mp3"),
    ("rain-shadows-ambient.mp3",          "https://assets.mixkit.co/music/677/677.mp3"),

    # --- Dark trap / hip-hop beats (trap mood) ---
    ("thunder-dark-trap.mp3",             "https://assets.mixkit.co/music/318/318.mp3"),
    ("greed-crime-mystery.mp3",           "https://assets.mixkit.co/music/404/404.mp3"),
    ("lord-knows-determined.mp3",         "https://assets.mixkit.co/music/293/293.mp3"),
    ("try-me-confident.mp3",              "https://assets.mixkit.co/music/235/235.mp3"),
    ("trapanomics-city-dark.mp3",         "https://assets.mixkit.co/music/283/283.mp3"),
    ("never-going-broke.mp3",             "https://assets.mixkit.co/music/304/304.mp3"),
    ("street-trap-dark.mp3",              "https://assets.mixkit.co/music/350/350.mp3"),
    ("cold-trap-hustle.mp3",              "https://assets.mixkit.co/music/386/386.mp3"),
    ("midnight-trap-beat.mp3",            "https://assets.mixkit.co/music/415/415.mp3"),
    ("dark-money-trap.mp3",               "https://assets.mixkit.co/music/447/447.mp3"),
    ("ruthless-trap-hit.mp3",             "https://assets.mixkit.co/music/488/488.mp3"),
    ("city-night-trap.mp3",               "https://assets.mixkit.co/music/519/519.mp3"),

    # --- Epic / cinematic builds (epic mood) ---
    ("epic-games-dramatic.mp3",           "https://assets.mixkit.co/music/76/76.mp3"),
    ("need-for-speed-dark.mp3",           "https://assets.mixkit.co/music/369/369.mp3"),
    ("rise-of-an-empire.mp3",             "https://assets.mixkit.co/music/98/98.mp3"),
    ("dark-hero-epic.mp3",                "https://assets.mixkit.co/music/112/112.mp3"),
    ("relentless-power-build.mp3",        "https://assets.mixkit.co/music/134/134.mp3"),
    ("cinematic-dark-rise.mp3",           "https://assets.mixkit.co/music/157/157.mp3"),
    ("unstoppable-force.mp3",             "https://assets.mixkit.co/music/201/201.mp3"),
    ("kingdom-builder-epic.mp3",          "https://assets.mixkit.co/music/228/228.mp3"),
    ("dark-triumph-cinematic.mp3",        "https://assets.mixkit.co/music/257/257.mp3"),
    ("final-stand-dramatic.mp3",          "https://assets.mixkit.co/music/312/312.mp3"),
]

SAVE_DIR = os.path.dirname(os.path.abspath(__file__))

print(f"\n  Downloading {len(TRACKS)} tracks into: {SAVE_DIR}\n")

headers = {"User-Agent": "Mozilla/5.0"}
ok = 0
failed = 0

for filename, url in TRACKS:
    dest = os.path.join(SAVE_DIR, filename)
    if os.path.exists(dest):
        print(f"  already exists  {filename}")
        ok += 1
        continue
    print(f"  downloading     {filename} ...", end=" ", flush=True)
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as r, open(dest, "wb") as f:
            f.write(r.read())
        size_kb = os.path.getsize(dest) // 1024
        if size_kb < 10:
            os.unlink(dest)
            print(f"SKIPPED (invalid file, {size_kb}KB)")
            failed += 1
        else:
            print(f"{size_kb} KB  OK")
            ok += 1
    except Exception as e:
        print(f"FAILED: {e}")
        failed += 1

print(f"\n  Done: {ok} tracks ready, {failed} failed/skipped.\n")
