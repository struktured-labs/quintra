# Launch Game

Launch the Penta Dragon DX ROM in mGBA with proper display settings for KDE Wayland + Nvidia.

## Steps

1. Kill any existing mGBA instances (ignore errors):
   ```bash
   pkill -f mgba-qt || true
   ```
   Wait 0.5s for cleanup.

2. Launch mGBA with proper environment (NO pipes, NO redirects — breaks Wayland window visibility):
   ```bash
   DISPLAY=:0 QT_QPA_PLATFORM=xcb __GLX_VENDOR_LIBRARY_NAME=nvidia mgba-qt /home/struktured/projects/penta-dragon-dx-claude/rom/working/penta_dragon_dx_FIXED.gb &
   ```

3. Optionally load a save state by appending `-t path/to/state.ss0` before the `&`.

4. Verify the process is running:
   ```bash
   sleep 1 && pgrep -a mgba-qt
   ```

## Critical Notes
- MUST use `DISPLAY=:0 QT_QPA_PLATFORM=xcb __GLX_VENDOR_LIBRARY_NAME=nvidia` — without these, the GPU display device fails and the game runs poorly
- NEVER pipe stdout/stderr — this breaks window visibility on Wayland
- The `pkill` and launch MUST be separate commands (not chained with `&&`) because pkill returns non-zero when no process exists
- The `&` at the end is required to avoid blocking the terminal
