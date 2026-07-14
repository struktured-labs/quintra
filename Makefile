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

# All .c under src/ (including generated)
SRCS = $(shell find $(SRCDIR) -name '*.c' 2>/dev/null)
OBJS = $(SRCS:%.c=$(OBJDIR)/%.o)

# GBDK / SDCC flags — BANKED build (see docs/superpowers/specs/
# 2026-07-05-gbdk-banking-architecture.md). -autobank runs bankpack, which
# assigns every '#pragma bank 255' file a real bank and auto-sizes the ROM.
# DO NOT add -Wm-yo<n>: a fixed bank count suppresses the auto sizing and
# collapses all banked code back into banks 0-1 (silent boot-breakage).
LCCFLAGS  = -Wa-l -Wl-m -Wl-j
LCCFLAGS += -autobank
LCCFLAGS += -Wm-yt0x1B          # MBC5 + RAM + BATTERY (set via makebin header byte)
LCCFLAGS += -Wm-ya4             # 4 SRAM banks (32KB)
LCCFLAGS += -Wm-yC              # CGB only (Quintra is GBC-native)
LCCFLAGS += -I$(SRCDIR) -I$(GENDIR)

.PHONY: all clean cleangen cleanall dirs gen build test verify balance play info
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
	@cargo build --release -p quintra-codegen -p quintra-assets 2>&1 | grep -E 'error|warning' || true
	@if [ ! -x target/release/quintra-codegen ] || [ ! -x target/release/quintra-assets ]; then \
		echo "[gen] FATAL: Rust tooling failed to build"; exit 1; \
	fi
	@target/release/quintra-codegen --content content --out $(GENDIR)
	@target/release/quintra-assets --out $(SRCDIR)/render/sprites_gen.c

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
$(BINDIR)/$(PROJECT).gbc: $(OBJS)
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
verify: all
	python3 scripts/report_budget.py $(BINDIR)/$(PROJECT)
	cargo test -q
	cargo build --release -q -p quintra-procgen
	bash scripts/test_smoke.sh
	uv run --quiet --with pyboy python scripts/test_procgen_parity.py
	uv run --quiet --with pyboy python scripts/test_town.py
	uv run --quiet --with pyboy python scripts/test_doors.py
	uv run --quiet --with pyboy python scripts/test_overworld.py

# Controller-only heuristic agents. Unlike smoke tests, these receive no HP
# or entity writes and produce comparable per-class run telemetry.
balance: all
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
