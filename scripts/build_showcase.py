#!/usr/bin/env python3
"""Build the local Quintra stage, item, Colossus, and enemy browser."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageSequence

from make_stage_states import boot_to_stage, select_rom_topology, symbol_addresses


ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
OUT = ROOT / "docs/showcase"
ASSETS = OUT / "assets"
ENEMIES_C = ROOT / "src/generated/enemies.c"
STAGES_C = ROOT / "src/generated/stages.c"
ITEMS_C = ROOT / "src/render/tiles_items.c"
VERSION_H = ROOT / "src/game/version.h"
BOSS_ATLAS = ROOT / "docs/media/boss-gallery.png"
BOSS_ANIMATED_ATLAS = ROOT / "docs/media/boss-gallery.gif"

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
    "Crystal Colossus", "Storm Serpent", "Kilnback Pack / Cinder Rex", "Frost Spider",
    "Mire Heart", "Shadow Reaper", "Sun Golem", "Blood Hydra", "Void Lord",
)
BOSS_DESCRIPTIONS = (
    "A hand-authored wall-titan with crown prongs, slab shoulders, split roots, and an angular diamond weak core that jumps between three distant wells.",
    "A connected storm serpent that eats four motes, drags a damaging 128-pixel sixteen-scale second coil through the arena, pulses a wider charged aura, fires from both ends, charges an AOE, then contracts from the rear.",
    "Five armored Kilnbacks rewrite their wheel into a press, a burning unlock glyph, and a broken cage before their husks forge the long Cinder Rex; the Rex answers with lane breath, slag pools, marked stomps, a tail charge, and a critical five-flame reprise.",
    "A charged web with a warned flank blink and alternating cardinal and diagonal volleys.",
    "An expanding organism that pulses outward, contracts, advances, and scatters mixed-speed shots.",
    "A hunting specter that telegraphs each disappearance before re-entering from a new flank.",
    "An awakened idol whose moving heart sends slow, heavy eight-way rings through the court.",
    "A broad three-headed weave firing staggered slow, medium, and fast streams down the same lanes.",
    "A slowly regenerating, warping weak point above an arena-scale World Collapse with one announced safe pocket.",
)
BOSS_MOVEMENT = (
    "Anchor warp", "Snake trail / feed / AOE", "Formation / press / charge", "Blink", "Expand / contract",
    "Hunt / teleport", "Pursuit", "Broad weave", "Anchor warp",
)
BOSS_SIGNATURES = (
    "Prism Lance", "Coil Tempest", "Brandwalk / Furnace Breath", "Web Crucifix",
    "Miasma Bloom", "Death Sweep", "Sunfall", "Threefold Deluge",
    "Event Horizon",
)
BOSS_HP = (200, 205, 240, 150, 255, 255, 230, 150, 220)
BOSS_DAMAGE = (1, 1, 2, 2, 3, 3, 4, 4, 5)

ENEMY_NAMES = (
    "Blue Crawler", "Stone Sentinel", "Hornet", "Skeleton", "Orc", "Wisp",
    "Bomber", "Shade", "Warlock", "Rope", "Sentry", "Fold Star",
    "Flutterbat", "Gloom Leech", "Cinder Maw", "Rift Ooze", "Mirror Moth",
    "Mire Spore", "Echo Guard", "Rune Lantern", "Dread Bell", "Rift Warden",
    "Prism Skitter", "Dusk Midge", "Sunwheel", "Cinder Kite", "Bog Toad",
    "Bramble Sprite", "Frost Lancer", "Vine Coil", "Shard Crab", "Void Halo",
    "Rift Cantor", "Facet Ram", "Dread Reaper",
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
    "An armored cardinal patrol whose bright rear facet accepts only rear-to-front attacks before it fires backward.",
    "A deep-court hunter whose warned mortal scythe cuts a healthy champion to one heart without killing outright.",
)

ITEM_NAMES = (
    "Iron Heart", "Speed Ring", "Power Stone", "Tough Skin", "Lucky Coin",
    "Mana Gem", "Ward Charm", "Swift Fang", "Hunter's Eye", "Blood Sigil",
    "Weapon Cache", "Spirit Chart", "Weapon Surge", "Phoenix Feather",
    "Echo Prism", "Ricochet Rune", "Thorn Mail", "War Drum", "Spirit Flask",
    "Ascension Crown", "Rift Sigil", "Rift Bomb", "Echo Chime", "Mirror Shard",
    "Blast Seed", "Rift Lens", "Titan Glove", "Tide Raft", "Rift Hook",
    "Worldglass",
)
ITEM_EFFECTS = (
    "Permanently raises maximum health by one full heart.",
    "Permanently quickens movement through combat fields.",
    "Permanently raises direct attack strength.",
    "Permanently reduces incoming damage.",
    "Raises luck, improving the run's reward economy.",
    "Permanently expands the champion's Will reserve.",
    "Combines defense and luck in one compact boon.",
    "Trades restraint for greater attack and movement speed.",
    "A high-luck hunter's boon for treasure-driven builds.",
    "Vampiric kills slowly return health.",
    "Adds a class-shaped alternate weapon to the current build.",
    "Reveals more of the procedural dungeon Compass.",
    "Temporarily accelerates and empowers the equipped weapon.",
    "Returns the champion from one otherwise-fatal hit.",
    "Every fourth primary shot fractures into bounded child shots.",
    "Direct projectiles rebound from dungeon walls.",
    "Taking a hit answers with a retaliatory counterburst.",
    "Every fifth kill strengthens the next B art and restores Will.",
    "Converts spare hearts into Will for ability-heavy builds.",
    "Refills Will and awakens a short weapon transformation.",
    "The stage's lore fixture and required Colossus seal.",
    "A permanent tool that destroys selected cracked barriers.",
    "Silences hostile projectiles and resolves chime secrets.",
    "A permanent tool that bends one room pattern back on itself.",
    "Direct impacts splash damage into nearby enemies.",
    "Every third primary becomes a wide, heavy beam.",
    "Permanent Waygear for moving boulders without Sauran.",
    "Permanent Waygear for crossing water without Picsean.",
    "Permanent Waygear for crossing chasms without Corvin.",
    "Shifts Riftwild between its Waking and Hollow expressions.",
)
ITEM_CATEGORIES = (
    "Stat relic", "Stat relic", "Stat relic", "Stat relic", "Stat relic",
    "Stat relic", "Hybrid relic", "Hybrid relic", "Hybrid relic", "Build relic",
    "Weapon", "Navigation", "Temporary boon", "Build relic", "Weapon physics",
    "Weapon physics", "Defense relic", "Kill-chain relic", "Will relic", "Transformation",
    "Stage fixture", "Dungeon tool", "Dungeon tool", "Dungeon tool", "Weapon physics",
    "Weapon physics", "Permanent Waygear", "Permanent Waygear", "Permanent Waygear",
    "Riftwild key item",
)
ITEM_PALETTES = (
    ((8, 15, 23), (61, 36, 44), (224, 75, 84), (255, 232, 195)),
    ((8, 15, 23), (25, 55, 60), (63, 205, 179), (230, 255, 221)),
    ((8, 15, 23), (55, 42, 76), (180, 125, 255), (255, 236, 190)),
    ((8, 15, 23), (70, 54, 20), (246, 188, 56), (255, 246, 195)),
)

AI_LABELS = {
    "AI_WALKER": "Walker", "AI_CHASER": "Chaser", "AI_CHARGER": "Charger",
    "AI_SHOOTER": "Shooter", "AI_SPINNER": "Orbiter", "AI_TURRET": "Turret",
    "AI_REPLICATOR": "Replicator", "AI_MIRROR": "Mirror",
    "AI_SPORE_MINE": "Proximity mine", "AI_COUNTER_GUARD": "Counter guard",
    "AI_SUMMONER": "Summoner", "AI_TELEPORT": "Teleporter",
}
ELEMENTS = ((1, "Fire"), (2, "Ice"), (4, "Lightning"), (8, "Shadow"), (16, "Poison"))
BIG_ENEMIES = {1, 4, 6, 8, 14, 33, 34}


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
    assert len(records) == len(ENEMY_NAMES), \
        f"expected {len(ENEMY_NAMES)} enemy records, got {len(records)}"
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


def save_gif(frames: list[Image.Image], path: Path, duration: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    frames[0].save(
        temp, format="GIF", save_all=True, append_images=frames[1:],
        duration=duration, loop=0, disposal=2, optimize=True,
    )
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


def display_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    try:
        return ImageFont.truetype(f"/usr/share/fonts/truetype/dejavu/{name}", size)
    except OSError:
        return ImageFont.load_default()


def parse_item_tiles() -> list[list[int]]:
    source = ITEMS_C.read_text()
    block = re.search(
        r"static const u8 sprite_item_icons\[30\]\[16\] = \{(.*?)\n\};",
        source, re.DOTALL,
    )
    assert block, "missing authored item icon table"
    rows = [
        [int(value, 16) for value in re.findall(r"0x[0-9A-Fa-f]{2}", row)]
        for row in re.findall(r"\{([^{}]+)\}", block.group(1))
    ]
    assert len(rows) == len(ITEM_NAMES) == 30
    assert all(len(row) == 16 for row in rows)
    return rows


def render_item_icon(tile: list[int], index: int) -> Image.Image:
    palette = ITEM_PALETTES[index % len(ITEM_PALETTES)]
    sprite = Image.new("RGB", (8, 8), palette[0])
    pixels = sprite.load()
    for y in range(8):
        low, high = tile[y * 2:y * 2 + 2]
        for x in range(8):
            bit = 7 - x
            color = ((low >> bit) & 1) | (((high >> bit) & 1) << 1)
            pixels[x, y] = palette[color]

    panel = Image.new("RGB", (128, 128), (4, 8, 15))
    draw = ImageDraw.Draw(panel)
    draw.rectangle((8, 8, 119, 119), fill=(8, 16, 25), outline=palette[2], width=2)
    draw.rectangle((13, 13, 114, 114), outline=(24, 43, 50))
    for point in ((16, 16), (111, 16), (16, 111), (111, 111)):
        draw.rectangle((point[0] - 1, point[1] - 1, point[0] + 1, point[1] + 1), fill=palette[3])
    panel.paste(sprite.resize((80, 80), Image.Resampling.NEAREST), (24, 24))
    return panel


def capture_items() -> tuple[list[dict], Image.Image]:
    images: list[Image.Image] = []
    items: list[dict] = []
    for index, tile in enumerate(parse_item_tiles()):
        image = render_item_icon(tile, index)
        path = ASSETS / f"item-{index:02d}-{slug(ITEM_NAMES[index])}.png"
        save_png(image, path)
        images.append(image)
        items.append({
            "id": index,
            "name": ITEM_NAMES[index],
            "description": ITEM_EFFECTS[index],
            "category": ITEM_CATEGORIES[index],
            "accent": ("#e04b54", "#3fcdb3", "#b47dff", "#f6bc38")[index % 4],
            "image": f"assets/{path.name}",
        })
    collage = labeled_collage(
        images, [f"{index:02d}  {name.upper()}" for index, name in enumerate(ITEM_NAMES)],
        columns=6, panel_size=(128, 128), label_height=24,
    )
    save_png(collage, ASSETS / "item-collage.png")
    return items, collage


def build_world_atlas(stage_collage: Image.Image, item_collage: Image.Image) -> None:
    boss_collage = Image.open(BOSS_ATLAS).convert("RGB")
    monster_collage = Image.open(ASSETS / "monster-collage.png").convert("RGB")
    canvas = Image.new("RGB", (1600, 1884), (3, 7, 12))
    draw = ImageDraw.Draw(canvas)
    draw.text((32, 20), "QUINTRA // CARTRIDGE FIELD ATLAS",
              fill=(233, 246, 237), font=display_font(30, bold=True))
    draw.text((34, 57), "9 STAGES  ·  9 COLOSSI  ·  29 RELICS & TOOLS  ·  35 MONSTERS",
              fill=(126, 240, 188), font=display_font(15, bold=True))

    stage_large = stage_collage.resize((720, 756), Image.Resampling.NEAREST)
    boss_large = boss_collage.resize((720, 720), Image.Resampling.NEAREST)
    draw.text((56, 91), "STAGES", fill=(255, 210, 111), font=display_font(20, bold=True))
    draw.text((824, 91), "COLOSSI", fill=(255, 210, 111), font=display_font(20, bold=True))
    canvas.paste(stage_large, (56, 120))
    canvas.paste(boss_large, (824, 120))

    draw.text((24, 910), "RELICS, TOOLS & WAYGEAR", fill=(185, 147, 255),
              font=display_font(20, bold=True))
    draw.text((808, 910), "BESTIARY", fill=(185, 147, 255),
              font=display_font(20, bold=True))
    canvas.paste(item_collage, (24, 946))
    canvas.paste(monster_collage, (808, 946))
    save_png(canvas, ASSETS / "quintra-world-atlas.png")


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
    enemy_stages[34] = list(range(len(STAGE_NAMES)))  # fixed deep Reaper

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
                # These specialists own runtime state outside the generated
                # content record. Mirror their real spawn initialization so
                # the Ram presents its broad silhouette and the Reaper is not
                # captured on the first hidden beat of its attack telegraph.
                if enemy_id == 33:
                    pyboy.memory[entity + 15] = 2
                    pyboy.memory[entity + 16] = 72
                    pyboy.memory[entity + 18] = 72
                elif enemy_id == 34:
                    pyboy.memory[entity + 20] = 78
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
    animated_atlas = Image.open(BOSS_ANIMATED_ATLAS)
    assert animated_atlas.size == (480, 480)
    assert animated_atlas.n_frames == 16
    duration = animated_atlas.info.get("duration", 120)
    animated_frames = [
        frame.convert("RGB").copy()
        for frame in ImageSequence.Iterator(animated_atlas)
    ]
    bosses = []
    for stage, name in enumerate(BOSS_NAMES):
        x = (stage % 3) * 160
        y = (stage // 3) * 160
        image = atlas.crop((x, y, x + 160, y + 144))
        path = ASSETS / f"boss-{stage + 1:02d}-{slug(name)}.png"
        save_png(image, path)
        animated_path = ASSETS / f"boss-{stage + 1:02d}-{slug(name)}.gif"
        save_gif([
            frame.crop((x, y, x + 160, y + 144))
            for frame in animated_frames
        ], animated_path, duration)
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
            "animated": f"assets/{animated_path.name}",
        })
    return bosses


def write_data(stages: list[dict], bosses: list[dict], monsters: list[dict],
               items: list[dict]) -> None:
    version_match = re.search(r'QUINTRA_VERSION "([^"]+)"', VERSION_H.read_text())
    assert version_match
    data = {
        "meta": {
            "version": version_match.group(1),
            "romSha256": sha256(ROM),
            "stageCount": len(stages),
            "bossCount": len(bosses),
            "monsterCount": len(monsters),
            "itemCount": len(items),
        },
        "collages": {
            "stages": "assets/stage-collage.png",
            "bosses": "../media/boss-gallery.png",
            "bossesAnimated": "../media/boss-gallery.gif",
            "monsters": "assets/monster-collage.png",
            "items": "assets/item-collage.png",
            "worldAtlas": "assets/quintra-world-atlas.png",
        },
        "stages": stages,
        "bosses": bosses,
        "monsters": monsters,
        "items": items,
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
    items, item_collage = capture_items()
    stage_collage = Image.open(ASSETS / "stage-collage.png").convert("RGB")
    build_world_atlas(stage_collage, item_collage)
    write_data(stages, bosses, monsters, items)
    print(
        f"[showcase] PASS {len(stages)} stages, {len(bosses)} Colossi, "
        f"{len(monsters)} monsters, {len(items)} items -> {OUT / 'index.html'}"
    )


if __name__ == "__main__":
    main()
