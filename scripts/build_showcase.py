#!/usr/bin/env python3
"""Build the local Quintra stage, Colossus, and complete-enemy browser."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from PIL import Image, ImageDraw

from make_stage_states import boot_to_stage, select_rom_topology, symbol_addresses


ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
OUT = ROOT / "docs/showcase"
ASSETS = OUT / "assets"
ENEMIES_C = ROOT / "src/generated/enemies.c"
STAGES_C = ROOT / "src/generated/stages.c"
VERSION_H = ROOT / "src/game/version.h"
BOSS_ATLAS = ROOT / "docs/media/boss-gallery.png"

STAGE_NAMES = (
    "Crystal Caverns", "Verdant Hollow", "Ember Depths",
    "Frost Vault", "Toxic Mire", "Shadow Keep",
    "Golden Temple", "Bloodmoon", "Void Sanctum",
)
STAGE_ACCENTS = (
    "#83e6ff", "#70e28d", "#ff765c", "#b8ecff", "#83dd73",
    "#bf91ff", "#ffd45b", "#ff668f", "#d690ff",
)
STAGE_DESCRIPTIONS = (
    "Faceted shards, pale stone courts, and the run's first shell-and-lane lessons.",
    "Root-wrapped halls and blossom debris introduce pursuit, coils, and quicker flanks.",
    "Braziers and ash frame fan-fire casters, splitting ooze, and heat-driven crossfire.",
    "Ice columns and snowfields mix reflection, line charges, turrets, and brittle lanes.",
    "Fungal ruins and bubbling mire pair proximity mines with pounces and pressure arcs.",
    "Gargoyles, webs, and dim masonry turn orbiting threats and teleporters into lane puzzles.",
    "Sun mosaics and monumental columns field guarded duelists and heavy ring volleys.",
    "Bone altars under red light combine fast harriers with staggered late-run barrages.",
    "Broken obelisks and watching halos culminate in wide orbits, summons, and collapsing space.",
)

BOSS_NAMES = (
    "Crystal Colossus", "Storm Serpent", "Cinder Maw", "Frost Spider",
    "Mire Heart", "Shadow Reaper", "Sun Golem", "Blood Hydra", "Void Lord",
)
BOSS_DESCRIPTIONS = (
    "A screen-scale crystal guardian whose exposed heart jumps between three distant wells.",
    "A connected storm serpent that eats four motes, drags a damaging 128-pixel sixteen-scale second coil through the arena, pulses a wider charged aura, fires from both ends, charges an AOE, then contracts from the rear.",
    "A furnace beast that breathes in aimed fans, telegraphs a hard lunge, then clenches to recover.",
    "A charged web with a warned flank blink and alternating cardinal and diagonal volleys.",
    "An expanding organism that pulses outward, contracts, advances, and scatters mixed-speed shots.",
    "A hunting specter that telegraphs each disappearance before re-entering from a new flank.",
    "An awakened idol whose moving heart sends slow, heavy eight-way rings through the court.",
    "A broad three-headed weave firing staggered slow, medium, and fast streams down the same lanes.",
    "A slowly regenerating, warping weak point above an arena-scale World Collapse with one announced safe pocket.",
)
BOSS_MOVEMENT = (
    "Anchor warp", "Snake trail / feed / AOE", "Lunge", "Blink", "Expand / contract",
    "Hunt / teleport", "Pursuit", "Broad weave", "Anchor warp",
)
BOSS_SIGNATURES = (
    "Prism Lance", "Coil Tempest", "Furnace Breath", "Web Crucifix",
    "Miasma Bloom", "Death Sweep", "Sunfall", "Threefold Deluge",
    "Event Horizon",
)
BOSS_HP = (200, 205, 150, 150, 255, 255, 230, 150, 220)
BOSS_DAMAGE = (1, 1, 2, 2, 3, 3, 4, 4, 5)

ENEMY_NAMES = (
    "Blue Crawler", "Stone Sentinel", "Hornet", "Skeleton", "Orc", "Wisp",
    "Bomber", "Shade", "Warlock", "Rope", "Sentry", "Fold Star",
    "Flutterbat", "Gloom Leech", "Cinder Maw", "Rift Ooze", "Mirror Moth",
    "Mire Spore", "Echo Guard", "Rune Lantern", "Dread Bell", "Rift Warden",
    "Prism Skitter", "Dusk Midge", "Sunwheel", "Cinder Kite", "Bog Toad",
    "Bramble Sprite", "Frost Lancer", "Vine Coil", "Shard Crab", "Void Halo",
    "Rift Cantor",
)
ENEMY_SIGNATURES = (
    "A compact wandering body that becomes dangerous when several close the same route.",
    "A durable 16x16 dungeon warden with high poise and a stage-colored guardian shell.",
    "A fast pursuer that follows around cover using champion-sized path clearance.",
    "A persistent chaser built to hold pressure through narrow dungeon routes.",
    "A heavy 16x16 bruiser that warns, then commits to a forceful lane charge.",
    "A slow drifting caster that releases a single readable shot.",
    "A 16x16 walking bomb whose defeat answers with a four-way revenge burst.",
    "A fragile ambusher that vanishes and reappears near the champion.",
    "A heavy 16x16 caster that controls a broad three-shot fan.",
    "A Zelda-like snake that snaps into a straight charge when a lane lines up.",
    "A rooted turret whose rotating cross makes the safe lanes move.",
    "Blooms into untouchable diagonal echoes on an odd cadence, then contracts to take damage.",
    "A Keese-like diagonal flyer that flutters in bursts and rebounds around obstacles.",
    "Pursues, attaches, and drains life until a dodge-dash shakes it loose.",
    "A narrow 10x15 middle-scale furnace caster whose deliberate three-way volleys turn open space into a routing test.",
    "A modest walker that splits into two fragile fragments, then tries to recombine.",
    "Reverses the champion's last movement and fires a reflected lane shot.",
    "A rooted proximity mine that unfolds into an eight-lane burst after a visible fuse.",
    "Parries the first careless hit, rushes, then opens a pale vulnerability window.",
    "Drifts between cover and releases slow cardinal rings with open diagonals.",
    "A heavy caster that announces a full eight-lane peal before it tolls.",
    "A late-stage lane breaker that claims the center with a deliberate five-shot fan.",
    "Maintains a ring around the champion and rotates an opposite projectile pair through it.",
    "A quick late-run harrier that periodically throws a narrow three-shot fan.",
    "Golden Temple's compact orbiting hazard, firing a slow pair through the center.",
    "A fast Ember drifter whose low-damage fan changes lanes without becoming a wall.",
    "Crouches for a readable beat, then commits to a quick mireland pounce.",
    "Holds a broad thorn ring and sends a slow opposing pair through the champion.",
    "Pauses behind an icy tell, then breaks a straight lane with a committed charge.",
    "Verdant's modest orbiting coil, teaching lane changes with one slow seed pair.",
    "Deflects one hasty hit, scuttles forward, then opens for a generous counterattack.",
    "A wide, slow Void orbit that shapes space with one opposite pair at a time.",
    "A priority target that chants once to summon a bounded escort wave; interrupting it cancels the call.",
)

AI_LABELS = {
    "AI_WALKER": "Walker", "AI_CHASER": "Chaser", "AI_CHARGER": "Charger",
    "AI_SHOOTER": "Shooter", "AI_SPINNER": "Orbiter", "AI_TURRET": "Turret",
    "AI_REPLICATOR": "Replicator", "AI_MIRROR": "Mirror",
    "AI_SPORE_MINE": "Proximity mine", "AI_COUNTER_GUARD": "Counter guard",
    "AI_SUMMONER": "Summoner", "AI_TELEPORT": "Teleporter",
}
ELEMENTS = ((1, "Fire"), (2, "Ice"), (4, "Lightning"), (8, "Shadow"), (16, "Poison"))
BIG_ENEMIES = {1, 4, 6, 8, 14}


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def extra_symbol(rom: Path, name: str) -> int:
    text = rom.with_suffix(".noi").read_text()
    match = re.search(rf"DEF {re.escape(name)} 0x([0-9A-Fa-f]+)", text)
    if not match:
        raise RuntimeError(f"missing ROM symbol {name}")
    return int(match.group(1), 16)


def parse_enemy_records() -> list[dict[str, int | str]]:
    source = ENEMIES_C.read_text()
    pattern = re.compile(
        r'\{ \.id=(\d+), \.name="[^"]+", \.sprite_set=(\d+), \.palette=(\d+),\s*'
        r'\.stats=\{ \.hp=(\d+), \.damage=(\d+), \.speed=(\d+), '
        r'\.score=(\d+), \.weakness=(\d+), \.poise=(\d+) \},\s*'
        r'\.ai_kind=(AI_[A-Z_]+), \.ai_p0=(\d+), \.ai_p1=(\d+), \.ai_p2=(\d+),',
        re.MULTILINE,
    )
    records = []
    for match in pattern.finditer(source):
        values = match.groups()
        records.append({
            "id": int(values[0]), "sprite": int(values[1]), "palette": int(values[2]),
            "hp": int(values[3]), "damage": int(values[4]), "speed": int(values[5]),
            "score": int(values[6]), "weakness": int(values[7]), "poise": int(values[8]),
            "ai": values[9], "p0": int(values[10]), "p1": int(values[11]),
            "p2": int(values[12]),
        })
    assert len(records) == len(ENEMY_NAMES), f"expected 33 enemy records, got {len(records)}"
    assert [record["id"] for record in records] == list(range(len(ENEMY_NAMES)))
    return records


def parse_stage_pools() -> list[list[int]]:
    source = STAGES_C.read_text()
    block = re.search(
        r"const u8 stage_pool_ids\[N_STAGES\]\[STAGE_POOL_MAX\] = \{(.*?)\n\};",
        source, re.DOTALL,
    )
    counts = re.search(
        r"const u8 stage_pool_n\[N_STAGES\] = \{([^}]+)\};", source,
    )
    assert block and counts
    rows = [
        [int(value.strip()) for value in row.split(",") if value.strip()]
        for row in re.findall(r"\{([^{}]+)\}", block.group(1))
    ]
    ns = [int(value.strip()) for value in counts.group(1).split(",")]
    assert len(rows) == len(ns) == len(STAGE_NAMES)
    return [row[:count] for row, count in zip(rows, ns)]


def put16(pyboy, address: int, value: int) -> None:
    pyboy.memory[address] = value & 0xFF
    pyboy.memory[address + 1] = (value >> 8) & 0xFF


def put_fix8(pyboy, address: int, pixels: int) -> None:
    raw = pixels << 8
    for offset in range(4):
        pyboy.memory[address + offset] = (raw >> (offset * 8)) & 0xFF


def save_png(image: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    image.save(temp, format="PNG", optimize=True)
    temp.replace(path)


def labeled_collage(images: list[Image.Image], labels: list[str], columns: int,
                    panel_size: tuple[int, int], label_height: int = 24) -> Image.Image:
    width, height = panel_size
    rows = (len(images) + columns - 1) // columns
    canvas = Image.new("RGB", (columns * width, rows * (height + label_height)), (4, 8, 15))
    draw = ImageDraw.Draw(canvas)
    for index, (image, label) in enumerate(zip(images, labels)):
        x = (index % columns) * width
        y = (index // columns) * (height + label_height)
        canvas.paste(image.resize(panel_size, Image.Resampling.NEAREST), (x, y))
        draw.rectangle((x, y + height, x + width - 1, y + height + label_height - 1),
                       fill=(6, 13, 22))
        draw.text((x + 6, y + height + 6), label, fill=(226, 244, 232))
    return canvas


def speed_tier(raw: int) -> str:
    if raw == 0:
        return "Rooted"
    if raw >= 80:
        return "Very fast"
    if raw >= 64:
        return "Fast"
    if raw >= 48:
        return "Mobile"
    return "Slow"


def capture_assets(records: list[dict[str, int | str]], pools: list[list[int]]) -> tuple[list[dict], list[dict]]:
    select_rom_topology(ROM)
    addrs = symbol_addresses(ROM)
    entities = addrs["_entities"]
    player = addrs["_player"]
    camera_x = addrs["_room_camera_x"]
    camera_y = addrs["_room_camera_y"]
    enemy_count = extra_symbol(ROM, "_entity_enemy_count")
    hitstop = extra_symbol(ROM, "_g_hitstop")

    stages: list[dict] = []
    monsters: list[dict] = [{} for _ in records]
    stage_images: list[Image.Image] = []
    # Captures are grouped by first habitat to minimize emulator boots, but
    # the final contact sheet is ordered by stable content ID.
    monster_focus_images: list[Image.Image | None] = [None] * len(records)

    enemy_stages = {
        enemy_id: [stage for stage, pool in enumerate(pools) if enemy_id in pool]
        for enemy_id in range(len(records))
    }
    enemy_stages[1] = list(range(len(STAGE_NAMES)))  # stage-colored Wardens

    for stage, stage_name in enumerate(STAGE_NAMES):
        pyboy, _, room = boot_to_stage(ROM, addrs, stage, "normal", 0)
        try:
            for _ in range(12):
                pyboy.tick()
            stage_image = pyboy.screen.image.convert("RGB").copy()
            stage_path = ASSETS / f"stage-{stage + 1:02d}-{slug(stage_name)}.png"
            save_png(stage_image, stage_path)
            stage_images.append(stage_image)
            stages.append({
                "id": stage + 1,
                "name": stage_name,
                "description": STAGE_DESCRIPTIONS[stage],
                "accent": STAGE_ACCENTS[stage],
                "boss": BOSS_NAMES[stage],
                "room": room,
                "image": f"assets/{stage_path.name}",
            })

            ids = [enemy_id for enemy_id, homes in enemy_stages.items()
                   if homes and homes[0] == stage]
            for enemy_id in ids:
                record = records[enemy_id]
                for offset in range(32 * 28):
                    pyboy.memory[entities + offset] = 0
                pyboy.memory[enemy_count] = 1
                pyboy.memory[hitstop] = 0

                cam_x = pyboy.memory[camera_x]
                cam_y = pyboy.memory[camera_y]
                put16(pyboy, player + 9, cam_x + 72)
                put16(pyboy, player + 11, cam_y + 74)
                pyboy.memory[player + 2] = pyboy.memory[player + 1]

                entity = entities
                pyboy.memory[entity] = 2
                pyboy.memory[entity + 1] = 0x07
                put_fix8(pyboy, entity + 2, cam_x + 112)
                put_fix8(pyboy, entity + 6, cam_y + 52)
                pyboy.memory[entity + 10] = pyboy.memory[entity + 11] = 0
                pyboy.memory[entity + 12] = int(record["sprite"])
                pyboy.memory[entity + 13] = int(record["palette"])
                pyboy.memory[entity + 14] = int(record["hp"])
                pyboy.memory[entity + 15] = 0
                pyboy.memory[entity + 16] = 240
                for offset in range(8):
                    pyboy.memory[entity + 17 + offset] = 0
                pyboy.memory[entity + 17] = enemy_id
                pyboy.memory[entity + 25] = 0xAA if enemy_id == 12 else (
                    0xDD if enemy_id in BIG_ENEMIES else 0x66)
                pyboy.memory[entity + 26] = int(record["damage"])
                pyboy.memory[entity + 27] = 4

                for _ in range(4):
                    pyboy.tick()
                field = pyboy.screen.image.convert("RGB").copy()
                field_path = ASSETS / f"monster-{enemy_id:02d}-{slug(ENEMY_NAMES[enemy_id])}-field.png"
                save_png(field, field_path)

                size = 16 if enemy_id in BIG_ENEMIES else 8
                world_x = pyboy.memory[entity + 3] | pyboy.memory[entity + 4] << 8
                world_y = pyboy.memory[entity + 7] | pyboy.memory[entity + 8] << 8
                screen_x = world_x - pyboy.memory[camera_x]
                screen_y = world_y - pyboy.memory[camera_y]
                center_x = screen_x + size // 2
                center_y = screen_y + size // 2
                focus = field.crop((center_x - 16, center_y - 16,
                                    center_x + 16, center_y + 16)).resize(
                                        (128, 128), Image.Resampling.NEAREST)
                focus_path = ASSETS / f"monster-{enemy_id:02d}-{slug(ENEMY_NAMES[enemy_id])}-focus.png"
                save_png(focus, focus_path)
                monster_focus_images[enemy_id] = focus

                homes = enemy_stages[enemy_id]
                weakness = [name for bit, name in ELEMENTS if int(record["weakness"]) & bit]
                monsters[enemy_id] = {
                    "id": enemy_id,
                    "name": ENEMY_NAMES[enemy_id],
                    "description": ENEMY_SIGNATURES[enemy_id],
                    "behavior": AI_LABELS.get(str(record["ai"]), str(record["ai"])),
                    "hp": record["hp"],
                    "damage": record["damage"],
                    "speed": speed_tier(int(record["speed"])),
                    "speedRaw": record["speed"],
                    "poise": record["poise"],
                    "score": record["score"],
                    "weakness": weakness,
                    "stages": [value + 1 for value in homes],
                    "firstSeen": STAGE_NAMES[homes[0]] if homes else "Special encounter",
                    "focus": f"assets/{focus_path.name}",
                    "field": f"assets/{field_path.name}",
                }
        finally:
            pyboy.stop(save=False)

    assert all(monsters), "one or more registered monsters were not captured"
    stage_collage = labeled_collage(
        stage_images, [f"{index + 1}  {name.upper()}" for index, name in enumerate(STAGE_NAMES)],
        columns=3, panel_size=(160, 144), label_height=24,
    )
    save_png(stage_collage, ASSETS / "stage-collage.png")

    assert all(image is not None for image in monster_focus_images)
    monster_collage = labeled_collage(
        [image for image in monster_focus_images if image is not None],
        [f"{index:02d}  {name.upper()}" for index, name in enumerate(ENEMY_NAMES)],
        columns=6, panel_size=(128, 128), label_height=24,
    )
    save_png(monster_collage, ASSETS / "monster-collage.png")
    return stages, monsters


def capture_bosses() -> list[dict]:
    atlas = Image.open(BOSS_ATLAS).convert("RGB")
    assert atlas.size == (480, 480), f"unexpected boss atlas size {atlas.size}"
    bosses = []
    for stage, name in enumerate(BOSS_NAMES):
        x = (stage % 3) * 160
        y = (stage // 3) * 160
        image = atlas.crop((x, y, x + 160, y + 144))
        path = ASSETS / f"boss-{stage + 1:02d}-{slug(name)}.png"
        save_png(image, path)
        bosses.append({
            "id": stage + 1,
            "name": name,
            "stage": STAGE_NAMES[stage],
            "description": BOSS_DESCRIPTIONS[stage],
            "movement": BOSS_MOVEMENT[stage],
            "signature": BOSS_SIGNATURES[stage],
            "hp": BOSS_HP[stage],
            "damage": BOSS_DAMAGE[stage],
            "accent": STAGE_ACCENTS[stage],
            "image": f"assets/{path.name}",
        })
    return bosses


def write_data(stages: list[dict], bosses: list[dict], monsters: list[dict]) -> None:
    version_match = re.search(r'QUINTRA_VERSION "([^"]+)"', VERSION_H.read_text())
    assert version_match
    data = {
        "meta": {
            "version": version_match.group(1),
            "romSha256": sha256(ROM),
            "stageCount": len(stages),
            "bossCount": len(bosses),
            "monsterCount": len(monsters),
        },
        "collages": {
            "stages": "assets/stage-collage.png",
            "bosses": "../media/boss-gallery.png",
            "bossesAnimated": "../media/boss-gallery.gif",
            "monsters": "assets/monster-collage.png",
        },
        "stages": stages,
        "bosses": bosses,
        "monsters": monsters,
    }
    payload = json.dumps(data, indent=2)
    (OUT / "gallery-data.js").write_text(
        "// Generated by scripts/build_showcase.py from the current ROM.\n"
        f"window.QUINTRA_SHOWCASE = {payload};\n"
    )
    (OUT / "manifest.json").write_text(payload + "\n")


def main() -> None:
    if not ROM.exists() or not ROM.with_suffix(".noi").exists():
        raise SystemExit("build the cartridge first: make all")
    if not BOSS_ATLAS.exists():
        raise SystemExit("missing live boss atlas: run make media")
    ASSETS.mkdir(parents=True, exist_ok=True)
    records = parse_enemy_records()
    pools = parse_stage_pools()
    stages, monsters = capture_assets(records, pools)
    bosses = capture_bosses()
    write_data(stages, bosses, monsters)
    print(
        f"[showcase] PASS {len(stages)} stages, {len(bosses)} Colossi, "
        f"{len(monsters)} monsters -> {OUT / 'index.html'}"
    )


if __name__ == "__main__":
    main()
