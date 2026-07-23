-- CLI-startup verifier for a native mGBA state loaded with -t.
local OUT = assert(os.getenv("QUINTRA_MGBA_VERIFY_OUT"))
local RS = assert(tonumber(os.getenv("QUINTRA_RS_ADDR")))
local PL = assert(tonumber(os.getenv("QUINTRA_PL_ADDR")))
local LS = assert(tonumber(os.getenv("QUINTRA_SCREEN_ADDR")))
local ROOM = assert(tonumber(os.getenv("QUINTRA_EXPECT_ROOM")))
local STAGE = assert(tonumber(os.getenv("QUINTRA_EXPECT_STAGE")))
local WORLD = assert(tonumber(os.getenv("QUINTRA_EXPECT_WORLD")))
local CLASS_ID = assert(tonumber(os.getenv("QUINTRA_EXPECT_CLASS")))
local DIFFICULTY = assert(tonumber(os.getenv("QUINTRA_EXPECT_DIFFICULTY")))

for _ = 1, 8 do emu:runFrame() end
local ok = emu:read8(RS + 1) == ROOM
    and emu:read8(RS + 11) == STAGE
    and emu:read8(RS + 17) == WORLD
    and emu:read8(RS + 26) == DIFFICULTY
    and emu:read8(PL) == CLASS_ID
    and emu:read8(PL + 2) > 0
    and emu:read8(LS) == 5
local result = assert(io.open(OUT, "w"))
result:write(ok and "PASS\n" or string.format(
    "FAIL room=%d stage=%d world=%d difficulty=%d class=%d screen=%d\n",
    emu:read8(RS + 1), emu:read8(RS + 11), emu:read8(RS + 17),
    emu:read8(RS + 26), emu:read8(PL), emu:read8(LS)))
result:close()
emu.frontend:quit()
