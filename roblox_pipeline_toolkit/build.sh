#!/data/data/com.termux/files/usr/bin/bash

set -euo pipefail

echo "================================================"
echo "   BUILDING ROBLOX PIPELINE TOOLKIT"
echo "================================================"

if command -v pkg >/dev/null 2>&1; then
    echo "[1/4] Checking Termux packages (python, jq, curl, git, zip)..."
    pkg install -y python jq curl git zip >/dev/null 2>&1 || true
fi

echo "[2/4] Installing Python dependencies (lz4, zstandard)..."
python3 -m pip install --quiet --upgrade pip >/dev/null 2>&1 || true
python3 -m pip install --quiet lz4 zstandard

echo "[3/4] Setting executable permissions on all scripts..."
chmod +x *.sh *.py 2>/dev/null || true

if [ ! -f "publish_config.json" ]; then
    cp publish_config.example.json publish_config.json
    echo "[4/4] Created publish_config.json from template (edit with your API key & IDs)."
else
    echo "[4/4] Found existing publish_config.json (preserved)."
fi

if [ -f "pipeline_steps.json" ] && command -v jq >/dev/null 2>&1; then
    tmp_reg=$(mktemp)
    jq '.steps |= sort_by(.category)' pipeline_steps.json > "$tmp_reg" && mv "$tmp_reg" pipeline_steps.json
fi

echo ""
echo "================================================"
echo "   BUILD COMPLETE!"
echo "================================================"
echo "  1. Edit publish_config.json with your Universe ID, Place ID, and API Key."
echo "  2. Launch the menu: ./roblox_pipeline.sh"
echo ""
