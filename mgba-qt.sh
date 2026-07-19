#!/usr/bin/env bash
# Never force NVIDIA's GLX provider: on hybrid/remote desktops that causes
# mGBA-Qt to display a graphics-driver error before it loads the cartridge.
# The software Mesa path is dependable for this small 160×144 GB viewport.
export DISPLAY="${DISPLAY:-:0}"
export QT_QPA_PLATFORM=xcb
export LIBGL_ALWAYS_SOFTWARE=1
unset __GLX_VENDOR_LIBRARY_NAME
exec /home/struktured/bin/mgba-qt "$@"
