#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$HOME/.local/share/applications"
DESKTOP_FILE="$APP_DIR/KaliHackerTerminal.desktop"

mkdir -p "$APP_DIR"

cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Kali Hacker Terminal
Comment=Red-team style terminal shell inspired by Kali Linux
Exec=python3 $SCRIPT_DIR/kali_hacker_terminal.py
Path=$SCRIPT_DIR
Terminal=false
Categories=System;Utility;
EOF

chmod +x "$DESKTOP_FILE"

echo "Installed: $DESKTOP_FILE"
echo "You can now launch 'Kali Hacker Terminal' from your app menu."
