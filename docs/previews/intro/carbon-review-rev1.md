### A. Verdict
Strong Ultima/ROV-inspired concept with cohesive colour scripts and well-scoped stage transitions, but the 33 s intro drags, Shot 4’s captures break the art style, and Shot 7 depicts a human instead of a spirit vessel. On the hardware side, there are critical math errors in map/attribute sizing, `0x8800` signed tile indexing, and GDMA per-frame limits that need correcting before writing `intro_assets.py`.

---

### B. Lore Clarity & Pacing
**Myth delivery:** Mostly clear, with two holes:
1. **No descent:** Lore says the champions carry sparks *"into the world below"*, yet Shot 7 shows a human standing high on an overworld cliff.
2. **Passive Shot 8:** "THE ROGUELIKE" breaks mythic register right at the climax, and "CHOOSE YOUR VESSEL" (the player's actual call to action) is missing.

**Length:** 33 s (1980 frames) is too long for a cold-boot handheld roguelike; players will reflexively mash START by second 15. **Target: ~22–24 s (1380–1440 frames).** Merge Shots 2 & 3 into a single continuous camera pan from the tearing sky down into the darkening valley.

**Concrete Shot & Text Edits (A–Z, 0–9 only, ≤20 chars/line):**
* **Shot 1 (180 f / 3.0 s):** `ONCE EVERY ROAD` / `KNEW ITS OWN NAME` (Pan sky→valley).
* **Shot 2+3 Merged (240 f / 4.0 s):** `THEN THE SKY TORE` (0–119 f, sky tear + shake) → text swaps on pan down → `DEVOURING ALL NAMES` (120–240 f, valley palettes dim to violet).
* **Shot 4 (180 f / 3.0 s):** `NINE COLOSSI ROSE` / `IN THE WORLD BELOW` (Pop in 3 per beat, or 1 every 12 f).
* **Shot 5 (180 f / 3.0 s):** `FIVE SPIRITS WOKE` / `TO BEAR THE SPARKS`
* **Shot 6 (240 f / 4.0 s):** Header `FIVE ARE CHOSEN` (Slide in every 32 f; keep exact class names + epithets—all fit ≤14 chars).
* **Shot 7 (180 f / 3.0 s):** `DESCEND THE RIFTWILD` / `BIND THE DARKNESS` (Replace cliff human with silhouette/chosen vessel facing the chasm).
* **Shot 8 (180 f / 3.0 s):** `CHOOSE YOUR VESSEL` / `REKINDLE THE DAWN` → resolves into `QUINTRA` logo + `PRESS START`. (Cut `THE ROGUELIKE`).

---

### C. Readability at 160×144
* **Shot 1 (Valley):** Reads surprisingly well, though roof/field dithering is slightly noisy. Good contrast against the black window band.
* **Shot 2 (Sky Tear):** Bottom silhouette tries to cram all 9 biome landmarks (volcano, crystal, pyramid, tower) into 32 vertical pixels—reads as messy miniature clutter, and conflicts with Shot 1/3’s valley geography. **Fix:** Replace bottom silhouettes with simple dark valley ridgelines matching Shot 1/3.
* **Shot 3 (Torn Valley):** Severe quantization artifact on the middle-right—a rectangular tan patch failed to dim to violet—plus blocky attribute clashing along the river. **Fix:** Hand-clean palette assignments after quantization; don't rely purely on automated per-tile matching, or dim Shot 1's exact tiles purely via CGB palette math!
* **Shot 4 (Boss Grid):** Weakest frame by far. Raw room captures show floor tiles, wall grids, and blue player sprites next to bosses; bottom-left and bottom-right cells don't read as creatures at all. **Fix:** Must use dedicated 48×32 dark-silhouette bust portraits with glowing eyes/cores framed in 1 px borders (true ROV style).
* **Shot 5 (Shrine):** Cleanest panel in the set. Sigils read clearly, though top particle trails look like static dotted lines—use animated 8×8 OBJ embers instead of baked BG dots. Bottom grass is empty; push stones down 8 px.
* **Shot 6 (Parade):** Very crisp ROV layout. Watch line spacing: 5 entries × 2 text rows + header = 15–16 tile rows; right now `STING OF BLOOM` kisses row 17. Keep 1 tile of top/bottom margin.
* **Shot 7 (Cliff):** **Lore mismatch:** Foreground character is a detailed 32 px tall human warrior, clashing with the 16×16 animal vessels in Shots 6 & 8. Also, lavender sky + tan ruins + purple rift have flat mid-tone value contrast. **Fix:** Darken sky to deep indigo so the magenta Rift pops; replace human with a rear-view cape silhouette matching the animal vessels (or show all five silhouettes overlooking the edge).
* **Shot 8 (Title):** `THE   ROGUELIKE` has awkward triple-space kerning, and the five 16×16 sprites float ungrounded above `QUINTRA`.
* **Trans / Stages:** `stages.png` frames are gorgeous, readable, and distinct. However, in `trans.png`:
  * **Riftwild Frame 2:** Two vertical black rectangles masking the arch look like missing-tile bugs rather than a rift opening. **Fix:** Open from the center outward over stone/darkness tiles, or mask with jagged purple rift-edge tiles.
  * **Ember Depths (`trans.png` vs `stages.png`):** `trans.png` has noisy grey rock clutter and Wolfkin's tan sprite blends right into the grey cobblestone path (`Frame 2`). `stages.png` has a cleaner lava path, **but** a hero can't walk up molten lava! **Fix:** Keep `trans.png`’s stone bridge, darken its stones to charcoal so light/coloured hero OBJs pop, and add a dark 1 px outline around all hero sprites. Also align motto margins: `THE WILD REMEMBERS` touches the outer screen edge (`col 0`–`19` must stay centered).

---

### D. GBC Technical Feasibility & Budget Audit
Several numbers in the spec's budget table and VRAM plan need correction:

1. **VRAM Tile Math & `0x8800` Addressing:**
   * Total VRAM across two banks in `0x8800–0x97FF` mode is `256 × 2 = 512` tiles. Minus 37 font tiles (`bank 0`, slots 0..36) + 1 blank tile = **474 tiles max** (`512 - 38`), close to your 475.
   * **Gotcha:** Under `LCDC.4 = 0` (`0x8800` mode), tile IDs `0..127` map to **`0x9000–0x97FF`**, while `128..255` (signed `-128..-1`) map to **`0x8800–0x8FFF`**. Your converter (`intro_assets.py`) must remap tile indices accordingly (`id ^ 0x80` if writing linearly from `0x8800`).
   * **Font glyph bug:** Spec says *"Font additions: X J Z . 0 3 6 7 9"*. Neither intro nor stage mottos use digits or periods (and prompt notes A–Z/digits only). Drop `.` and unused digits; verify `Q, V, K, Y, B, P` are already in `0..36`.
2. **Map + Attr Sizes Are Understated for Hardware Loading:**
   * Spec lists Valley `Map+attr = 1.2 KB` (`20×30 × 2 = 1200 B`). While true in ROM if stored packed (`w × h`), CGB BG maps in VRAM (`0x9800`) are fixed **32×32 Stride** (`1024 B` map + `1024 B` attr = **2.0 KB**). Either store 2 KB flat or copy row-by-row via CPU.
3. **Torn Valley (Shot 3) Optimization:**
   * If Shot 3 is the exact same valley panning down while dimming, **it costs 0 KB of tiles/maps**—just interpolate the 7 BG palettes toward dark violet over 2 steps and swap only the top sky/rift tiles! Even as a 14-row overlay (`20×14 = 280` tiles), budget ≤200 unique tiles (`3.2 KB`).
4. **Loading Strategy (LCD-Off vs GDMA):**
   * **Do NOT turn LCD off (`LCDC.7 = 0`) outside VBlank**, and turning LCD off for a full frame causes a visible white flash on real CGB screens unless done carefully behind black palettes—Nintendo's guidelines forbid mid-game LCD-off transitions if avoidable.
   * **GDMA limit:** In CGB double-speed mode, VBlank is ~1.09 ms (~2280 M-cycles). GDMA copies `16 B` per `8` double-speed M-cycles (~`4.5 KB` max theoretical, **`~2.0–2.5 KB` safe** alongside OAM DMA + music tick). A `6.4 KB` tile load + `2 KB` map/attr (`8.4 KB`) takes **4 VBlanks** under black palettes (`BGP` all `0x0000`)—only 67 ms, completely invisible, zero LCD-off risk!
5. **Window Layer & LYC Conflicts:**
   * Window at `WY=112, WX=7` cleanly covers rows 14–17 (32 px text band) with solid black BG palette 7, hiding vertical `SCY` scroll seams beneath it.
   * **Bug in Shot 7 & Void Sanctum:** When panning diagonally (`SCX = 0→32` in Shot 7) or doing `SCY ±1` LYC bobbing in Void Sanctum, `WX` stays fixed so the Window is unaffected—**good**—*except* Void Sanctum's frame border in `stages.png` sits on the same scanlines as the interior! If you wobble `SCY ±1` via LYC on rows 16–104, **the left/right double-line frame borders will bob up and down too**, breaking the top/bottom frame corners. **Fix:** Either bob floating island rocks as OBJs, or keep the outer frame outside the bobbing scanlines (only wobble horizontal rock bands that don't touch vertical frame rails—impossible with a side border). Use OBJ islands instead.
