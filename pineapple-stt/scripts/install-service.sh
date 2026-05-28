#!/usr/bin/env bash
# Installs Pineapple STT as a macOS background service that starts
# automatically at login. No terminal window needed.
set -e

LABEL="com.pineapple.stt"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP="$SCRIPT_DIR/pineapple_stt.py"
PYTHON="$(command -v python3)"
LOG_DIR="$HOME/Library/Logs/pineapple-stt"

if [ -z "$PYTHON" ]; then
  echo "Error: python3 not found on PATH." >&2
  exit 1
fi

mkdir -p "$HOME/Library/LaunchAgents" "$LOG_DIR"

cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$PYTHON</string>
    <string>$APP</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>$LOG_DIR/out.log</string>
  <key>StandardErrorPath</key>
  <string>$LOG_DIR/err.log</string>
  <key>WorkingDirectory</key>
  <string>$SCRIPT_DIR</string>
</dict>
</plist>
EOF

# Reload if already loaded
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"

echo ""
echo "Pineapple STT is now running in the background and will start"
echo "automatically every time you log in."
echo ""
echo "Logs:    $LOG_DIR/out.log"
echo "Stop:    launchctl unload $PLIST"
echo "Start:   launchctl load $PLIST"
echo "Remove:  launchctl unload $PLIST && rm $PLIST"
echo ""
echo "NOTE: On first run, grant Microphone + Accessibility permissions"
echo "to your terminal/python in System Settings > Privacy & Security,"
echo "or text injection and listening won't work."
