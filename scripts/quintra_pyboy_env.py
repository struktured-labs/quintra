#!/usr/bin/env python3
"""Small controller-only PyBoy environment for Quintra research and RL.

This deliberately reads only the cartridge's ordinary WRAM state and drives
only normal joypad input.  It is a reusable counterpart to the long mGBA
balance pilot: use it for short interactive policies, curriculum rollouts,
and emulator-native deep-stage save-state work without putting test hooks in
the GBC ROM.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
from importlib.metadata import version
from pathlib import Path
from typing import Any

from pyboy import PyBoy


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ROM = ROOT / "rom" / "working" / "quintra.gbc"

# A compact six-bit action space. Directions can be ORed with A/B; for
# example ACTION_RIGHT | ACTION_A is a normal aimed attack while moving.
ACTION_UP = 0x01
ACTION_RIGHT = 0x02
ACTION_DOWN = 0x04
ACTION_LEFT = 0x08
ACTION_A = 0x10
ACTION_B = 0x20

_BUTTONS = (
    (ACTION_UP, "up"), (ACTION_RIGHT, "right"),
    (ACTION_DOWN, "down"), (ACTION_LEFT, "left"),
    (ACTION_A, "a"), (ACTION_B, "b"),
)

# Keep these explicit rather than borrowing historical harness numbers: the
# current cartridge's screen enum is BOOT..DIALOG=0..10, GAMEOVER=11,
# VICTORY=12 (src/game/screen.h).
SCREEN_GAMEOVER = 11
SCREEN_VICTORY = 12
ROOM_PIXEL_W = 20 * 8
ROOM_PIXEL_H = 17 * 8
ROOM_W = 20
ROOM_H = 17
ROOM_WIDE_W = 31
ROOM_WIDE_H = 31
ROOM_WIDE_EXT_W = ROOM_WIDE_W - ROOM_W
BGT_FLOOR = 1
BGT_WALL = 2
BGT_DOOR = 3
BLANK_SRAM_BYTES = 32 * 1024
ENEMY_STONE_SENTINEL = 1


def _symbol_addresses(rom: Path) -> dict[str, int]:
    noi = rom.with_suffix(".noi").read_text()
    names = ("_run_state", "_player", "_entities", "_room_tilemap",
             "_room_world_extension", "_room_world_bottom",
             "_room_world_width", "_room_world_height",
             "_room_camera_x", "_room_camera_y",
             "_loop_current_screen", "_input_keys", "_input_pressed")
    result: dict[str, int] = {}
    for name in names:
        found = re.search(rf"DEF {re.escape(name)} 0x([0-9A-Fa-f]+)", noi)
        if not found:
            raise RuntimeError(f"missing ROM symbol {name}")
        result[name] = int(found.group(1), 16)
    return result


class QuintraPyBoyEnv:
    """A minimal reset/step environment with JSON-serializable observations.

    It is intentionally framework-neutral: gymnasium, Stable Baselines, or a
    bespoke policy can wrap this tiny surface without making either dependency
    part of the project toolchain. Reward favors real run progress while
    retaining HP loss as a negative signal.
    """

    def __init__(self, rom: Path | str = DEFAULT_ROM, *, cgb: bool = True,
                 window: str = "null"):
        self.rom = Path(rom)
        self.addrs = _symbol_addresses(self.rom)
        self._cgb = cgb
        self._window = window
        self.pb: PyBoy | None = None
        self._ram_file: io.BytesIO | None = None
        self.episode_frames = 0
        self._new_emulator()
        self._held = 0
        self._last_score = 0
        self._last_hp = 0
        self._last_room = 0
        self._last_bosses = 0

    def _new_emulator(self) -> None:
        if self.pb is not None:
            self.pb.stop(save=False)
        # RL/checkpoint runs must not inherit a developer's adjacent .ram file.
        # Keeping the BytesIO alive also gives every reset the same blank SRAM.
        self._ram_file = io.BytesIO(bytes(BLANK_SRAM_BYTES))
        self.pb = PyBoy(str(self.rom), window=self._window, cgb=self._cgb,
                        ram_file=self._ram_file)
        self._held = 0
        self.episode_frames = 0

    def close(self) -> None:
        self._set_action(0)
        if self.pb is not None:
            self.pb.stop(save=False)
            self.pb = None

    def _tick(self, frames: int) -> None:
        assert self.pb is not None
        for _ in range(frames):
            self.pb.tick()
        self.episode_frames += frames

    def _set_action(self, mask: int) -> None:
        assert self.pb is not None
        mask &= 0x3F
        for bit, name in _BUTTONS:
            was_held = bool(self._held & bit)
            now_held = bool(mask & bit)
            if now_held and not was_held:
                self.pb.button_press(name)
            elif was_held and not now_held:
                self.pb.button_release(name)
        self._held = mask

    @staticmethod
    def _u16(memory: Any, address: int) -> int:
        return memory[address] | (memory[address + 1] << 8)

    @classmethod
    def _i16(cls, memory: Any, address: int) -> int:
        """Read the cartridge's signed ``ppos_t`` entity coordinate."""
        value = cls._u16(memory, address)
        return value - 0x10000 if value & 0x8000 else value

    @staticmethod
    def _i8(value: int) -> int:
        return value - 0x100 if value & 0x80 else value

    def reset(self, class_id: int = 0, *, difficulty: str = "normal") -> dict[str, Any]:
        """Boot a fresh run through title/class-select using ordinary input."""
        if not 0 <= class_id < 5:
            raise ValueError("class_id must be in 0..4")
        if difficulty not in ("normal", "easy"):
            raise ValueError("difficulty must be 'normal' or 'easy'")
        # RL reset means a genuinely fresh emulator episode. Reusing a game
        # already in a room made a second reset press START into live combat
        # rather than title/class-select, leaking prior-run state into data.
        self._new_emulator()
        self._tick(240)
        self.pb.button("start")
        self._tick(24)
        for _ in range(class_id):
            self.pb.button("down")
            self._tick(8)
        if difficulty == "easy":
            self.pb.button("select")
            self._tick(8)
        self.pb.button("a")
        self._tick(60)
        obs = self.observe()
        self._remember(obs)
        self.episode_frames = 0
        return obs

    def load_state(self, state_path: Path | str, *, require_manifest: bool = True) -> dict[str, Any]:
        """Restore an external PyBoy checkpoint and begin observing from it.

        Checkpoints are intentionally emulator-native developer fixtures, not
        a second cartridge save system. Regenerate them after a ROM rebuild
        with ``make stage-states`` before using them for a training run.  The
        generated-state manifest pins the ROM hash, so a stale curriculum
        checkpoint cannot silently train against shifted WRAM/layout data.
        """
        path = Path(state_path)
        manifest_path = path.parent / "manifest.json"
        record = None
        if not manifest_path.exists() and require_manifest:
            raise RuntimeError(f"checkpoint manifest is missing: {manifest_path}")
        if manifest_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text())
                expected = manifest.get("rom_sha256")
            except (OSError, json.JSONDecodeError) as exc:
                raise RuntimeError(f"cannot read stage-state manifest: {manifest_path}") from exc
            actual = hashlib.sha256(self.rom.read_bytes()).hexdigest()
            if expected != actual:
                raise RuntimeError(
                    "stage-state ROM hash does not match the active cartridge; "
                    "regenerate with make stage-states")
            expected_pyboy = manifest.get("pyboy_version")
            actual_pyboy = version("pyboy")
            if expected_pyboy != actual_pyboy:
                raise RuntimeError(
                    f"checkpoint requires PyBoy {expected_pyboy}, active is {actual_pyboy}")
            record = next((item for item in manifest.get("states", [])
                           if item.get("file") == path.name), None)
            if record is None:
                raise RuntimeError(f"checkpoint is not listed in manifest: {path.name}")
            expected_state_hash = record.get("sha256")
            actual_state_hash = hashlib.sha256(path.read_bytes()).hexdigest()
            if expected_state_hash != actual_state_hash:
                raise RuntimeError(f"checkpoint hash does not match manifest: {path.name}")
        self._set_action(0)
        assert self.pb is not None
        with path.open("rb") as saved:
            self.pb.load_state(saved)
        obs = self.observe()
        if record is not None:
            expected_stage = record.get("stage")
            expected_room = record.get("room_counter")
            expected_class = record.get("class_id")
            expected_difficulty = record.get("difficulty")
            if expected_stage is not None and obs["stage"] != expected_stage:
                raise RuntimeError(f"checkpoint restored wrong stage: {path.name}")
            if expected_room is not None and obs["room"] != expected_room:
                raise RuntimeError(f"checkpoint restored wrong room: {path.name}")
            if expected_class is not None and obs["class_id"] != expected_class:
                raise RuntimeError(f"checkpoint restored wrong champion: {path.name}")
            if (expected_difficulty is not None
                    and obs["difficulty"] != expected_difficulty):
                raise RuntimeError(f"checkpoint restored wrong difficulty: {path.name}")
        self._remember(obs)
        self.episode_frames = 0
        return obs

    def save_state(self, state_path: Path | str) -> Path:
        """Atomically capture the exact current frame without advancing it."""
        path = Path(state_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + ".tmp")
        self._set_action(0)
        assert self.pb is not None
        with temp.open("wb") as saved:
            self.pb.save_state(saved)
        temp.replace(path)
        return path

    def _remember(self, obs: dict[str, Any]) -> None:
        self._last_score = obs["score"]
        self._last_hp = obs["hp"]
        self._last_room = obs["room"]
        self._last_bosses = obs["bosses"]

    def observe(self, *, include_tiles: bool = True) -> dict[str, Any]:
        """Return the complete current-world player-visible observation.

        ``tiles`` retains the compact 20x17 compatibility view while
        ``world_tiles`` spans the live generated field or Colossus arena.
        Enemy bodies are public world entities; no private RNG, future rooms,
        or collision hooks are exposed.
        """
        mem = self.pb.memory
        rs = self.addrs["_run_state"]
        player = self.addrs["_player"]
        entities = self.addrs["_entities"]
        tilemap = self.addrs["_room_tilemap"]
        extension = self.addrs["_room_world_extension"]
        bottom = self.addrs["_room_world_bottom"]
        world_width = mem[self.addrs["_room_world_width"]] or ROOM_PIXEL_W
        world_height = mem[self.addrs["_room_world_height"]] or ROOM_PIXEL_H
        world_width = max(ROOM_PIXEL_W, min(ROOM_WIDE_W * 8, world_width))
        world_height = max(ROOM_PIXEL_H, min(ROOM_WIDE_H * 8, world_height))
        world_tile_w = world_width // 8
        world_tile_h = world_height // 8

        hostiles = []
        projectiles = []
        pickups = []
        for slot in range(32):
            base = entities + slot * 28
            flags = mem[base + 1]
            # ENT_PROJECTILE (1) without EF_PLAYER_PROJ (bit 4) is an
            # on-screen hostile bullet. Keep its public kinematics alongside
            # enemy bodies so an RL policy can learn the same dodge problem
            # as the mGBA controller without any cartridge debug hook.
            if mem[base] == 1 and (flags & 0x01) and not (flags & 0x10):
                x = self._i16(mem, base + 3)
                y = self._i16(mem, base + 7)
                if -8 < x < world_width and -8 < y < world_height:
                    projectiles.append({
                        "x": x, "y": y,
                        "vx": self._i8(mem[base + 10]), "vy": self._i8(mem[base + 11]),
                        "damage": mem[base + 14], "ttl": mem[base + 18],
                    })
            # Pickups are visible room objects. Exposing their position and
            # kind lets a controller learn the same Sigil/heart/relic choices
            # a player sees without reading future rooms or private RNG.
            if mem[base] == 3 and (flags & 0x01):
                x = self._i16(mem, base + 3)
                y = self._i16(mem, base + 7)
                if -8 < x < world_width and -8 < y < world_height:
                    pickups.append({"kind": mem[base + 17], "x": x, "y": y})
            # ENT_ENEMY (2) with bit 0 of flags marks a live hostile.
            if mem[base] != 2 or not (flags & 0x01):
                continue
            x = self._i16(mem, base + 3)
            y = self._i16(mem, base + 7)
            # During a Zelda-style room slide, the previous room's entity
            # table can remain live for a few frames while the next room is
            # streaming. It is neither visible nor actionable. Clip bodies
            # wholly outside the live world (with a 32px giant margin), not
            # the old 160x136 viewport: every Colossus arena is 224px wide
            # and generated districts are 248x248.
            is_giant = (mem[base + 17] == ENEMY_STONE_SENTINEL
                        and bool(mem[base + 20] & 0x01))
            size = 32 if is_giant else 16
            if x <= -size or x >= world_width or y <= -size or y >= world_height:
                continue
            hostiles.append({
                "kind": mem[base + 17],
                "x": x, "y": y,
                "vx": self._i8(mem[base + 10]), "vy": self._i8(mem[base + 11]),
                "hp": mem[base + 14], "state": mem[base + 15],
                # The giant's current movement pattern and its phase timer
                # are the same public runtime state sampled by the mGBA
                # controller trace. They let an offline policy learn a
                # telegraphed lunge/blink rather than treating it as noise.
                "pattern": mem[base + 19], "phase_timer": mem[base + 18],
                # Void Lord's visible World Collapse telegraph. The charge
                # flag and announced safe-corner slot are intentionally
                # public to controller-only curricula just as they are to
                # the live mGBA pilot; no future position or immunity leaks.
                "collapse": mem[base + 21],
                "safe_slot": mem[base + 22],
                # ai_data[3] is enemy-private storage. Only Stone Sentinel
                # interprets bit 0 as the authored giant marker; Folding Star
                # and other specialists may legitimately reuse that same bit.
                "giant": is_giant,
            })

        world_tiles: list[int] = []
        if include_tiles:
            giant_alive = any(enemy["giant"] for enemy in hostiles)
            for y in range(world_tile_h):
                for x in range(world_tile_w):
                    if y < ROOM_H and x < ROOM_W:
                        tile = mem[tilemap + y * ROOM_W + x]
                    elif y < ROOM_H and world_height > ROOM_PIXEL_H:
                        tile = mem[extension + y * ROOM_WIDE_EXT_W
                                   + (x - ROOM_W)]
                    elif y >= ROOM_H:
                        tile = mem[bottom + (y - ROOM_H) * ROOM_WIDE_W + x]
                    else:
                        # Colossus arenas synthesize their 8-column eastern
                        # chamber at query/render time rather than spending
                        # WRAM on a third compact strip. Mirror room_tile_at_px:
                        # visual projection space is walkable; the true far
                        # border is solid until the giant has fallen.
                        if x == world_tile_w - 1:
                            tile = (BGT_DOOR if not giant_alive and y in (8, 9)
                                    else BGT_WALL)
                        elif y in (0, ROOM_H - 1):
                            tile = BGT_WALL
                        else:
                            tile = BGT_FLOOR
                    world_tiles.append(tile)

        return {
            "screen": mem[self.addrs["_loop_current_screen"]],
            "room": mem[rs + 1],
            "bosses": mem[rs + 11],
            # Stage and world mode are already player-visible through the
            # Pack/compass UI.  Exposing them explicitly lets a curriculum
            # distinguish a late dungeon checkpoint from Riftwild traversal
            # without asking a policy to reverse-engineer that fact from
            # tile art alone.
            "stage": min(9, mem[rs + 11] + 1),
            "world_mode": bool(mem[rs + 17]),
            "world_screen": mem[rs + 18],
            "entered_from": mem[rs + 6],
            "world_width": world_width,
            "world_height": world_height,
            "camera_x": mem[self.addrs["_room_camera_x"]],
            "camera_y": mem[self.addrs["_room_camera_y"]],
            "difficulty": "easy" if mem[rs + 26] else "normal",
            "victory": bool(mem[rs + 10]),
            "class_id": mem[player],
            "hp_max": mem[player + 1], "hp": mem[player + 2],
            "mp_max": mem[player + 3], "mp": mem[player + 4],
            "x": self._u16(mem, player + 9),
            "y": self._u16(mem, player + 11),
            "iframes": mem[player + 15],
            "coins": self._u16(mem, player + 16),
            "weapon": mem[player + 21],
            "active_charge": mem[player + 19],
            "shield_timer": mem[player + 20],
            "score": self._u16(mem, player + 40),
            # These are the cartridge's ordinary post-poll joypad bytes. They
            # let a passive human report distinguish real interaction from an
            # unattended hero taking damage; they do not inject or alter input.
            "input_keys": mem[self.addrs["_input_keys"]],
            "input_pressed": mem[self.addrs["_input_pressed"]],
            # Interactive human telemetry samples every displayed frame and
            # does not need the 340-byte collision grid. Policies retain the
            # full default observation; passive launchers may omit it to avoid
            # adding needless overhead to the SDL play experience.
            "tiles": (list(mem[tilemap:tilemap + 20 * 17])
                      if include_tiles else []),
            "world_tiles": world_tiles,
            "hostiles": hostiles,
            "projectiles": projectiles,
            "pickups": pickups,
        }

    @staticmethod
    def is_terminal(observation: dict[str, Any]) -> bool:
        return observation["screen"] in (SCREEN_GAMEOVER, SCREEN_VICTORY) or observation["victory"]

    def step(self, action: int, frames: int = 4) -> tuple[dict[str, Any], float, bool, dict[str, Any]]:
        """Apply a six-bit controller mask for 1..60 emulated frames."""
        if not 1 <= frames <= 60:
            raise ValueError("frames must be in 1..60")
        self._set_action(action)
        self._tick(frames)
        obs = self.observe()
        reward = (obs["score"] - self._last_score) * 0.05
        reward += (obs["room"] - self._last_room) * 2.0
        reward += (obs["bosses"] - self._last_bosses) * 20.0
        reward -= max(0, self._last_hp - obs["hp"]) * 0.5
        terminal = self.is_terminal(obs)
        info = {"action": action & 0x3F, "frames": frames}
        self._remember(obs)
        return obs, reward, terminal, info


def main() -> None:
    parser = argparse.ArgumentParser(description="Emit a short Quintra PyBoy environment rollout as JSONL")
    parser.add_argument("--rom", type=Path, default=DEFAULT_ROM)
    parser.add_argument("--class-id", type=int, default=0)
    parser.add_argument("--difficulty", choices=("normal", "easy"),
                        default="normal")
    parser.add_argument("--steps", type=int, default=4)
    parser.add_argument("--frames", type=int, default=4)
    parser.add_argument("--action", type=int, default=ACTION_RIGHT | ACTION_A)
    parser.add_argument("--state", type=Path,
                        help="external PyBoy state from make stage-states; skips fresh reset")
    args = parser.parse_args()

    env = QuintraPyBoyEnv(args.rom)
    try:
        initial = (env.load_state(args.state) if args.state
                   else env.reset(args.class_id, difficulty=args.difficulty))
        print(json.dumps({"reset": initial}, separators=(",", ":")))
        for _ in range(args.steps):
            obs, reward, terminal, info = env.step(args.action, args.frames)
            print(json.dumps({"observation": obs, "reward": reward,
                              "terminal": terminal, "info": info}, separators=(",", ":")))
            if terminal:
                break
    finally:
        env.close()


if __name__ == "__main__":
    main()
