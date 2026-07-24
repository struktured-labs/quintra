# Quintra — GBC Native + Rust dev-host tooling
# Runtime: C / GBDK-2020 / SDCC — only thing in the ROM
# Tooling:  Rust workspace under tools/ — never linked into ROM

GBDK    = /home/struktured/gbdk
LCC     = $(GBDK)/bin/lcc

PROJECT = quintra
SRCDIR  = src
OBJDIR  = obj
BINDIR  = rom/working
GENDIR  = $(SRCDIR)/generated
# External PyBoy curriculum checkpoints are developer artifacts, never ROM or
# SRAM data. Rebuild them after every linked cartridge so a tester never gets
# an emulator state whose manifest belongs to the previous ROM bytes.
STATE_OUT ?= $(CURDIR)/tmp/stage-states
MGBA_STATE_OUT ?= $(CURDIR)/tmp/mgba-states
MGBA_STATE_SMOKE_OUT ?= $(CURDIR)/tmp/mgba-states-smoke
MGBA_BIN ?= mgba-headless
TIMED_STATE_OUT ?= $(CURDIR)/tmp/timed-states
TIMED_MGBA_STATE_OUT ?= $(CURDIR)/tmp/timed-mgba-states
TIMED_MINUTES ?= 30
TIMED_STATE_START ?= $(STATE_OUT)/quintra-stage-04-entry-wolfkin-easy.pyboy
TIMED_CHECKPOINT ?= 30

# Keep uv self-contained inside the ignored workspace cache. Linked worktrees
# may expose a read-only home cache, and verification should never require
# system installs or writable global state.
UV_CACHE_DIR ?= $(CURDIR)/tmp/uv-cache
export UV_CACHE_DIR
PYBOY_SPEC ?= pyboy==2.7.0
PYBOY_RUN = uv run --quiet --with "$(PYBOY_SPEC)" python

# All .c under src/ (including generated)
# Link order affects autobank placement and therefore the ROM hash. `find`
# order varies by filesystem/copy history, so sort the manifest explicitly.
SRCS = $(sort $(shell find $(SRCDIR) -name '*.c' 2>/dev/null))
OBJS = $(SRCS:%.c=$(OBJDIR)/%.o)

# GBDK / SDCC flags — BANKED build (see docs/superpowers/specs/
# 2026-07-05-gbdk-banking-architecture.md). -autobank runs bankpack, which
# still auto-sizes the ROM. Gameplay banks are pinned explicitly: autobank's
# assignment heuristic depends on absolute checkout paths and changed hashes.
# DO NOT add -Wm-yo<n>: a fixed bank count suppresses the auto sizing and
# collapses all banked code back into banks 0-1 (silent boot-breakage).
LCCFLAGS  = -Wa-l -Wl-m -Wl-j
LCCFLAGS += -autobank
LCCFLAGS += -Wm-yt0x1B          # MBC5 + RAM + BATTERY (set via makebin header byte)
LCCFLAGS += -Wm-ya4             # 4 SRAM banks (32KB)
LCCFLAGS += -Wm-yC              # CGB only (Quintra is GBC-native)
LCCFLAGS += -Wm-yn"QUINTRA"     # cart/flash-tool header title
LCCFLAGS += -I$(SRCDIR) -I$(GENDIR)

.PHONY: all clean cleangen cleanall dirs gen build force-link force-title test verify preflight repro-check balance endurance fatal-report fixed-controller-matrix boss-pacing boss-curriculum-audit room-curriculum-audit picsean-endurance victory-proof final-sigil-proof media media-check play play-state play-mgba-state play-timed-state play-timed-mgba-state info check-balance-bot agent-events stall-maps stage-states mgba-states mgba-state-smoke timed-states timed-mgba-states
# Two-stage build: gen produces src/generated/*.c BEFORE SRCS is evaluated
# for the rom-link step. Without the recursive $(MAKE), Make captures SRCS
# at parse time and misses the generated files on a fresh build.
all: gen
	@$(MAKE) --no-print-directory build

build: dirs $(BINDIR)/$(PROJECT).gbc
	@$(PYBOY_RUN) scripts/make_stage_states.py \
		--rom "$(BINDIR)/$(PROJECT).gbc" --out "$(STATE_OUT)"

