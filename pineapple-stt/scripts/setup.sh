#!/usr/bin/env bash
# setup.sh — install system-level dependencies for Pineapple STT
# Run once before first use: bash scripts/setup.sh

set -euo pipefail

echo ""
echo "🍍  Pineapple STT — System Setup"
echo "-------------------------------------"

# ── Python version check ──────────────────────────────────────────────────────
if ! python3 -c "import sys; assert sys.version_info >= (3,8)" 2>/dev/null; then
  echo "❌  Python 3.8+ is required. Please install it first."
  exit 1
fi
echo "✓  Python $(python3 --version | cut -d' ' -f2)"

# ── Linux (Debian / Ubuntu) ────────────────────────────────────────────────────
if command -v apt-get &>/dev/null; then
  echo "→  Installing system packages (apt) ..."
  sudo apt-get update -qq
  sudo apt-get install -y \
    portaudio19-dev \
    python3-dev \
    python3-pip \
    xdotool \
    libsndfile1 \
    libasound2-dev
  echo "✓  System packages installed"
fi

# ── Linux (Fedora / RHEL / CentOS) ───────────────────────────────────────────
if command -v dnf &>/dev/null && ! command -v apt-get &>/dev/null; then
  echo "→  Installing system packages (dnf) ..."
  sudo dnf install -y portaudio-devel python3-devel xdotool libsndfile
  echo "✓  System packages installed"
fi

# ── macOS (Homebrew) ────────────────────────────────────────────────────────────
if command -v brew &>/dev/null; then
  echo "→  Installing portaudio via Homebrew ..."
  brew install portaudio
  echo "✓  Homebrew packages installed"
fi

# ── Python packages ──────────────────────────────────────────────────────────
echo "→  Installing Python packages ..."
pip3 install --upgrade pip --quiet
pip3 install -r "$(dirname "$0")/requirements.txt"
echo "✓  Python packages installed"

echo ""
echo "✅  Setup complete!"
echo ""
echo "Run with:   python3 scripts/pineapple_stt.py"
echo "Help:       python3 scripts/pineapple_stt.py --help"
echo ""
