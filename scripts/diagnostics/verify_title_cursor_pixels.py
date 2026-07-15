#!/usr/bin/env python3
import os
import sys
import numpy as np
from pyboy import PyBoy

ROM_PATH = os.path.expanduser("~/projects/penta-dragon-dx-claude/rom/working/penta_dragon_dx_teleport.gb")

def check_cursor_visuals():
    print("=== PROGRAMMATIC VISUAL VERIFICATION: TITLE SCREEN CURSOR ===")
    
    if not os.path.exists(ROM_PATH):
        print(f"Error: ROM file {ROM_PATH} not found.")
        sys.exit(1)
        
    # 1. Initialize PyBoy headlessly
    print("Booting emulator core headlessly...")
    pb = PyBoy(ROM_PATH, window="null", cgb=True)
    pb.set_emulation_speed(0) # Run at maximum possible speed
    
    # 2. Advance emulator to the title screen (let menus and animations settle)
    # The title screen settles around frame 180-200. We run for 250 frames.
    print("Advancing emulator to title screen (250 frames)...")
    for _ in range(250):
        pb.tick(1, True)
        
    # 3. Capture the screen image as a numpy array
    # PyBoy screen image is a PIL Image object
    screen_image = pb.screen.image
    screen_data = np.array(screen_image)
    
    # Bounding box of the cursor tile on the GBC screen
    # In Penta Dragon, the title screen cursor is located at the left of 'GAME START'
    # GBC screen resolution is 160x144. Let's crop the cursor tile.
    # We'll dump a crop of the left-menu area to inspect pixel patterns.
    # Typically, the cursor sits at: X around 24-32, Y around 88-96.
    # Let's crop a 16x16 pixel area around the cursor and analyze the pixel density.
    x_start, x_end = 20, 36
    y_start, y_end = 84, 100
    
    crop = screen_data[y_start:y_end, x_start:x_end]
    
    # Save the crop to disk so the user can visually verify it if needed
    os.makedirs("tmp/diagnostics", exist_ok=True)
    crop_image_path = "tmp/diagnostics/title_cursor_crop.png"
    screen_image.crop((x_start, y_start, x_end, y_end)).save(crop_image_path)
    print(f"Captured cursor area crop saved to {crop_image_path}")
    
    # 4. First-principles analysis of the pixel data:
    # A standard Game Boy Color pixel is [R, G, B, A] (or [R, G, B]).
    # We can convert the crop to grayscale to count active (non-white) pixels.
    grayscale = np.dot(crop[..., :3], [0.2989, 0.5870, 0.1140])
    
    # White is 255. Non-white (colored/black) pixels represent the drawn glyph.
    active_pixels = grayscale < 200
    
    print("\nVisual Pixel Matrix Grid (16x16 crop around cursor position):")
    for r in range(16):
        row_chars = ""
        for c in range(16):
            row_chars += "# " if active_pixels[r, c] else ". "
        print(row_chars)
        
    # 5. Programmatic Check for the Character 'A':
    # An uppercase letter 'A' glyph in a standard 8x8 font has a specific pattern:
    # - It has a hollow center/bridge in the middle rows.
    # - It is symmetric.
    # - It has a flat top or two points.
    # A hand/arrow cursor (0x73) points to the right:
    # - It is highly asymmetric (heavier on the left/middle, tapering to a point on the right).
    # - The top rows are empty or diagonal.
    #
    # Let's inspect the vertical symmetry:
    left_half = active_pixels[:, :8]
    right_half = active_pixels[:, 8:]
    # Flip right half to compare symmetry
    right_half_flipped = np.fliplr(right_half)
    
    symmetry_match = np.mean(left_half == right_half_flipped)
    print(f"\nVertical Symmetry Coefficient: {symmetry_match:.4f}")
    
    # Standard font 'A' is highly symmetric vertically (symmetry > 0.82)
    # The arrow cursor (pointing right) is highly ASYMMETRIC (symmetry < 0.65)
    
    pb.stop(save=False)
    
    if symmetry_match > 0.80:
        print("\n❌ VERIFICATION FAILURE: The cursor is rendering as a symmetric character glyph (likely the letter 'A').")
        return False
    else:
        print("\n✅ VERIFICATION SUCCESS: The cursor is rendering with asymmetric arrow/hand geometry.")
        return True

if __name__ == "__main__":
    success = check_cursor_visuals()
    sys.exit(0 if success else 1)