dirs:
	@mkdir -p $(OBJDIR) $(BINDIR) $(GENDIR)

# Rust codegen: content tables + sprite/tile art, both from typed Rust.
gen:
	@cargo build --release -q -p quintra-codegen -p quintra-assets
	@if [ ! -x target/release/quintra-codegen ] || [ ! -x target/release/quintra-assets ]; then \
		echo "[gen] FATAL: Rust tooling failed to build"; exit 1; \
	fi
	@target/release/quintra-codegen --content content --out $(GENDIR)
	@target/release/quintra-assets --out $(SRCDIR)/render/sprites_gen.c \
		--header-out $(SRCDIR)/render/sprites_gen.h

# All headers under src/ (+ generated). lcc/SDCC can't emit .d dep files here,
# so use a coarse dependency for ordinary headers. version.h is deliberately
# title-only; keeping it in this global list makes a one-character release
# footer bump rebuild the entire ROM even though no other translation unit can
# observe it.
HDRS = $(filter-out $(SRCDIR)/game/version.h,$(shell find $(SRCDIR) -name '*.h' 2>/dev/null))

# Compile each .c under any subdir of src/
$(OBJDIR)/%.o: %.c $(HDRS)
	@mkdir -p $(dir $@)
	$(LCC) $(LCCFLAGS) -c -o $@ $<

# The title renders QUINTRA_VERSION directly from version.h. A version edit
# made within the same one-second filesystem timestamp as a prior build can
# otherwise leave title.o looking newer than its header. Recompile this tiny
# unit every build so a release ROM can never advertise its previous tag.
force-title:

$(OBJDIR)/src/game/title.o: force-title $(SRCDIR)/game/version.h

# Link to ROM, then verify the memory layout. The layout check exists
# because the linker SILENTLY placed init code past 0x8000 when the flat
# 32KB image overflowed (white screen at boot, shipped 6 broken commits).
# Always perform the final link. GBDK's map/NOI side artifacts and coarse
# generated-header dependencies can otherwise leave a newly compiled object
# newer than an apparently-current ROM, which is unacceptable for a flash or
# GitHub release build.
force-link:

$(BINDIR)/$(PROJECT).gbc: $(OBJS) Makefile force-link
	$(LCC) $(LCCFLAGS) -o $@ $(OBJS)
	@python3 scripts/check_rom_layout.py $(BINDIR)/$(PROJECT)

clean:
	rm -rf $(OBJDIR) $(BINDIR)/$(PROJECT).gbc $(BINDIR)/$(PROJECT).map $(BINDIR)/$(PROJECT).noi

