#!/usr/bin/env bash
set -e

REPO_DIR="$HOME/pineapple-stt-repo"
APP_DIR="$REPO_DIR/pineapple-stt"
REPO_URL="https://github.com/archerc84-spec/awesome-claude-skills.git"

echo ""
echo "Pineapple STT Installer"
echo "-----------------------"

# Clone or update
if [ -d "$REPO_DIR/.git" ]; then
  echo "-> Updating existing install..."
  git -C "$REPO_DIR" pull --quiet
else
  echo "-> Cloning repository into $REPO_DIR..."
  git clone --depth=1 "$REPO_URL" "$REPO_DIR"
fi

cd "$APP_DIR"

echo "-> Running system setup..."
bash scripts/setup.sh

echo ""
echo "Done! To launch Pineapple STT any time, run:"
echo "  python3 $APP_DIR/scripts/pineapple_stt.py"
echo ""

read -r -p "Launch now? [y/N] " REPLY
if [[ "$REPLY" =~ ^[Yy]$ ]]; then
  python3 "$APP_DIR/scripts/pineapple_stt.py"
fi
