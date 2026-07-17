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

# Keep uv self-contained inside the ignored workspace cache. Linked worktrees
# may expose a read-only home cache, and verification should never require
# system installs or writable global state.
UV_CACHE_DIR ?= $(CURDIR)/tmp/uv-cache
export UV_CACHE_DIR

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

.PHONY: all clean cleangen cleanall dirs gen build test verify preflight repro-check balance endurance media media-check play info check-balance-bot
# Two-stage build: gen produces src/generated/*.c BEFORE SRCS is evaluated
# for the rom-link step. Without the recursive $(MAKE), Make captures SRCS
# at parse time and misses the generated files on a fresh build.
all: gen
	@$(MAKE) --no-print-directory build

build: dirs $(BINDIR)/$(PROJECT).gbc

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
# so use a coarse dependency: any header change rebuilds every object. Slower
# but correct — a stale-header build once shipped a wrong constant.
HDRS = $(shell find $(SRCDIR) -name '*.h' 2>/dev/null)

# Compile each .c under any subdir of src/
$(OBJDIR)/%.o: %.c $(HDRS)
	@mkdir -p $(dir $@)
	$(LCC) $(LCCFLAGS) -c -o $@ $<

# Link to ROM, then verify the memory layout. The layout check exists
# because the linker SILENTLY placed init code past 0x8000 when the flat
# 32KB image overflowed (white screen at boot, shipped 6 broken commits).
$(BINDIR)/$(PROJECT).gbc: $(OBJS) Makefile
	$(LCC) $(LCCFLAGS) -o $@ $(OBJS)
	@python3 scripts/check_rom_layout.py $(BINDIR)/$(PROJECT)

clean:
	rm -rf $(OBJDIR) $(BINDIR)/$(PROJECT).gbc $(BINDIR)/$(PROJECT).map $(BINDIR)/$(PROJECT).noi

cleangen:
	rm -rf $(GENDIR)/*

cleanall: clean cleangen
	cargo clean

# Headless test (build + boot + screenshots)
test: all
	@bash scripts/test_headless.sh $(BINDIR)/$(PROJECT).gbc 2>/dev/null || \
		echo "[test] headless harness not yet wired (Phase 3)"

# The whole verification stack: Rust unit/property/golden tests, the
# headless gameplay smoke (pixel + state asserts), and the cross-seam
# procgen parity check (Rust reference vs the ROM's WRAM).
verify: all check-balance-bot
	python3 scripts/report_budget.py $(BINDIR)/$(PROJECT)
	python3 scripts/check_cartridge.py $(BINDIR)/$(PROJECT).gbc
	cargo test -q
	cargo build --release -q -p quintra-procgen
	bash scripts/test_smoke.sh
	uv run --quiet --with pyboy python scripts/test_procgen_parity.py
	uv run --quiet --with pyboy python scripts/test_town.py
	uv run --quiet --with pyboy python scripts/test_stage_archetypes.py
	uv run --quiet --with pyboy python scripts/test_music.py
	uv run --quiet --with pyboy python scripts/test_melee_visual.py
	uv run --quiet --with pyboy python scripts/test_performance.py
	uv run --quiet --with pyboy python scripts/test_run_clock.py
	uv run --quiet --with pyboy python scripts/test_title_version.py
	uv run --quiet --with pyboy python scripts/test_boss_identity.py
	uv run --quiet --with pyboy python scripts/test_enemy_identity.py
	uv run --quiet --with pyboy python scripts/test_score.py
	uv run --quiet --with pyboy python scripts/test_doors.py
	uv run --quiet --with pyboy python scripts/test_rift_sigil.py
	uv run --quiet --with pyboy python scripts/test_overworld.py
	uv run --quiet --with pyboy python scripts/test_victory.py
	uv run --quiet --with pyboy python scripts/test_gameover.py
	uv run --quiet --with pyboy python scripts/test_damage_hud.py
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

# Long-form pre-show soak: three entropy samples per champion and enough
# emulated time for a cautious full clear. Every champion must clear twice;
# missing reports, skipped economies, and live-enemy/route stalls fail the target.
endurance: all check-balance-bot
	QUINTRA_BALANCE_REPS=3 QUINTRA_BALANCE_FRAMES=90000 \
	QUINTRA_BALANCE_MIN_WINS=2 QUINTRA_BALANCE_MIN_SHOP_RUNS=3 \
	QUINTRA_BALANCE_MAX_COMBAT_STALLS=0 \
	QUINTRA_BALANCE_MAX_ROUTE_STALLS=0 QUINTRA_BALANCE_MAX_WORLD_HOPS=150 \
	QUINTRA_BALANCE_REQUIRED_ENEMIES='0 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18' \
	QUINTRA_BALANCE_STALL_FRAMES=7200 \
	QUINTRA_BALANCE_OUT=$(CURDIR)/tmp/endurance-runs.csv \
	bash scripts/run_balance_bot.sh $(BINDIR)/$(PROJECT).gbc

# Human play
play: all
	@bash mgba-qt.sh $(BINDIR)/$(PROJECT).gbc

info:
	@echo "Quintra build info:"
	@echo "  Project:   $(PROJECT)"
	@echo "  Sources:   $(words $(SRCS)) .c files"
	@echo "  Output:    $(BINDIR)/$(PROJECT).gbc"
	@echo "  Toolchain: $(LCC)"
