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
        cursor_invisible = false, cursor_changes = {}, mapped = {}, property_changes = {},
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
        config = function(config)
            if config.cursor and config.cursor.invisible ~= nil then
                f.cursor_invisible = config.cursor.invisible
                table.insert(f.cursor_changes, f.cursor_invisible)
            end
        end,
        get_config = function(key)
            equal(key, "cursor.invisible")
            return f.cursor_invisible
        end,
        device = function(spec) table.insert(f.devices, spec) end,
        gesture = function() end,
        on = function(name, callback)
            local previous = f.events[name]
            f.events[name] = previous and function(...) previous(...); callback(...) end or callback
        end,
        get_cursor_pos = function() return f.cursor end,
        get_monitor_at_cursor = function() return f.monitor end,
        exec_cmd = function(command) table.insert(f.commands, command) end,
        get_window = function(selector) return f.mapped[selector:sub(9)] end,
        dispatch = function(action)
            if action.command then table.insert(f.windows, action)
            else table.insert(f.property_changes, action) end
            return { ok = true }
        end,
        dsp = {
            exec_cmd = function(command, rules) return { command = command, rules = rules } end,
            window = {
                set_prop = function(spec) return spec end,
                tag = function(spec) return spec end,
            },
        },
        timer = function(callback, opts)
            local timer = { callback = callback, enabled = true, opts = opts }
            function timer:set_enabled(enabled) self.enabled = enabled end
            table.insert(f.timers, timer)
            return timer
        end,
    }
    f.module = dofile(hardware_path)
    function f:tick()
        for _, timer in ipairs(self.timers) do
            if timer.enabled and timer.opts.type == "repeat" then timer.callback() end
        end
    end
    function f:fire_timeout(timeout)
        for _, timer in ipairs(self.timers) do
            if timer.enabled and timer.opts.type == "oneshot" and timer.opts.timeout == timeout then
                timer.enabled = false
                timer.callback()
            end
        end
    end
    function f:map_window(class)
        local window = {
            initial_class = class or self.windows[#self.windows].command:match("%-%-class (%S+)"),
            address = "0x1234", floating = true,
        }
        self.mapped[window.address] = window
        self.events["window.open"](window)
        return window
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

test("reload cleans up overlay and cancels pending spawn", function()
    local f = fixture()
    f.module.dragStart()
    f.events["config.reloaded"]()
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

-- Load the real binding declarations too: direct calls to dragEnd alone cannot
-- catch a release shortcut that Hyprland suppresses after a consumed press.
test("mouse release binding survives press binding shadowing", function()
    local f = fixture()
    local press, release
    hl.bind = function(keys, callback, opts)
        if keys ~= "SUPER + ALT + mouse:272" then return end
        if opts and opts.release then
            release = { callback = callback, options = opts }
        else
            press = callback
        end
    end
    local noop
    noop = setmetatable({}, {
        __index = function() return noop end,
        __call = function() return {} end,
    })
    setmetatable(hl.dsp, { __index = function() return noop end })
    setmetatable(hl.dsp.window, { __index = function() return noop end })
    local old_hardware = package.loaded["modules.hardware"]
    local old_power = package.loaded["modules.power"]
    package.loaded["modules.hardware"] = f.module
    package.loaded["modules.power"] = { toggle = function() end }
    local ok, err = pcall(dofile, "dotfiles/hyprland/.config/hypr/modules/keybinds.lua")
    package.loaded["modules.hardware"] = old_hardware
    package.loaded["modules.power"] = old_power
    assert(ok, err)
    assert(press and release, "both mouse press and release must be bound")
    equal(release.options.transparent, true,
        "release must bypass Hyprland's shadowing after a consumed mouse press")
    press()
    f.cursor = { x = 200, y = 200 }
    release.callback()
    equal(#f.windows, 1)
    press()
    f:release_key()
    release.callback()
    equal(#f.windows, 1, "keyboard-first release must still cancel")
end)

test("native pointer is restored on every selection exit", function()
    local finishers = {
        function(f) f.module.dragEnd(); f:map_window() end,
        function(f) f:release_key() end,
        function(f)
            f.monitor = { name = "DP-1", position = { x = 1920, y = 0 } }
            f:tick()
        end,
        function(f) f.events["config.reloaded"]() end,
        function(f) f.events["hyprland.shutdown"]() end,
        function(f)
            f.cursor = { x = 100, y = 100 }
            f.module.dragEnd()
        end,
    }
    for _, finish in ipairs(finishers) do
        local f = fixture()
        f.module.dragStart()
        equal(f.cursor_invisible, true, "native cursor hidden while overlay draws crosshair")
        f.cursor = { x = 200, y = 200 }
        finish(f)
        equal(f.cursor_invisible, false, "native cursor restored on exit")
        equal(#f.cursor_changes, 2)
    end
end)

test("missing overlay never hides native pointer", function()
    local f = fixture("")
    f.module.dragStart()
    equal(f.cursor_invisible, false)
    f.module.dragCancel()
    equal(#f.cursor_changes, 0)
end)

test("selection preserves an already hidden native pointer", function()
    local f = fixture()
    f.cursor_invisible = true
    f.module.dragStart()
    f.module.dragCancel()
    equal(f.cursor_invisible, true)
end)

test("overlay hands off only when the selected terminal maps", function()
    local f = fixture()
    f.module.dragStart()
    f.cursor = { x = 300, y = 250 }
    f.module.dragEnd()
    equal(f.windows[1].rules.no_anim, true)
    equal(f.windows[1].rules.no_wobble, nil, "wobble follows dynamic window rules")
    equal(#f.commands, 2, "keep the rectangle visible while Kitty starts")
    assert(f.commands[2]:match("dragOverlay update 300 250$"), "final rectangle must match release coordinates")
    f:release_key()
    equal(#f.commands, 2, "keyboard release after the mouse must not interrupt handoff")
    f:map_window("kitty")
    equal(#f.commands, 2, "an unrelated terminal must not stop the overlay")
    f:map_window()
    assert(f.commands[#f.commands]:match("dragOverlay stop$"))
    equal(f.cursor_invisible, false)
    equal(#f.property_changes, 0, "keep the animation override through initial frames")
    f:fire_timeout(100)
    equal(f.property_changes[1].prop, "no_anim")
    equal(f.property_changes[1].value, "0")
    equal(f.property_changes[2].prop, "no_wobble")
    equal(f.property_changes[2].value, "0")
end)

test("failed or delayed terminal startup releases the overlay", function()
    local f = fixture()
    f.module.dragStart()
    f.cursor = { x = 300, y = 250 }
    f.module.dragEnd()
    f:fire_timeout(3000)
    assert(f.commands[#f.commands]:match("dragOverlay stop$"))
    equal(f.cursor_invisible, false)
    equal(#f.windows, 1)
end)

test("closed windows are ignored by opening-property cleanup", function()
    local f = fixture()
    f.module.dragStart()
    f.cursor = { x = 300, y = 250 }
    f.module.dragEnd()
    local window = f:map_window()
    f.mapped[window.address] = nil
    f:fire_timeout(100)
    equal(#f.property_changes, 0)
end)

test("new selection does not hand off to an older pending terminal", function()
    local f = fixture()
    f.module.dragStart()
    f.cursor = { x = 300, y = 250 }
    f.module.dragEnd()
    local old_class = f.windows[1].command:match("%-%-class (%S+)")
    f.module.dragStart()
    f.cursor = { x = 500, y = 450 }
    f.module.dragEnd()
    local commands_before = #f.commands
    f:map_window(old_class)
    equal(#f.commands, commands_before)
    f:map_window()
    equal(#f.commands, commands_before + 1)
end)

test("desktop windows keep normal animation rules", function()
    local f = fixture()
    local animations, rules = {}, {}
    hl.curve = function() end
    hl.animation = function(spec) animations[spec.leaf] = spec end
    hl.window_rule = function(spec) rules[#rules + 1] = spec end
    hl.layer_rule = function() end
    dofile("dotfiles/hyprland/.config/hypr/modules/ui.lua")
    for _, leaf in ipairs({ "windowsIn", "windowsOut", "windowsMove" }) do
        equal(animations[leaf].enabled, true)
    end
    equal(animations.fadeIn.enabled, false)
    equal(animations.fadeOut.enabled, false)
    equal(animations.windowsIn.style, "slide")
    equal(animations.windowsOut.style, "slide")
    equal(animations.windowsIn.speed, animations.windowsMove.speed)
    equal(animations.windowsOut.speed, animations.windowsMove.speed)
    equal(animations.windowsIn.bezier, animations.windowsMove.bezier)
    equal(animations.windowsOut.bezier, animations.windowsMove.bezier)
    local tiled_wobble_rule, opening_wobble_rule, floating_wobble_rule
    for _, rule in ipairs(rules) do
        assert(not rule.no_anim, "ordinary windows must not be opted out of animation")
        if rule.name == "no-wobble-for-tiled-windows" then tiled_wobble_rule = rule end
        if rule.name == "drag-terminal-opening-wobble" then opening_wobble_rule = rule end
        if rule.name == "wobble-for-floating-windows" then floating_wobble_rule = rule end
    end
    assert(tiled_wobble_rule)
    equal(tiled_wobble_rule.match.float, false)
    equal(tiled_wobble_rule.no_wobble, true)
    assert(opening_wobble_rule)
    assert(floating_wobble_rule)
    equal(floating_wobble_rule.match.float, true)
    equal(floating_wobble_rule.no_wobble, false)
    equal(opening_wobble_rule.no_wobble, true)
end)

test("wobble follows existing windows between tiled and floating states", function()
    local f = fixture()
    hl.curve = function() end
    hl.animation = function() end
    hl.window_rule = function() end
    hl.layer_rule = function() end
    hl.get_windows = function() return {} end
    dofile("dotfiles/hyprland/.config/hypr/modules/ui.lua")
    local window = { initial_class = "kitty", address = "0x5678", floating = false }
    f.events["window.open"](window)
    equal(f.property_changes[#f.property_changes].value, "1")
    window.floating = true
    f.events["window.update_rules"](window)
    equal(f.property_changes[#f.property_changes].value, "0")
    local count = #f.property_changes
    f.events["window.update_rules"](window)
    equal(#f.property_changes, count, "property updates must not recurse")
    window.floating = false
    f.events["window.update_rules"](window)
    equal(f.property_changes[#f.property_changes].value, "1")
end)

print(string.format("%d hardware tests passed", passed))
