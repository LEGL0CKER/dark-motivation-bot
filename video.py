"""
Video generation pipeline.
  1. Download a random dark-city background clip from Pexels.
  2. Pick a random music track from the local music/ folder.
  3. Render each quote line as a full-canvas RGBA PNG with Permanent Marker font + gold.
  4. Composite everything with FFmpeg: loop bg, fade-in each line, mix music → 1080×1920 MP4.
"""
import os
import random
import subprocess
import tempfile
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------------------
# Mood presets — paired Pexels queries + music filename keywords
# ---------------------------------------------------------------------------
MOOD_PRESETS = {
    "rain": {
        "queries": [
            "rain window city night",
            "rainy night city street",
            "wet street neon night",
            "dark rain city bokeh",
            "rain drops window dark",
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
        headers=headers,
        params=params,
        timeout=20,
    )
    resp.raise_for_status()
    videos = resp.json().get("videos", [])

    if not videos:
        # Fallback: landscape orientation, page 1
        params["orientation"] = "landscape"
        params["page"] = 1
        resp = requests.get(
            "https://api.pexels.com/videos/search",
            headers=headers,
            params=params,
            timeout=20,
        )
        resp.raise_for_status()
        videos = resp.json().get("videos", [])

    if not videos:
        raise RuntimeError(f"No Pexels videos found for: {query}")

    video = random.choice(videos)
    files = video.get("video_files", [])

    # Prefer portrait files; pick highest resolution
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
# Step 2 — Pick a music track
# ---------------------------------------------------------------------------
def pick_music(config: dict, mood: dict | None = None) -> str:
    """Return path to a mood-matched audio file in the music/ directory."""
    music_dir = Path(config.get("music_dir", "./music"))
    if not music_dir.exists():
        raise FileNotFoundError(
            f"Music folder not found: {music_dir}\n"
            "Create the folder and drop your audio tracks in it."
        )

    extensions = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}
    all_tracks = [f for f in music_dir.iterdir() if f.suffix.lower() in extensions]
    if not all_tracks:
        raise FileNotFoundError(f"No audio files found in {music_dir}")

    if mood:
        keywords = mood["music"]
        matched = [f for f in all_tracks if any(kw in f.stem.lower() for kw in keywords)]
        tracks = matched if matched else all_tracks  # fall back to any track
    else:
        tracks = all_tracks

    chosen = random.choice(tracks)
    print(f"   Music: {chosen.name}")
    return str(chosen)


# ---------------------------------------------------------------------------
# Step 3 — Render text lines as PNGs with Pillow
# ---------------------------------------------------------------------------
def split_into_lines(text: str, max_words: int = 3, min_lines: int = 3) -> list[str]:
    """
    Split quote into visually balanced lines.
    Finds the line count (between min_lines and 6) that produces the most
    even word distribution, then merges any single-word last line up.
    """
    text = text.replace("\\n", "\n").upper()
    words = []
    for raw in text.split("\n"):
        words.extend(raw.strip().split())
    if not words:
        return []

    n = len(words)

    # Find line count with most even distribution (smallest remainder)
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


def auto_font_size(num_lines: int, canvas_h: int = 1920, fill_ratio: float = 0.92) -> int:
    """Calculate font size so all lines fill ~fill_ratio of the canvas height."""
    line_spacing_ratio = 1.4  # line_spacing = font_size * this
    available_h = canvas_h * fill_ratio
    size = int(available_h / (num_lines * line_spacing_ratio))
    return max(60, min(size, 400))  # clamp between 60 and 400


def fit_font_size(
    lines: list[str],
    font_path: str,
    canvas_w: int = 1080,
    canvas_h: int = 1920,
    start_size: int = 0,
    max_w_ratio: float = 0.88,   # lines must fit within 88% of canvas width
) -> tuple[int, "ImageFont.FreeTypeFont"]:
    """
    Return (font_size, font) that fills the screen height while keeping every
    line narrower than canvas_w * max_w_ratio.
    """
    from PIL import ImageFont as _IF, ImageDraw as _ID, Image as _IM
    size = start_size if start_size > 0 else auto_font_size(len(lines), canvas_h)
    max_px = int(canvas_w * max_w_ratio)

    while size > 60:
        font = ImageFont.truetype(font_path, size)
        # Measure widest line
        dummy = _IM.new("RGBA", (1, 1))
        draw  = _ID.Draw(dummy)
        widths = [draw.textbbox((0, 0), l, font=font)[2] for l in lines]
        if max(widths) <= max_px:
            return size, font
        size -= 4   # shrink until it fits

    return size, ImageFont.truetype(font_path, size)


def render_line_images(
    lines: list[str],
    font_path: str,
    font_size: int = 0,       # 0 = auto-size to fill screen
    canvas_w: int = 1080,
    canvas_h: int = 1920,
    text_alpha: int = 153,    # 0–255; 153 ≈ 60 %
) -> tuple[list[str], int]:
    """
    Render ALL lines onto a single transparent 1080×1920 canvas (static overlay).
    Font is auto-sized to fill the screen vertically AND fit within canvas width.
    Returns (list_with_one_png_path, line_spacing_px).
    """
    font_size, font = fit_font_size(lines, font_path, canvas_w, canvas_h, start_size=font_size)

    line_spacing = int(font_size * 1.5)
    total_h = len(lines) * line_spacing
    start_y = (canvas_h - total_h) // 2

    gold   = (255, 215, 0, text_alpha)
    shadow = (0, 0, 0, min(255, int(text_alpha * 0.9)))
    shadow_offset = max(3, font_size // 28)

    img  = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    for i, line in enumerate(lines):
        bbox   = draw.textbbox((0, 0), line, font=font)
        text_w = bbox[2] - bbox[0]
        x = (canvas_w - text_w) // 2
        y = start_y + i * line_spacing
        draw.text((x + shadow_offset, y + shadow_offset), line, font=font, fill=shadow)
        draw.text((x, y), line, font=font, fill=gold)

    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False, prefix="dm_text_")
    img.save(tmp.name, "PNG")
    tmp.close()

    return [tmp.name], line_spacing


# ---------------------------------------------------------------------------
# Step 4 — Composite with FFmpeg
# ---------------------------------------------------------------------------
def generate_video(
    quote: str,
    bg_video: str,
    music: str,
    output: str,
    config: dict,
) -> str:
    """
    Build the final 1080×1920 MP4:
      • loops background video
      • overlays each line with a fade-in, staggered by line_delay seconds
      • mixes music at reduced volume
    """
    font_path = str(Path(config.get("font_path", "./PermanentMarker.ttf")).resolve())
    if not Path(font_path).exists():
        raise FileNotFoundError(
            f"Font file not found: {font_path}\n"
            "Copy PermanentMarker.ttf into the project folder."
        )

    font_size   = int(config.get("font_size", 0))        # 0 = auto-fill screen
    music_vol   = float(config.get("music_volume", 0.25))
    max_words   = int(config.get("words_per_line", 3))
    text_alpha  = int(config.get("text_alpha", 153))     # 153 ≈ 60 %
    total_dur   = float(config.get("video_duration", 15.0))

    lines = split_into_lines(quote, max_words=max_words, min_lines=3)
    if not lines:
        raise ValueError("Quote produced no renderable lines.")

    print(f"   Rendering {len(lines)} lines …")
    png_paths, _ = render_line_images(lines, font_path, font_size, text_alpha=text_alpha)

    # --- Pick a random start point in the music track ---
    music_start = 0.0
    try:
        probe = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                music,
            ],
            capture_output=True, text=True,
        )
        duration = float(probe.stdout.strip())
        max_start = max(0.0, duration - total_dur - 2)
        music_start = random.uniform(0, max_start) if max_start > 0 else 0.0
        print(f"   Music start: {music_start:.1f}s / {duration:.1f}s")
    except Exception:
        pass  # if ffprobe fails, start from 0

    # --- Build FFmpeg command ---
    # Static text: one combined PNG overlaid from t=0
    cmd = ["ffmpeg", "-y"]
    cmd += ["-stream_loop", "-1", "-i", bg_video]                        # input 0
    cmd += ["-ss", str(music_start), "-i", music]                        # input 1
    cmd += ["-loop", "1", "-t", str(total_dur), "-i", png_paths[0]]      # input 2

    # --- filter_complex: scale bg, overlay static text ---
    filter_complex = (
        "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920,format=yuv420p[base];"
        "[base][2:v]overlay=0:0[out]"
    )

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

    # Clean up temp PNGs
    for p in png_paths:
        try:
            os.unlink(p)
        except OSError:
            pass

    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg failed:\n{result.stderr[-3000:]}")

    return output
