-- Live palette editor — polls /tmp/live_palettes.txt and writes CGB CRAM
local f = 0
local last_hash = 0
local PAL_FILE = "/tmp/live_palettes.txt"
local SENTINEL = "/tmp/live_palettes_lua.log"

-- Log to sentinel file (since mGBA print may not go to stdout)
local function log(msg)
    local fh = io.open(SENTINEL, "a")
    if fh then
        fh:write(msg .. "\n")
        fh:close()
    end
end

-- Reset log on startup
local fh = io.open(SENTINEL, "w")
if fh then fh:write("live_palettes.lua loaded at start\n"); fh:close() end

local function parse_color(s)
    if #s == 6 then
        local r = tonumber(s:sub(1,2), 16) or 0
        local g = tonumber(s:sub(3,4), 16) or 0
        local b = tonumber(s:sub(5,6), 16) or 0
        local r5 = math.floor(r * 31 / 255)
        local g5 = math.floor(g * 31 / 255)
        local b5 = math.floor(b * 31 / 255)
        return (b5 << 10) | (g5 << 5) | r5
    elseif #s == 4 then
        return tonumber(s, 16) or 0
    end
    return 0
end

-- Parsed file contains:
--   writes:    list of palette overrides applied every frame
--   force:     {addr=value, ...} - HRAM/WRAM bytes to set every frame (e.g. FFBF)
--   teleport:  {addr=value, ...} - one-shot writes (applied once then cleared)
local function load_palettes(path)
    local fh = io.open(path, "r")
    if not fh then return nil end
    local txt = fh:read("*all")
    fh:close()
    local result = {writes = {}, force = {}, teleport = nil}
    for line in txt:gmatch("[^\r\n]+") do
        if line:sub(1,1) == "#" then
            -- comment, skip
        elseif line:match("^TELEPORT:1") then
            -- one-shot teleport sentinel (other lines on same write supply
            -- the FFBA/D880/FFB7/FFBF values via force, but we copy them
            -- into the teleport one-shot slot and clear force for next frame)
            result.teleport = result.force
            result.force = {}  -- teleport is one-shot, don't keep forcing
        else
            local kind, pal_idx, colors = line:match("^(OBJ)(%d):(.+)$")
            if not kind then
                kind, pal_idx, colors = line:match("^(BG)(%d):(.+)$")
            end
            if kind and pal_idx then
                local is_obj = kind == "OBJ"
                pal_idx = tonumber(pal_idx)
                for entry in colors:gmatch("[^,]+") do
                    local ci, cv = entry:match("^%s*(%d+)=(%w+)%s*$")
                    if ci and cv then
                        ci = tonumber(ci)
                        local val15 = parse_color(cv)
                        local base = pal_idx * 8 + ci * 2
                        table.insert(result.writes, {
                            is_obj = is_obj, idx = base,
                            lo = val15 & 0xFF, hi = (val15 >> 8) & 0xFF,
                        })
                    end
                end
            else
                -- Try byte-write directives: FFBF:N, FFBA:N, D880:0xXX, FFB7:0xXX
                local reg, val = line:match("^(%w+):(%S+)$")
                if reg and val then
                    local v
                    if val:sub(1,2) == "0x" or val:sub(1,2) == "0X" then
                        v = tonumber(val:sub(3), 16)
                    else
                        v = tonumber(val)
                    end
                    if v then
                        local addr
                        if reg == "FFBF" then addr = 0xFFBF
                        elseif reg == "FFBA" then addr = 0xFFBA
                        elseif reg == "FFB7" then addr = 0xFFB7
                        elseif reg == "D880" then addr = 0xD880
                        elseif reg == "FFBE" then addr = 0xFFBE
                        elseif reg == "FFC0" then addr = 0xFFC0
                        elseif reg == "FFC1" then addr = 0xFFC1
                        elseif reg == "FFBD" then addr = 0xFFBD
                        elseif reg == "FFD0" then addr = 0xFFD0
                        end
                        if addr then
                            result.force[addr] = v & 0xFF
                        end
                    end
                end
            end
        end
    end
    return result
end

local function apply_writes(writes)
    if not writes or #writes == 0 then return end
    for _, w in ipairs(writes) do
        if w.is_obj then
            emu:write8(0xFF6A, w.idx)
            emu:write8(0xFF6B, w.lo)
            emu:write8(0xFF6A, w.idx + 1)
            emu:write8(0xFF6B, w.hi)
        else
            emu:write8(0xFF68, w.idx)
            emu:write8(0xFF69, w.lo)
            emu:write8(0xFF68, w.idx + 1)
            emu:write8(0xFF69, w.hi)
        end
    end
end

-- Cached parsed data — applied EVERY frame so the game's cond_pal
-- can't override our changes when it triggers a palette reload on
-- state change (room transition, miniboss spawn, etc.)
local cached = nil
local pending_teleport = nil

callbacks:add("frame", function()
    f = f + 1
    if f == 30 then log("Lua frame=30, polling /tmp/live_palettes.txt") end

    -- Check for file changes every 30 frames (~0.5s).
    if f % 30 == 0 then
        local fh = io.open(PAL_FILE, "r")
        if fh then
            local content = fh:read("*all")
            fh:close()
            local hash = 0
            for i = 1, #content do
                hash = (hash * 31 + content:byte(i)) & 0xFFFFFFFF
            end
            if hash ~= last_hash then
                last_hash = hash
                cached = load_palettes(PAL_FILE)
                local nw = cached and #cached.writes or 0
                local nf = 0
                if cached and cached.force then
                    for _ in pairs(cached.force) do nf = nf + 1 end
                end
                local nt = cached and cached.teleport and 1 or 0
                log(string.format("f%d: Loaded %d writes, %d forces, %d teleport", f, nw, nf, nt))
                -- If teleport, queue it for one-shot application this frame
                if cached and cached.teleport then
                    pending_teleport = cached.teleport
                    cached.teleport = nil  -- consume so we don't repeat
                end
            end
        end
    end

    -- Apply palette overrides EVERY frame
    if cached then apply_writes(cached.writes) end

    -- Apply force writes EVERY frame (e.g., FFBF=3 for boss preview)
    if cached and cached.force then
        for addr, val in pairs(cached.force) do
            emu:write8(addr, val)
        end
    end

    -- Apply teleport once (write state bytes, then clear).
    -- Note: this may not give a fully-functional arena since boss tile
    -- data isn't loaded — but it's enough to preview palettes in
    -- something resembling the arena state.
    if pending_teleport then
        for addr, val in pairs(pending_teleport) do
            emu:write8(addr, val)
        end
        log(string.format("f%d: Teleport applied", f))
        pending_teleport = nil
    end
end)
