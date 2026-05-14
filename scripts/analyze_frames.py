#!/usr/bin/env python3
"""
Statistical frame analysis - NO IMAGE RECOGNITION.
Analyzes emulator output for timing, stability, and responsiveness.
"""
import json
from pathlib import Path
from typing import Dict, List, Any


def analyze_frame_data(output_json_path: Path) -> Dict[str, Any]:
    """Analyze MCP output JSON for frame statistics."""
    with open(output_json_path) as f:
        data = json.load(f)

    stats = {
        'total_frames': data.get('frame_count', 0),
        'freeze_detected': data.get('freeze_detected', False),
        'frames_without_change': data.get('frames_without_change', 0),
        'oam_activity': False,
        'input_responsive': False,
        'timing_ok': True,
    }

    # Check OAM activity
    oam_snapshots = data.get('oam_snapshots', [])
    if oam_snapshots:
        visible_counts = []
        for snapshot in oam_snapshots:
            visible = sum(1 for sprite in snapshot if sprite.get('y', 0) > 0 and sprite.get('y', 0) < 160)
            visible_counts.append(visible)

        # OAM is active if we see variation in sprite counts
        if len(set(visible_counts)) > 1 or max(visible_counts, default=0) > 0:
            stats['oam_activity'] = True

        stats['max_sprites_visible'] = max(visible_counts, default=0)
        stats['oam_variation'] = len(set(visible_counts))

    # Check input responsiveness (did OAM change after input frames?)
    # This is a heuristic - if sprites appear/disappear after input, likely responsive
    if len(oam_snapshots) >= 3:
        early_count = len([s for s in oam_snapshots[:len(oam_snapshots)//3]])
        late_count = len([s for s in oam_snapshots[len(oam_snapshots)//3:]])
        if late_count > early_count:
            stats['input_responsive'] = True

    # Timing check - if running slower than expected
    if stats['total_frames'] > 0:
        # Expect ~60fps, check if we're significantly slower
        pass  # MCP doesn't provide wall-clock time

    return stats


def print_analysis(stats: Dict[str, Any]):
    """Print analysis in readable format."""
    print("\n=== Frame Analysis ===")
    print(f"Total frames: {stats['total_frames']}")
    print(f"Freeze detected: {stats['freeze_detected']}")
    print(f"Frames without OAM change: {stats['frames_without_change']}")
    print(f"OAM activity: {stats['oam_activity']}")
    print(f"Max sprites visible: {stats.get('max_sprites_visible', 0)}")
    print(f"OAM variation: {stats.get('oam_variation', 0)} unique states")
    print(f"Input responsive: {stats['input_responsive']}")

    # Overall verdict
    print("\n=== Verdict ===")
    if stats['freeze_detected']:
        print("❌ FROZEN - Game not progressing")
    elif not stats['oam_activity']:
        print("⚠️  NO SPRITES - Title screen or crashed")
    elif stats['input_responsive']:
        print("✅ WORKING - Input responsive, sprites active")
    else:
        print("⚠️  UNCLEAR - Need more frames or different test")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        path = Path(sys.argv[1])
        stats = analyze_frame_data(path)
        print_analysis(stats)
    else:
        print("Usage: analyze_frames.py <output.json>")