6. **ROM Space & Compression:**
   * 13 empty 16 KB banks (`18–30`, assuming 31 reserved or `18–31` = 14 banks = **224 KB free**). `~50 KB` uncompressed fits in 4 banks easily; with simple RLE/LZ4 or GBDK `gbcompress`, tiles+maps drop to **~28–32 KB** (2 banks) and decompress into a WRAM buffer in <8 ms at 2× CPU before VBlank GDMA.

---

### E. Stage-Transition Vignettes
* **Shape & Fatigue Risk:** 4.5–5.5 s × 9 dungeons + 9 Riftwild entries = **~90 s of transitions per run** if unskipped. Even once-per-stage, 5.5 s before *every* biome interrupts roguelike flow.
  * **Fix:** Cut the separate 1 s black title card! Show the framed vignette immediately on fade-in with **Stage Name on row 15** and **Motto on row 16** (just like `stages.png` already mocks up!). Total duration drops to a punchy **2.8–3.2 s (170–190 f)**: 20 f fade in → 110 f walk + signature effect → 30 f fade/lift out.
  * **Skip rule:** Allow `A / B / START` from frame 8 onward. Add an Options toggle (`CUTSCENES: ONCE / OFF`).
* **Riftwild Enter/Leave:**
  * **Drop `Riftwild (leave)` (40 f reverse vignette).** Playing a closing Riftwild vignette *immediately followed by* a dungeon entry vignette creates a double-transition bottleneck (`Riftwild leave → black → Dungeon enter`). Walking into a Riftwild dungeon gate in gameplay is already the "leave" beat; cut straight to the dungeon's 3 s vignette.
  * **Hollow Phase:** Reusing the Riftwild vignette with a sickly cyan/violet palette swap + `HOLLOW RIFTWILD` text is super smart and costs 48 bytes.
