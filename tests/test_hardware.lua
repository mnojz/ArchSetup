-- Run with: lua tests/test_hardware.lua
-- Exercise input ordering without a running compositor or shell commands.
local hardware_path = "dotfiles/hyprland/.config/hypr/modules/hardware.lua"
local original_popen = io.popen
local original_getenv = os.getenv
local passed = 0

local function equal(actual, expected, message)
    assert(actual == expected, (message or "unexpected value")
        .. ": expected " .. tostring(expected) .. ", got " .. tostring(actual))
end

local function fixture(shell_output)
    local f = {
        events = {}, commands = {}, windows = {}, devices = {}, timers = {}, lookups = 0,
        cursor = { x = 100, y = 100 },
        monitor = { name = "eDP-1", position = { x = 0, y = 0 } },
    }
    io.popen = function(command)
        f.lookups = f.lookups + 1
        assert(command:match("^timeout "), "shell discovery must be bounded")
        return {
            read = function() return shell_output or "Instance test-id:\n  Shell ID: ambxst\n" end,
            close = function() return true end,
        }
    end
    os.getenv = function(name)
        if name == "XDG_RUNTIME_DIR" then return nil end
        return original_getenv(name)
    end
    hl = {
        monitor = function() end,
        config = function() end,
        device = function(spec) table.insert(f.devices, spec) end,
        gesture = function() end,
        on = function(name, callback) f.events[name] = callback end,
        get_cursor_pos = function() return f.cursor end,
        get_monitor_at_cursor = function() return f.monitor end,
        exec_cmd = function(command) table.insert(f.commands, command) end,
        dispatch = function(window) table.insert(f.windows, window) end,
        dsp = { exec_cmd = function(command, rules) return { command = command, rules = rules } end },
        timer = function(callback)
            local timer = { callback = callback, enabled = true }
            function timer:set_enabled(enabled) self.enabled = enabled end
            table.insert(f.timers, timer)
            return timer
        end,
    }
    f.module = dofile(hardware_path)
    function f:tick()
        for _, timer in ipairs(self.timers) do
            if timer.enabled then timer.callback() end
        end
    end
    function f:release_key() self.events["input.keyboard.key"](30, 1, 0) end
    return f
end

local function test(name, fn)
    local ok, err = pcall(fn)
    io.popen = original_popen
    os.getenv = original_getenv
    if not ok then error(name .. ": " .. tostring(err)) end
    passed = passed + 1
end

