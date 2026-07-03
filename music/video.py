"""
Video generation pipeline.
  1. Download a moody dark-city background clip from Pexels.
  2. Keep audio near-silent — TikTok soundId overlay handles the music.
  3. Render each phrase of the quote as a separate PNG with Bebas Neue.
  4. Composite with FFmpeg: phrase-by-phrase reveal → 1080×1920 MP4.
"""
import os
import random
import subprocess
import tempfile
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------------------
# Font — Bebas Neue (auto-downloaded on first run)
# ---------------------------------------------------------------------------
BEBAS_NEUE_PATH = Path(__file__).parent / "BebasNeue-Regular.ttf"
BEBAS_NEUE_URL  = (
    "https://github.com/dharmatype/Bebas-Neue/raw/master/"
    "fonts/BebasNeue(OFL)/TTF/BebasNeue-Regular.ttf"
)


def ensure_font() -> str:
    """Download Bebas Neue Regular if not present. Returns local path."""
    if not BEBAS_NEUE_PATH.exists():
        print("   Downloading Bebas Neue font …")
        r = requests.get(BEBAS_NEUE_URL, timeout=30)
        r.raise_for_status()
        BEBAS_NEUE_PATH.write_bytes(r.content)
        print(f"   Saved → {BEBAS_NEUE_PATH.name}")
    return str(BEBAS_NEUE_PATH)


# ---------------------------------------------------------------------------
# Pexels queries — moody night / rain / atmospheric dark vibes
# ---------------------------------------------------------------------------
MOOD_PRESETS = {
    "rain": {
        "queries": [
            "rain window city night",
            "rainy night city street",
            "wet street neon night",
            "dark rain city bokeh",
            "rain drops window dark",
            "cobblestone street night rain",
            "wet pavement night reflections",
            "rainy street puddle city night",
            "dark alley night rain",
            "rain street lamp night",
        ],
        "music": ["echoes", "cyberpunk", "torn", "vampires", "complicated"],
    },
    "trap": {
        "queries": [
            "dark city night",
            "dark downtown city",
            "city alley night neon",
            "urban street dark night",
            "dark rooftop city night",
            "night street empty dark",
            "dark urban walkway night",
            "empty road night dark",
        ],
        "music": ["thunder", "greed", "lord-knows", "try-me", "trapanomics", "never-going-broke"],
    },
    "epic": {
        "queries": [
            "neon city night skyline",
            "city skyline night dark",
            "skyscraper night dark",
            "urban city night lights",
            "night city aerial dark",
            "dark dramatic sky city",
            "storm clouds dark city",
        ],
        "music": ["epic", "need-for-speed", "greed", "lord-knows"],
    },
}


def pick_mood() -> tuple[str, dict]:
    """Return (mood_name, preset_dict) chosen at random."""
    name = random.choice(list(MOOD_PRESETS.keys()))
    return name, MOOD_PRESETS[name]


# ---------------------------------------------------------------------------
# Step 1 — Download background video from Pexels
# ---------------------------------------------------------------------------
def download_pexels_video(config: dict, mood: dict | None = None) -> str:
    """Download a mood-matched dark-city clip. Returns path to a temp MP4 file."""
    api_key = config.get("pexels_api_key", "").strip()
    if not api_key:
        raise ValueError("pexels_api_key is missing from config.json")

    query_pool = mood["queries"] if mood else [q for p in MOOD_PRESETS.values() for q in p["queries"]]
    query = random.choice(query_pool)
    headers = {"Authorization": api_key}
    params = {
        "query": query,
        "orientation": "portrait",
        "size": "medium",
        "per_page": 20,
        "page": random.randint(1, 3),
    }

    resp = requests.get(
        "https://api.pexels.com/videos/search",
        headers=headers, params=params, timeout=20,
    )
    resp.raise_for_status()
    videos = resp.json().get("videos", [])

    if not videos:
        params["orientation"] = "landscape"
        params["page"] = 1
        resp = requests.get(
            "https://api.pexels.com/videos/search",
            headers=headers, params=params, timeout=20,
        )
        resp.raise_for_status()
        videos = resp.json().get("videos", [])

    if not videos:
        raise RuntimeError(f"No Pexels videos found for: {query}")

    video = random.choice(videos)
    files = video.get("video_files", [])
    portrait = [f for f in files if f.get("height", 0) > f.get("width", 0)]
    pool = portrait if portrait else files
    best = max(pool, key=lambda f: f.get("height", 0) * f.get("width", 0))
    url = best["link"]

    print(f"   Downloading Pexels video (query: '{query}') …")
    tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False, prefix="dm_bg_")
    try:
        with requests.get(url, stream=True, timeout=120) as r:
            r.raise_for_status()
            for chunk in r.iter_content(chunk_size=65_536):
                tmp.write(chunk)
    finally:
        tmp.close()

    return tmp.name


