#!/bin/bash
# ============================================================
# Dark Motivation Bot — One-time setup script (Mac)
# Run this once from the project folder: bash setup.sh
# ============================================================

set -e
cd "$(dirname "$0")"

echo ""
echo "=== Dark Motivation Bot — Setup ==="
echo ""

# 1. Python deps
echo "[1/4] Installing Python dependencies..."
pip3 install -r requirements.txt --break-system-packages -q || pip3 install -r requirements.txt -q
echo "      Done."

# 2. FFmpeg check
echo "[2/4] Checking FFmpeg..."
if command -v ffmpeg &>/dev/null; then
  echo "      FFmpeg found: $(ffmpeg -version 2>&1 | head -1)"
else
  echo ""
  echo "      ⚠️  FFmpeg not found. Install it with:"
  echo "         brew install ffmpeg"
  echo ""
fi

# 3. Create folders
echo "[3/4] Creating folders..."
mkdir -p music output
echo "      music/ and output/ ready."

# 4. Config check
echo "[4/4] Checking config..."
if [ -f config.json ]; then
  echo "      config.json found."
else
  cp config.template.json config.json
  echo "      config.json created from template."
  echo "      ⚠️  Open config.json and fill in your API keys."
fi

echo ""
echo "=== Next Steps ==="
echo ""
echo "  1. Fill in config.json with your API keys"
echo "     - Pexels: https://www.pexels.com/api/"
echo "     - Publer: https://app.publer.com/settings/api"
echo "     - Publer workspace ID: shown in Publer Settings → Workspace"
echo ""
echo "  2. Copy PermanentMarker.ttf into this folder"
echo ""
echo "  3. Add music tracks (.mp3 / .wav / .m4a) to the music/ folder"
echo ""
echo "  4. Connect TikTok + Instagram in Publer dashboard"
echo "     Then run: python3 get_account_ids.py"
echo "     Copy the IDs into config.json"
echo ""
echo "  5. Test the full pipeline:"
echo "     python3 run.py --dry-run"
echo ""
echo "  6. Add to Mac cron for daily posts at 7:50 AM Central:"
echo "     (cron runs 10 min early so Publer has time to schedule)"
echo ""
echo "     Run: crontab -e   and add this line:"
echo "     50 7 * * * cd $(pwd) && /usr/local/bin/python3 run.py --post-time 08:00 >> output/cron.log 2>&1"
echo ""
echo "     Or for 8 PM:"
echo "     50 19 * * * cd $(pwd) && /usr/local/bin/python3 run.py --post-time 20:00 >> output/cron.log 2>&1"
echo ""
echo "  Done! 🔥"
echo ""
