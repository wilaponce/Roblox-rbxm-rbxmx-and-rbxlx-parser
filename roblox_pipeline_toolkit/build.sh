#!/usr/bin/env bash
set -euo pipefail

echo "=== BUILDING ROBLOX PIPELINE TOOLKIT ==="
if command -v pkg >/dev/null 2>&1; then
    pkg install -y python nodejs-lts rust curl git zip >/dev/null 2>&1 || true
elif command -v brew >/dev/null 2>&1; then
    brew install python node rust curl git zip >/dev/null 2>&1 || true
fi

for tool in python3 node cargo curl git zip; do
    command -v "$tool" >/dev/null 2>&1 || echo "  [WARN] Missing tool: $tool"
done

[ -d ".venv" ] || python3 -m venv .venv
source .venv/bin/activate
python -m pip install --quiet --upgrade pip >/dev/null 2>&1 || true
python -m pip install --quiet -r requirements.txt

if [ -f "Cargo.toml" ] && command -v cargo >/dev/null 2>&1; then
    cargo build --quiet
    [ -f "target/debug/rbxlx" ] && cp target/debug/rbxlx bin/
fi

mkdir -p downloads converted fixed published bin
chmod +x *.sh *.py 2>/dev/null || true
[ -f "publish_config.json" ] || cp publish_config.example.json publish_config.json

echo "BUILD COMPLETE! Run: source .venv/bin/activate && ./roblox_pipeline.sh"