# ---------------------------------------------------------------------------
# Step 2 — Pick a music track (kept silent; TikTok soundId handles audio)
# ---------------------------------------------------------------------------
def pick_music(config: dict, mood: dict | None = None) -> str:
    """Return path to a mood-matched audio file in the music/ directory."""
    music_dir = Path(config.get("music_dir", "./music"))
    if not music_dir.exists():
        raise FileNotFoundError(f"Music folder not found: {music_dir}")

    extensions = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}
    all_tracks = [f for f in music_dir.iterdir() if f.suffix.lower() in extensions]
    if not all_tracks:
        raise FileNotFoundError(f"No audio files found in {music_dir}")

    if mood:
        keywords = mood["music"]
        matched = [f for f in all_tracks if any(kw in f.stem.lower() for kw in keywords)]
        tracks = matched if matched else all_tracks
    else:
        tracks = all_tracks

    chosen = random.choice(tracks)
    print(f"   Music: {chosen.name} (muted — TikTok soundId handles audio)")
    return str(chosen)


# ---------------------------------------------------------------------------
# Step 3 — Render phrase PNGs with Bebas Neue
# ---------------------------------------------------------------------------
def split_into_lines(text: str, max_words: int = 3, min_lines: int = 3) -> list[str]:
    """Split quote into visually balanced ALL-CAPS lines."""
    text = text.replace("\\n", "\n").upper()
    words = []
    for raw in text.split("\n"):
        words.extend(raw.strip().split())
    if not words:
        return []

    n = len(words)
    best_nl = min_lines
    best_rem = n
    for nl in range(min_lines, min(7, n + 1)):
        rem = n % nl
        if rem == 0:
            best_nl = nl
            break
        if rem < best_rem:
            best_rem = rem
            best_nl = nl

    base  = n // best_nl
    extra = n % best_nl
    lines = []
    i = 0
    for l in range(best_nl):
        count = base + (1 if l < extra else 0)
        lines.append(" ".join(words[i:i + count]))
        i += count

    # Never leave a single word stranded on the last line
    if len(lines) > 1 and len(lines[-1].split()) == 1:
        lines[-2] = lines[-2] + " " + lines[-1]
        lines.pop()

    return [l for l in lines if l.strip()]


def _fit_font_for_phrases(
    lines: list[str],
    font_path: str,
    canvas_w: int = 1080,
    canvas_h: int = 1920,
    max_w_ratio: float = 0.90,
    target_h_ratio: float = 0.28,
) -> tuple[int, "ImageFont.FreeTypeFont"]:
    """
    Find the largest font size where every phrase fits within canvas_w * max_w_ratio.
    Starts from target_h_ratio of canvas height.
    """
    from PIL import Image as _IM, ImageDraw as _ID

    start_size = int(canvas_h * target_h_ratio)
    start_size = max(80, min(start_size, 500))
    size = start_size
    max_px = int(canvas_w * max_w_ratio)

    while size > 60:
        font = ImageFont.truetype(font_path, size)
        dummy = _IM.new("RGBA", (1, 1))
        draw  = _ID.Draw(dummy)
        widths = [draw.textbbox((0, 0), l, font=font)[2] for l in lines]
        if max(widths) <= max_px:
            return size, font
        size -= 6

    return size, ImageFont.truetype(font_path, size)