cleangen:
	rm -rf $(GENDIR)/*

cleanall: clean cleangen
	cargo clean

# Fast live-cartridge test (build + boot + state-asserted screenshots).
# Keep this honest: the old target swallowed a missing Phase-3 script and
# reported success without exercising the ROM.
test: all
	bash scripts/test_smoke.sh $(BINDIR)/$(PROJECT).gbc

# The whole verification stack: Rust unit/property/golden tests, the
# headless gameplay smoke (pixel + state asserts), and the cross-seam
# procgen parity check (Rust reference vs the ROM's WRAM).
verify: all check-balance-bot
	bash scripts/capture_media.sh $(BINDIR)/$(PROJECT).gbc
	python3 scripts/check_media.py $(BINDIR)/$(PROJECT).gbc
	python3 scripts/report_budget.py $(BINDIR)/$(PROJECT)
	python3 scripts/check_cartridge.py $(BINDIR)/$(PROJECT).gbc
	cargo test -q
	cargo build --release -q -p quintra-procgen
	bash scripts/test_smoke.sh
	uv run --quiet --with pyboy python scripts/test_procgen_parity.py
	uv run --quiet --with pyboy python scripts/test_town.py
	$(PYBOY_RUN) scripts/test_town_compass.py
	uv run --quiet --with pyboy python scripts/test_cartographer_scout.py
	uv run --quiet --with pyboy python scripts/test_stage_archetypes.py
	$(PYBOY_RUN) scripts/test_procgen_variety.py
	$(PYBOY_RUN) scripts/test_stage_entry_pacing.py
	uv run --quiet --with pyboy python scripts/test_music.py
	python3 scripts/music_sheet.py --self-test
	uv run --quiet --with pyboy python scripts/test_melee_visual.py
	uv run --quiet --with pyboy python scripts/test_melee_special_guard.py
	uv run --quiet --with pyboy python scripts/test_wolfkin_forms.py
	uv run --quiet --with pyboy python scripts/test_champion_animation.py
	uv run --quiet --with pyboy python scripts/test_rift_flail.py
	uv run --quiet --with pyboy python scripts/test_astral_spear.py
	uv run --quiet --with pyboy python scripts/test_performance.py
	uv run --quiet --with pyboy python scripts/test_run_clock.py
	uv run --quiet --with pyboy python scripts/test_compass_map.py
	$(PYBOY_RUN) scripts/test_quest_guidance.py
	python3 scripts/test_dungeon_topology.py
	$(PYBOY_RUN) scripts/test_dungeon_courts.py
	$(PYBOY_RUN) scripts/test_difficulty_mode.py
	$(PYBOY_RUN) scripts/test_boss_threshold.py
	uv run --quiet --with pyboy python scripts/test_inventory_action_tip.py
	uv run --quiet --with pyboy python scripts/test_full_mp_hud.py
	$(PYBOY_RUN) scripts/test_pyboy_env.py
	python3 scripts/test_playtest_report.py
	$(PYBOY_RUN) scripts/test_stage_states.py
	python3 scripts/make_mgba_states.py \
		--rom "$(BINDIR)/$(PROJECT).gbc" --out "$(MGBA_STATE_SMOKE_OUT)" \
		--mgba "$(MGBA_BIN)" --champion wolfkin --difficulty easy
	$(PYBOY_RUN) scripts/test_puzzles.py
	$(PYBOY_RUN) scripts/test_transition_audio.py
	$(PYBOY_RUN) scripts/test_timed_states.py
	$(PYBOY_RUN) scripts/test_controller_policy.py
	uv run --quiet --with pyboy python scripts/test_title_version.py
	uv run --quiet --with pyboy python scripts/test_boss_identity.py
	uv run --quiet --with pyboy python scripts/test_boss_movement.py
	$(PYBOY_RUN) scripts/test_colossal_crystal.py
	$(PYBOY_RUN) scripts/test_colossal_serpent.py
	$(PYBOY_RUN) scripts/test_colossal_cinder.py
	$(PYBOY_RUN) scripts/test_colossal_spider.py
	$(PYBOY_RUN) scripts/test_colossal_mire.py
	$(PYBOY_RUN) scripts/test_colossal_reaper.py
	$(PYBOY_RUN) scripts/test_colossal_golem.py
	$(PYBOY_RUN) scripts/test_colossal_hydra.py
	$(PYBOY_RUN) scripts/test_colossal_void.py
	uv run --quiet --with pyboy python scripts/test_void_collapse.py
	uv run --quiet --with pyboy python scripts/test_boss_rewards.py
	uv run --quiet --with pyboy python scripts/test_convergence_boss_cap.py
	uv run --quiet --with pyboy python scripts/test_convergence_transform.py
	uv run --quiet --with pyboy python scripts/test_enemy_identity.py
	bash scripts/test_enemy_coverage_config.sh
	uv run --quiet --with pyboy python scripts/test_hornet_swarm.py
	uv run --quiet --with pyboy python scripts/test_ooze_cycle.py
	uv run --quiet --with pyboy python scripts/test_ember_movement_roster.py
	uv run --quiet --with pyboy python scripts/test_dusk_midge.py
	uv run --quiet --with pyboy python scripts/test_cinder_kite.py
	uv run --quiet --with pyboy python scripts/test_bog_toad.py
	uv run --quiet --with pyboy python scripts/test_frost_lancer.py
	uv run --quiet --with pyboy python scripts/test_bramble_sprite.py
	uv run --quiet --with pyboy python scripts/test_shard_crab.py
	uv run --quiet --with pyboy python scripts/test_void_halo.py
	uv run --quiet --with pyboy python scripts/test_sunwheel.py
	uv run --quiet --with pyboy python scripts/test_bellwarden.py
	uv run --quiet --with pyboy python scripts/test_enemy_density.py
	uv run --quiet --with pyboy python scripts/test_score.py
	uv run --quiet --with pyboy python scripts/test_block_lower_edge.py
	uv run --quiet --with pyboy python scripts/test_doors.py
	uv run --quiet --with pyboy python scripts/test_rift_sigil.py
	uv run --quiet --with pyboy python scripts/test_stage8_sigil_path.py
	uv run --quiet --with pyboy python scripts/test_overworld.py
	$(PYBOY_RUN) scripts/test_riftwild_landmarks.py
	uv run --quiet --with pyboy python scripts/test_riftwell.py
	uv run --quiet --with pyboy python scripts/test_victory.py
	uv run --quiet --with pyboy python scripts/test_gameover.py
	uv run --quiet --with pyboy python scripts/test_damage_hud.py
	uv run --quiet --with pyboy python scripts/test_corvin_hp_bar.py
	uv run --quiet --with pyboy python scripts/test_heart_pickup.py
	uv run --quiet --with pyboy python scripts/test_vampiric_sigil.py
	uv run --quiet --with pyboy python scripts/test_shop_surge.py
	uv run --quiet --with pyboy python scripts/test_sauran_shield.py
	uv run --quiet --with pyboy python scripts/test_sauran_regen.py
	uv run --quiet --with pyboy python scripts/test_surge.py
	bash scripts/test_miniboss_escorts.sh $(BINDIR)/$(PROJECT).gbc
	uv run --quiet --with pyboy python scripts/test_miniboss_spawn_reach.py
	bash scripts/test_rift_sigil_pathing.sh $(BINDIR)/$(PROJECT).gbc
	bash scripts/test_sigil_sanctuary_return.sh $(BINDIR)/$(PROJECT).gbc
	bash scripts/test_picsean_victory_replay.sh $(BINDIR)/$(PROJECT).gbc
	bash scripts/test_weapon_trade_policy.sh $(BINDIR)/$(PROJECT).gbc
	bash scripts/test_town_continuation.sh $(BINDIR)/$(PROJECT).gbc
	bash scripts/test_wolfkin_cadence_policy.sh $(BINDIR)/$(PROJECT).gbc
	bash scripts/test_wolfkin_leech_lane.sh $(BINDIR)/$(PROJECT).gbc
	bash scripts/test_wolfkin_unsealed_exit.sh $(BINDIR)/$(PROJECT).gbc
	bash scripts/test_giant_wall_dash.sh $(BINDIR)/$(PROJECT).gbc
	bash scripts/test_balance_observation_trace.sh $(BINDIR)/$(PROJECT).gbc
	bash scripts/test_picsean_convergence_policy.sh $(BINDIR)/$(PROJECT).gbc
	bash scripts/test_wolfkin_mire_entry.sh $(BINDIR)/$(PROJECT).gbc
	bash scripts/test_boss_relic_collection.sh $(BINDIR)/$(PROJECT).gbc
	uv run --quiet --with pyboy python scripts/test_leech_detach.py
	bash scripts/test_sauran_boss_policy.sh $(BINDIR)/$(PROJECT).gbc
	bash scripts/test_sauran_miniboss_guard.sh $(BINDIR)/$(PROJECT).gbc
	bash scripts/test_sauran_frost_miniboss_lane.sh $(BINDIR)/$(PROJECT).gbc
	bash scripts/test_sauran_open_room_exit.sh $(BINDIR)/$(PROJECT).gbc
	bash scripts/test_sauran_rope_policy.sh $(BINDIR)/$(PROJECT).gbc
	bash scripts/test_death_telemetry.sh $(BINDIR)/$(PROJECT).gbc
	bash scripts/test_corvin_boss_policy.sh $(BINDIR)/$(PROJECT).gbc
	bash scripts/test_corvin_spore_policy.sh $(BINDIR)/$(PROJECT).gbc
	bash scripts/test_corvin_riftwild_pathing.sh $(BINDIR)/$(PROJECT).gbc
	bash scripts/test_vespine_boss_policy.sh $(BINDIR)/$(PROJECT).gbc
	bash scripts/test_vespine_flutterbat_pathing.sh $(BINDIR)/$(PROJECT).gbc
	bash scripts/test_vespine_rope_escape.sh $(BINDIR)/$(PROJECT).gbc
	bash scripts/test_balance_replay.sh $(BINDIR)/$(PROJECT).gbc

# Release/hardware gate: static cartridge header plus a true battery-backed
# suspend across emulator process restart. Safe to run before GB Operator flash.
preflight: all repro-check
	python3 scripts/check_cartridge.py $(BINDIR)/$(PROJECT).gbc
	uv run --quiet --with pyboy python scripts/test_suspend.py
	uv run --quiet --with pillow python scripts/check_media.py

# Fresh-copy determinism: rebuild without obj/target/current ROM and demand
# exact cartridge bytes. This catches filesystem-dependent source/link order.
repro-check: all
	bash scripts/check_reproducible.sh

media: all
	bash scripts/capture_media.sh

media-check: all
	uv run --quiet --with pillow python scripts/check_media.py

# Controller-only heuristic agents. Unlike smoke tests, these receive no HP
# or entity writes and produce comparable per-class run telemetry.
check-balance-bot:
	@luac -p scripts/quintra_balance_bot.lua

balance: all check-balance-bot
	QUINTRA_BALANCE_MIN_SHOP_RUNS=2 \
	QUINTRA_BALANCE_MAX_COMBAT_STALLS=0 QUINTRA_BALANCE_MAX_ROUTE_STALLS=0 \
	QUINTRA_BALANCE_MAX_WORLD_HOPS=150 \
	bash scripts/run_balance_bot.sh $(BINDIR)/$(PROJECT).gbc

# Turn retained QUINTRA_BALANCE_DEBUG_DIR event logs into an actionable
# collision/ability summary. Example: make agent-events AGENT_EVENTS_DIR=tmp/agent-debug
agent-events:
	@test -n "$(AGENT_EVENTS_DIR)" || (echo "set AGENT_EVENTS_DIR=tmp/agent-debug" >&2; exit 2)
	python3 scripts/report_agent_events.py "$(AGENT_EVENTS_DIR)"

# Decode the read-only controller watchdog's compact geometry artifacts.
# Example: make stall-maps STALL_MAP_DIR=tmp/agent-debug
stall-maps:
	@test -n "$(STALL_MAP_DIR)" || (echo "set STALL_MAP_DIR=tmp/agent-debug" >&2; exit 2)
	python3 scripts/report_stall_maps.py "$(STALL_MAP_DIR)" --last

# Controller-only policy search: compares giant movement plus optional lunge
# and Sauran-shield body-buffer policies using real ROM and ordinary inputs.
# Defaults to Sauran + Corvin; override QUINTRA_POLICY_* to widen the experiment.
policy-sweep: all check-balance-bot
	bash scripts/sweep_giant_policy.sh $(BINDIR)/$(PROJECT).gbc

# Long-form pre-show soak: three entropy samples per champion and enough
# emulated time for a cautious full clear. Every champion must clear twice;
# missing reports, skipped economies, and live-enemy/route stalls fail the target.
# Every generated enemy ID must appear in the fresh controller matrix. The
# list is derived from codegen, so a new monster cannot be silently omitted.
endurance: all check-balance-bot
	QUINTRA_BALANCE_REPS=3 QUINTRA_BALANCE_FRAMES=90000 \
	QUINTRA_BALANCE_MIN_WINS=2 QUINTRA_BALANCE_MIN_SHOP_RUNS=3 \
	QUINTRA_BALANCE_MAX_COMBAT_STALLS=0 \
	QUINTRA_BALANCE_MAX_ROUTE_STALLS=0 QUINTRA_BALANCE_MAX_WORLD_HOPS=150 \
	QUINTRA_BALANCE_REQUIRED_ENEMIES="$$(bash scripts/released_enemy_ids.sh)" \
	QUINTRA_BALANCE_STALL_FRAMES=7200 \
	QUINTRA_BALANCE_OUT=$(CURDIR)/tmp/endurance-runs.csv \
	bash scripts/run_balance_bot.sh $(BINDIR)/$(PROJECT).gbc

fatal-report:
	python3 scripts/report_fatal_context.py tmp/endurance-runs.csv

# Fixed-world all-champion diagnostic: every vessel uses controller input to
# enter the same frame-derived procgen run. It reports honest outcomes rather
# than claiming the current balance already meets the endurance delivery bar.
fixed-controller-matrix: all check-balance-bot
	bash scripts/fixed_controller_matrix.sh $(BINDIR)/$(PROJECT).gbc

# Human-facing boss tuning starts with observed cartridge timing, not only
# health math. This reuses the paired fixed-world pilot and prints per-stage
# median clear frames with the class/fatal context alongside it. Its very high
# stall threshold makes it a diagnostic report; `endurance` remains the gate.
boss-pacing: fixed-controller-matrix
	cargo run --quiet --manifest-path Cargo.toml -p quintra-mgba -- \
		report $(CURDIR)/tmp/fixed-controller-matrix.csv --runs 1 --classes 5 \
		--min-wins 0 --min-shop-runs 0 --stall-frames 999999

# Quick external-policy diagnostic over all progression-matched live bosses.
# This is not a delivery balance gate: the mGBA controller/replay remains the
# authoritative whole-run evidence, while this catches PyBoy curriculum and
# observation regressions (walkability, class identity, projectile lanes).
AUDIT_DIFFICULTY ?= normal
boss-curriculum-audit: stage-states
	@$(PYBOY_RUN) scripts/audit_boss_curriculum.py \
		--rom "$(BINDIR)/$(PROJECT).gbc" --state-dir "$(STATE_OUT)" \
		--difficulty "$(AUDIT_DIFFICULTY)"

# Complement the giant sample with the ordinary room at each progression-
# matched Normal stage entry. Reports exits, deaths, HP loss, density, and
# projectile pressure independently so boss and room tuning cannot mask one
# another.
room-curriculum-audit: stage-states
	@$(PYBOY_RUN) scripts/audit_room_curriculum.py \
		--rom "$(BINDIR)/$(PROJECT).gbc" --state-dir "$(STATE_OUT)" \
		--difficulty "$(AUDIT_DIFFICULTY)"

# Four completed Picsean seeds; complements the all-class soak above.
picsean-endurance: all check-balance-bot
	bash scripts/test_picsean_endurance.sh $(BINDIR)/$(PROJECT).gbc

# Deterministic all-nine-boss controller proof plus clean-emulator replay.
victory-proof: all check-balance-bot
	bash scripts/test_picsean_victory_replay.sh $(BINDIR)/$(PROJECT).gbc

# Targeted controller proof for the formerly-stalled final mandatory fixture.
final-sigil-proof: all check-balance-bot
	bash scripts/test_final_sigil_controller.sh $(BINDIR)/$(PROJECT).gbc

# Human play
play: all
	@bash mgba-qt.sh $(BINDIR)/$(PROJECT).gbc

# External emulator fixtures for testing/RL at dungeon, post-boss Riftwild,
# and village milestones. These are PyBoy save states in tmp/, never ROM or
# battery-SRAM data. `build` refreshes the
# requested output after the ROM link; this target remains a discoverable
# explicit command and accepts STATE_OUT for an alternate curriculum set.
stage-states: all

# Native mGBA equivalents for hands-on testing in mGBA-Qt. Generation covers
# the same 460 champion/difficulty/checkpoint combinations as the PyBoy set and
# independently starts one file from every family through mGBA's -t loader.
mgba-states: all
	@python3 scripts/make_mgba_states.py \
		--rom "$(BINDIR)/$(PROJECT).gbc" --out "$(MGBA_STATE_OUT)" \
		--mgba "$(MGBA_BIN)"

# Fast native-format contract used by `make verify`.
mgba-state-smoke:
	@python3 scripts/make_mgba_states.py \
		--rom "$(BINDIR)/$(PROJECT).gbc" --out "$(MGBA_STATE_SMOKE_OUT)" \
		--mgba "$(MGBA_BIN)" --champion wolfkin --difficulty easy

# Controller-driven periodic capture. The default begins from the plausible
# stage-four Wolfkin Easy curriculum and emits a fresh PyBoy checkpoint every
# five emulated minutes for thirty minutes. If an entire interval makes no
# forward progress, the external trainer records a manifest-bound advance to
# the next stage entry rather than publishing six copies of one stuck room.
timed-states: all
	@$(PYBOY_RUN) scripts/run_pyboy_checkpoints.py \
		--rom "$(BINDIR)/$(PROJECT).gbc" --out "$(TIMED_STATE_OUT)" \
		--state "$(TIMED_STATE_START)" \
		--minutes "$(TIMED_MINUTES)" --checkpoint-minutes 5

# Preferred hands-on training set: the real mGBA controller plays one fixed
# Easy Picsean expedition and serializes native states every five emulated
# minutes. Every file is then cold-loaded through mGBA's -t startup path.
timed-mgba-states: all check-balance-bot
	@python3 scripts/make_timed_mgba_states.py \
		--rom "$(BINDIR)/$(PROJECT).gbc" --out "$(TIMED_MGBA_STATE_OUT)" \
		--mgba "$(MGBA_BIN)" --minutes "$(TIMED_MINUTES)" \
		--checkpoint-minutes 5

# Open a manifest-verified external checkpoint for hands-on deep testing.
# Closing the window writes passive room/HP/map/boss timing telemetry under
# tmp/human-playtests; the observer never supplies input or mutates cartridge
# state. Set PLAYTEST_REPORT_DIR to retain the JSON somewhere else.
# Examples: `make play-state STAGE=3`,
# `make play-state STAGE=3 CHECKPOINT=court DIFFICULTY=easy`,
# `make play-state STAGE=7 CHECKPOINT=sanctuary HERO=sauran`,
# `make play-state STAGE=7 CHECKPOINT=boss HERO=sauran`, or
# `make play-state STAGE=1 CHECKPOINT=riftwild DIFFICULTY=easy`, or
# `make play-state STAGE=3 CHECKPOINT=village DIFFICULTY=easy`.
STAGE ?= 1
DIFFICULTY ?= normal
CHECKPOINT ?= entry
HERO ?= wolfkin
PLAYTEST_REPORT_DIR ?= $(CURDIR)/tmp/human-playtests
play-state:
	@$(PYBOY_RUN) scripts/play_stage_state.py --rom "$(BINDIR)/$(PROJECT).gbc" \
		--state-dir "$(STATE_OUT)" --stage "$(STAGE)" --difficulty "$(DIFFICULTY)" \
		--checkpoint "$(CHECKPOINT)" --champion "$(HERO)" \
		--report-dir "$(PLAYTEST_REPORT_DIR)"

# Open the matching ROM-bound native state in the project's software-rendered
# mGBA-Qt wrapper. Unlike play-state this is the exact emulator the human uses.
play-mgba-state:
	@python3 scripts/play_mgba_state.py --rom "$(BINDIR)/$(PROJECT).gbc" \
		--state-dir "$(MGBA_STATE_OUT)" --stage "$(STAGE)" \
		--difficulty "$(DIFFICULTY)" --checkpoint "$(CHECKPOINT)" \
		--champion "$(HERO)"

# Open one of the controller-produced five-minute checkpoints without a ROM
# rebuild. The manifest rejects stale cartridge, PyBoy, or state bytes; the
# same readiness pause and passive human report used by play-state apply here.
play-timed-state:
	@$(PYBOY_RUN) scripts/play_timed_state.py --rom "$(BINDIR)/$(PROJECT).gbc" \
		--state-dir "$(TIMED_STATE_OUT)" --minutes "$(TIMED_CHECKPOINT)"

# Open the equivalent native mGBA training beat (5, 10, ... 30 minutes).
play-timed-mgba-state:
	@python3 scripts/play_timed_mgba_state.py --rom "$(BINDIR)/$(PROJECT).gbc" \
		--state-dir "$(TIMED_MGBA_STATE_OUT)" --minutes "$(TIMED_CHECKPOINT)"

info:
	@echo "Quintra build info:"
	@echo "  Project:   $(PROJECT)"
	@echo "  Sources:   $(words $(SRCS)) .c files"
	@echo "  Output:    $(BINDIR)/$(PROJECT).gbc"
	@echo "  Toolchain: $(LCC)"
