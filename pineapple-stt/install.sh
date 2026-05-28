#!/usr/bin/env bash
set -e

INSTALL_DIR="$HOME/pineapple-stt"
REPO_URL="https://github.com/archerc84-spec/awesome-claude-skills.git"

echo ""
echo "🍍 Pineapple STT Installer"
echo "--------------------------"

# Clone or update
if [ -d "$INSTALL_DIR/.git" ]; then
  echo "→ Updating existing install at $INSTALL_DIR..."
  git -C "$INSTALL_DIR" pull --quiet
else
  echo "→ Cloning into $INSTALL_DIR..."
  git clone --depth=1 --filter=blob:none --sparse "$REPO_URL" "$INSTALL_DIR"
  git -C "$INSTALL_DIR" sparse-checkout set pineapple-stt
  # Move contents up one level for convenience
  cp -r "$INSTALL_DIR/pineapple-stt/." "$INSTALL_DIR/"
fi

cd "$INSTALL_DIR"

echo "→ Running system setup (may ask for sudo for brew packages)..."
bash scripts/setup.sh

echo ""
echo "✅ Done! To launch Pineapple STT, run:"
echo "   python3 $INSTALL_DIR/scripts/pineapple_stt.py"
echo ""
echo "   Or just: cd ~/pineapple-stt && python3 scripts/pineapple_stt.py"
echo ""

read -r -p "Launch now? [y/N] " REPLY
if [[ "$REPLY" =~ ^[Yy]$ ]]; then
  python3 "$INSTALL_DIR/scripts/pineapple_stt.py"
fi
