-- Trace CPU writes to the game's primary shadow OAM buffer (C000-C09F).
-- Put an mGBA .ss0/.ss1 path in /tmp/state_path.txt before launching.

local statePath
do
    local f = io.open("/tmp/state_path.txt", "r")
    if f then statePath = f:read("*l"); f:close() end
end

local log = assert(io.open("/tmp/shadow_oam_write_trace.log", "w"))
local frame = 0
local writes = 0
local seen = {}

local function emit(s)
    log:write(s .. "\n")
    log:flush()
end

local function onWrite(addr, value)
    local pc = emu:getRegister("PC")
    local bank = (pc < 0x4000) and 0 or emu:read8(0xFF99)
    local key = string.format("%02X:%04X", bank, pc)
    writes = writes + 1
    if not seen[key] then
        seen[key] = true
        emit(string.format(
            "first frame=%d bank=%02X pc=%04X addr=%04X value=%02X",
            frame, bank, pc, addr, value))
    end
end

-- Some mGBA builds only accept a single address for each callback.
for addr = 0xC000, 0xC09F do
    emu:addMemoryCallback(onWrite, emu.memoryCallback.WRITE, addr, addr)
end

callbacks:add("frame", function()
    frame = frame + 1
    if frame == 5 then
        if not statePath then
            emit("ERROR: /tmp/state_path.txt is missing or empty")
            emu:stop()
            return
        end
        local ok, result = pcall(function() return emu:loadStateFile(statePath) end)
        emit(string.format("load path=%s ok=%s result=%s", statePath, tostring(ok), tostring(result)))
    elseif frame == 125 then
        local unique = 0
        for _ in pairs(seen) do unique = unique + 1 end
        emit(string.format("summary frames=%d writes=%d unique_pcs=%d", frame, writes, unique))
        emu:stop()
    end
end)

callbacks:add("shutdown", function()
    emit(string.format("shutdown frame=%d writes=%d", frame, writes))
    log:close()
end)

emit("trace registered for C000-C09F")
