#!/bin/bash
# Launch mgba-qt for human play on NVIDIA + KDE Wayland
# Usage: launch_mgba.sh [rom_path]
set -e

PROJECT_DIR="/home/struktured/projects/penta-dragon-dx-claude"
ROM="${1:-rom/working/penta_dragon_dx_FIXED.gb}"

# Resolve relative paths against project dir
if [[ "$ROM" != /* ]]; then
    ROM="$PROJECT_DIR/$ROM"
fi

if [ ! -f "$ROM" ]; then
    echo "ROM not found: $ROM"
    exit 1
fi

# Kill existing instances
pkill -9 -f 'mgba-qt' 2>/dev/null || true
sleep 1

# Ensure OpenGL display driver in config
QTINI="$HOME/.config/mgba/qt.ini"
if [ -f "$QTINI" ]; then
    sed -i 's/^displayDriver=.*/displayDriver=1/' "$QTINI"
fi

# Launch with XWayland (fixes OpenGL context on NVIDIA + KDE Wayland)
QT_QPA_PLATFORM=xcb \
__GLX_VENDOR_LIBRARY_NAME=nvidia \
VK_DRIVER_FILES=/usr/share/vulkan/icd.d/nvidia_icd.json \
  mgba-qt "$ROM" &

sleep 3
if pgrep -f mgba-qt > /dev/null; then
    echo "Running: $(basename "$ROM")"
else
    echo "FAILED to start mgba-qt"
    exit 1
fi