* **Motto & Effect Polish (≤20 chars, stronger imagery):**
  * **Ember Depths:** `stages.png` (`THE KILN WAKES`) beats `THE PATH RUNS HOT`—drop the text swap and stick to `EMBER DEPTHS` / `THE KILN WAKES`.
  * **Toxic Mire:** `THE MIRE HAS A HEART` (20 chars, tight edge-to-edge) → `A BLACK HEART BEATS` (19 chars, punchier foreshadowing of Mire Heart).
  * **Bloodmoon:** `THE MOON IS BLEEDING` (20 chars, hits border) → `UNDER A BLEEDING SKY` or `BLOOD CALLS TO BLOOD` (18–20 chars; keep ≤18 chars so row 16 has 1-tile breathing room on each side!).
  * **Void Sanctum:** Replace LYC `SCY` bob (breaks vertical frame lines) with **4 OBJ floating stone shards** drifting upward + palette rift shimmer.

---

### F. Top 8 Changes for Single Revision Pass (Ranked)
1. **Replace LCD-off loading with 4-frame VBlank GDMA under black palettes** (`~2 KB/frame`), fix map+attr VRAM stride math (`2 KB` per 32×32 map), and apply `id ^ 0x80` remapping for `0x8800` signed tile addressing.
2. **Redraw Shot 4 (`intro.png`) with 9 dedicated 48×32 dark-silhouette boss busts** instead of raw gameplay room screenshots containing floor grids and player sprites.
3. **Fix Shot 7's lore/art mismatch** by replacing the 32 px human warrior with animal-vessel silhouette(s) looking *down* into the chasm (`DESCEND THE RIFTWILD / BIND THE DARKNESS`).
4. **Tighten the intro from 33 s to ~23 s** by merging Shots 2 & 3 into one pan-and-palette-dim shot (saving `3.2 KB` of duplicate valley tiles) and cutting `THE ROGUELIKE` from Shot 8 in favor of `CHOOSE YOUR VESSEL`.
5. **Fold the 1 s black stage card into the vignette screen** (`ROW 15: STAGE NAME`, `ROW 16: MOTTO`, matching `stages.png`) to trim vignettes to a brisk **3.0 s**, and cap all mottos at **≤18 chars** for 1-tile side margins.
6. **Cut the `Riftwild (leave)` vignette** so entering a dungeon gate transitions directly into that dungeon's vignette without back-to-back cutscenes.
7. **Fix Void Sanctum's signature effect** by swapping the LYC `SCY ±1` scanline wobble (which tears the left/right double-line frame border) for 4 drifting rock OBJs + palette shimmer.
8. **Clean up `trans.png` visual bugs:** replace Riftwild's two black-bar masks with jagged center-outward rift tiles, and darken Ember Depths' stone walkway + add dark outlines so light-coloured hero OBJs stay legible.