test("mouse release first spawns exactly once", function()
    local f = fixture()
    f.module.dragStart()
    f.cursor = { x = 200, y = 180 }
    f.module.dragEnd()
    f:release_key()
    f.module.dragEnd()
    equal(#f.windows, 1)
    equal(f.windows[1].rules.size[1], 100)
    equal(f.windows[1].rules.size[2], 80)
    equal(f.timers[1].enabled, false)
end)

test("keyboard release cancels before mouse release", function()
    local f = fixture()
    f.module.dragStart()
    f.cursor = { x = 200, y = 200 }
    f:release_key()
    equal(f.timers[1].enabled, false)
    assert(f.commands[#f.commands]:match("dragOverlay stop$"))
    f.module.dragEnd()
    equal(#f.windows, 0)
end)

test("key press does not cancel", function()
    local f = fixture()
    f.module.dragStart()
    f.events["input.keyboard.key"](30, 1, 1)
    f.cursor = { x = 200, y = 200 }
    f.module.dragEnd()
    equal(#f.windows, 1)
end)

test("clicks and selections below 16 in either dimension are ignored", function()
    for _, size in ipairs({ {0, 0}, {15, 40}, {40, 15} }) do
        local f = fixture()
        f.module.dragStart()
        f.cursor = { x = 100 + size[1], y = 100 + size[2] }
        f.module.dragEnd()
        equal(#f.windows, 0)
        equal(f.timers[1].enabled, false)
    end
end)

test("exactly 16 by 16 is accepted", function()
    local f = fixture()
    f.module.dragStart()
    f.cursor = { x = 116, y = 116 }
    f.module.dragEnd()
    equal(#f.windows, 1)
    equal(f.windows[1].rules.size[1], 16)
    equal(f.windows[1].rules.size[2], 16)
end)

test("reverse drag uses the rectangle's top left corner", function()
    local f = fixture()
    f.module.dragStart()
    f.cursor = { x = 50, y = 60 }
    f.module.dragEnd()
    equal(f.windows[1].rules.move[1], 50)
    equal(f.windows[1].rules.move[2], 60)
    equal(f.windows[1].rules.size[1], 50)
    equal(f.windows[1].rules.size[2], 40)
end)

test("stationary cursor sends no update commands", function()
    local f = fixture()
    f.module.dragStart()
    f:tick()
    f:tick()
    equal(#f.commands, 1)
    f.cursor = { x = 120, y = 120 }
    f:tick()
    f:tick()
    equal(#f.commands, 2)
end)

test("missing Ambxst is discovered only once per drag", function()
    local f = fixture("")
    f.module.dragStart()
    for i = 1, 20 do
        f.cursor = { x = 100 + i, y = 100 + i }
        f:tick()
    end
    equal(f.lookups, 1)
    equal(#f.commands, 0)
    f.module.dragEnd()
    equal(#f.windows, 1, "terminal works without the overlay")
    f.module.dragStart()
    equal(f.lookups, 2)
    f.module.dragCancel()
end)

test("crossing monitors cancels before sending mismatched coordinates", function()
    local f = fixture()
    f.module.dragStart()
    f.monitor = { name = "DP-1", position = { x = 1920, y = 0 } }
    f.cursor = { x = 2000, y = 200 }
    f:tick()
    equal(#f.commands, 2) -- start and stop only
    equal(f.timers[1].enabled, false)
    f.monitor = { name = "eDP-1", position = { x = 0, y = 0 } }
    f.cursor = { x = 200, y = 200 }
    f.module.dragEnd()
    equal(#f.windows, 0, "returning to the original monitor does not revive the drag")
end)

test("mouse release on another monitor cancels without waiting for timer", function()
    local f = fixture()
    f.module.dragStart()
    f.monitor = { name = "DP-1", position = { x = 1920, y = 0 } }
    f.module.dragEnd()
    equal(#f.windows, 0)
end)

test("moving the original monitor cancels the drag", function()
    local f = fixture()
    f.module.dragStart()
    f.monitor.position.x = 50
    f:tick()
    f.module.dragEnd()
    equal(#f.windows, 0)
end)

test("monitor-relative coordinates work at nonzero desktop origins", function()
    local f = fixture()
    f.monitor.position = { x = -1920, y = 100 }
    f.cursor = { x = -1820, y = 200 }
    f.module.dragStart()
    f.cursor = { x = -1720, y = 280 }
    f.module.dragEnd()
    equal(f.windows[1].rules.move[1], 100)
    equal(f.windows[1].rules.move[2], 100)
    equal(f.windows[1].rules.size[1], 100)
end)

test("one timer is reused across drags", function()
    local f = fixture()
    for _ = 1, 3 do
        f.module.dragStart()
        f.module.dragCancel()
    end
    equal(#f.timers, 1)
    equal(f.timers[1].enabled, false)
end)

test("a new drag works after cancellation", function()
    local f = fixture()
    f.module.dragStart()
    f:release_key()
    f.module.dragStart()
    f.cursor = { x = 150, y = 150 }
    f.module.dragEnd()
    equal(#f.windows, 1)
end)

test("unload cleans up overlay and cancels pending spawn", function()
    local f = fixture()
    f.module.dragStart()
    f.events["config.unload"]()
    f.module.dragEnd()
    equal(#f.windows, 0)
    equal(f.timers[1].enabled, false)
    assert(f.commands[#f.commands]:match("dragOverlay stop$"))
end)

test("touchpad state starts in sync and toggles both ways", function()
    local f = fixture()
    equal(f.devices[1].enabled, true)
    f.module.touchpad_toggle()
    equal(f.devices[2].enabled, false)
    f.module.touchpad_toggle()
    equal(f.devices[3].enabled, true)
end)

test("shell instance ids are quoted", function()
    local f = fixture("Instance a'b:\n  Shell ID: ambxst\n")
    f.module.dragStart()
    assert(f.commands[1]:find([[-i 'a'"'"'b']], 1, true))
end)

print(string.format("%d hardware tests passed", passed))