def render_phrase_pngs(
    lines: list[str],
    font_path: str,
    canvas_w: int = 1080,
    canvas_h: int = 1920,
) -> list[str]:
    """
    Render each phrase as its own centered PNG on a transparent canvas.
    All phrases use the same font size (fitted to the widest line).
    Returns list of temp PNG file paths — one per phrase.
    """
    font_size, font = _fit_font_for_phrases(lines, font_path, canvas_w, canvas_h)

    yellow = (255, 226, 52, 255)   # bright yellow, fully opaque
    shadow = (0, 0, 0, 210)
    shadow_offset = max(4, font_size // 16)

    pngs = []
    for line in lines:
        img  = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        bbox   = draw.textbbox((0, 0), line, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        x = (canvas_w - text_w) // 2
        y = (canvas_h - text_h) // 2 - bbox[1]  # correct for ascender offset

        draw.text((x + shadow_offset, y + shadow_offset), line, font=font, fill=shadow)
        draw.text((x, y), line, font=font, fill=yellow)

        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False, prefix="dm_phrase_")
        img.save(tmp.name, "PNG")
        tmp.close()
        pngs.append(tmp.name)

    print(f"   Font size: {font_size}px | {len(lines)} phrases")
    return pngs


# ---------------------------------------------------------------------------
# Step 4 — Composite with FFmpeg (phrase-by-phrase reveal)
# ---------------------------------------------------------------------------
def generate_video(
    quote: str,
    bg_video: str,
    music: str,
    output: str,
    config: dict,
) -> str:
    """
    Build the final 1080×1920 MP4 with phrase-by-phrase text reveal.
    Each phrase is shown centered for an equal time slice, replacing the previous.
    Audio is silent — TikTok's soundId provides the music.
    """
    font_path  = ensure_font()
    music_vol  = float(config.get("music_volume", 0.0))  # 0 = silent; TikTok sound handles audio
    max_words  = int(config.get("words_per_line", 3))
    total_dur  = float(config.get("video_duration", 15.0))

    lines = split_into_lines(quote, max_words=max_words, min_lines=3)
    if not lines:
        raise ValueError("Quote produced no renderable lines.")

    print(f"   Rendering {len(lines)} phrases …")
    png_paths = render_phrase_pngs(lines, font_path)

    # Pick a random start point in the music track
    music_start = 0.0
    try:
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", music],
            capture_output=True, text=True,
        )
        duration    = float(probe.stdout.strip())
        max_start   = max(0.0, duration - total_dur - 2)
        music_start = random.uniform(0, max_start) if max_start > 0 else 0.0
        print(f"   Music start: {music_start:.1f}s / {duration:.1f}s")
    except Exception:
        pass

    # Build FFmpeg command
    # inputs: 0=bg_video, 1=music, 2..N+1=phrase PNGs
    cmd = ["ffmpeg", "-y"]
    cmd += ["-stream_loop", "-1", "-i", bg_video]
    cmd += ["-ss", str(music_start), "-i", music]
    for png in png_paths:
        cmd += ["-loop", "1", "-t", str(total_dur), "-i", png]

    # filter_complex: slightly darken + desaturate bg, then chain phrase overlays
    n = len(png_paths)
    phrase_dur = total_dur / n

    parts = [
        "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920,"
        "eq=brightness=-0.12:saturation=0.75,"
        "format=yuv420p[base]"
    ]

    current = "base"
    for i in range(n):
        t0  = i * phrase_dur
        t1  = (i + 1) * phrase_dur
        inp = i + 2              # inputs: 0=bg, 1=music, 2+=pngs
        nxt = "out" if i == n - 1 else f"v{i}"
        parts.append(
            f"[{current}][{inp}:v]overlay=0:0"
            f":enable='between(t,{t0:.3f},{t1:.3f})'[{nxt}]"
        )
        current = nxt

    filter_complex = ";".join(parts)

    cmd += [
        "-t", str(total_dur),
        "-filter_complex", filter_complex,
        "-map", "[out]",
        "-map", "1:a:0",
        "-af", f"volume={music_vol}",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "22",
        "-c:a", "aac",
        "-b:a", "192k",
        "-movflags", "+faststart",
        output,
    ]

    print("   Running FFmpeg …")
    result = subprocess.run(cmd, capture_output=True, text=True)

    for p in png_paths:
        try:
            os.unlink(p)
        except OSError:
            pass

    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg failed:\n{result.stderr[-3000:]}")

    return output
