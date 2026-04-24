#!/bin/bash
# Install Neuzelaar desktop launcher and icon.

PROJECT_DIR=$(pwd)
ICON_PATH="$PROJECT_DIR/assets/neuzelaar.png"
LAUNCHER_PATH="$HOME/.local/share/applications/neuzelaar.desktop"

echo "[Desktop Entry]" > "$LAUNCHER_PATH"
echo "Type=Application" >> "$LAUNCHER_PATH"
echo "Name=Neuzelaar" >> "$LAUNCHER_PATH"
echo "Comment=Safe and Stable Web Browser" >> "$LAUNCHER_PATH"
echo "Exec=$PROJECT_DIR/neuzelaar-ui.sh %u" >> "$LAUNCHER_PATH"
echo "Icon=$ICON_PATH" >> "$LAUNCHER_PATH"
echo "Terminal=false" >> "$LAUNCHER_PATH"
echo "Categories=Network;WebBrowser;" >> "$LAUNCHER_PATH"
echo "MimeType=text/html;text/xml;application/xhtml+xml;x-scheme-handler/http;x-scheme-handler/https;" >> "$LAUNCHER_PATH"

chmod +x "$LAUNCHER_PATH"

echo "Launcher installed to $LAUNCHER_PATH"
echo "Icon path: $ICON_PATH"
echo "You may need to restart your shell or logout/login for it to appear in the dash."
