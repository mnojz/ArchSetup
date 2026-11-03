local M = {}

-- ==============================================================================
-- hardware.lua: Monitors, Inputs, Devices, Gestures, and Hardware Scripts
-- ==============================================================================

-- Personal hardware settings; keep connector/device names in one place.
local INTERNAL_DISPLAY = "eDP-1"
local EXTERNAL_DISPLAY = "HDMI-A-1"
local TOUCHPAD_NAME = "elan0307:00-04f3:3282-touchpad"
local MIN_DRAG_SIZE = 16
local DRAG_TERMINAL_PREFIX = "archsetup-drag-terminal-"

---- MONITORS ----
hl.monitor({
    output   = INTERNAL_DISPLAY,
    mode     = "preferred",
    position = "auto",
    scale    = 1,
})

hl.monitor({
    output   = EXTERNAL_DISPLAY,
    mode     = "preferred",
    position = "auto",
    scale    = 1,
    mirror   = INTERNAL_DISPLAY,
})

-- Direct in-memory monitor rotation (no circular hyprctl eval)
function M.rotate(transform)
    hl.monitor({
        output    = INTERNAL_DISPLAY,
        transform = transform,
    })
end

---- INPUT CONFIGURATION ----
hl.config({
    input = {
        kb_layout          = "us",
        follow_mouse       = 1,
        sensitivity        = 0,
        accel_profile      = "flat",
        numlock_by_default = true,

        touchpad = {
            natural_scroll       = true,
            scroll_factor        = 0.5,
            disable_while_typing = true,
        },
    },
})

-- Touchpad device configuration
local COLOR_ACCENT = "#95bcfb"   -- Catppuccin Sky Blue / Desktop Accent
-- Reloading the config explicitly enables the device and resets this state.
local touchpad_enabled = true

hl.device({
    name          = TOUCHPAD_NAME,
    enabled       = touchpad_enabled,
    accel_profile = "flat",
    sensitivity   = 0.5,
})

local function shell_quote(value)
    return "'" .. value:gsub("'", [['"'"']]) .. "'"
end

-- Render custom SVG icon with dynamic accent color into RAM tmpfs
local function prepare_touchpad_icon(enabled)
    local icon_file = enabled and "touchpad.svg" or "touchpad-disabled.svg"
    local fallback = enabled and "input-touchpad-symbolic" or "touchpad-disabled-symbolic"
    local home = os.getenv("HOME")
    local config_dir = os.getenv("XDG_CONFIG_HOME") or (home and home .. "/.config")
    local runtime_dir = os.getenv("XDG_RUNTIME_DIR")
    -- Use themed icons when no private runtime directory is available.
    if not config_dir or not runtime_dir or runtime_dir == "" then return fallback end
    local template_path = config_dir .. "/hypr/icons/" .. icon_file
    local out_path = runtime_dir .. "/touchpad_" .. (enabled and "enabled" or "disabled") .. ".svg"

    local f = io.open(template_path, "r")
    if f then
        local content = f:read("*a")
        f:close()
        if content then
            local colored = content:gsub("{COLOR}", COLOR_ACCENT)
            local out_f = io.open(out_path, "w")
            if out_f then
                out_f:write(colored)
                out_f:close()
                return out_path
            end
        end
    end
    return fallback
end

-- Touchpad toggle function
function M.touchpad_toggle()
    touchpad_enabled = not touchpad_enabled
    hl.device({
        name    = TOUCHPAD_NAME,
        enabled = touchpad_enabled,
    })
    local status_text = touchpad_enabled and "enabled" or "disabled"
    local icon_path = prepare_touchpad_icon(touchpad_enabled)
    hl.exec_cmd(string.format(
        "notify-send -a 'Device' -i %s -u low -t 2000 -h string:x-canonical-private-synchronous:touchpad 'Touchpad' '%s'",
        shell_quote(icon_path), status_text
    ))
end

---- GESTURES ----
local function ctrlTab()
    hl.exec_cmd("wtype -M ctrl -k tab -m ctrl")
end

local function ctrlShiftTab()
    hl.exec_cmd("wtype -M ctrl -M shift -k tab -m shift -m ctrl")
end

hl.gesture({ fingers = 3, direction = "down",       action = ctrlTab })
hl.gesture({ fingers = 3, direction = "up",         action = ctrlShiftTab })
hl.gesture({ fingers = 3, direction = "horizontal", action = "workspace" })

---- SELECTION DRAG TO SPAWN TERMINAL ----
local start_x = 0
local start_y = 0
local start_monitor = nil
local start_origin_x = 0
local start_origin_y = 0
local is_dragging = false
local drag_timer = nil
local cached_qs_id = nil
local last_overlay_x = nil
local last_overlay_y = nil
local cursor_visibility_before_drag = nil
local pending_terminal = nil
local spawn_timeout = nil
local launch_number = 0

local function hide_native_cursor()
    -- The overlay draws the crosshair because an application can retain cursor
    -- ownership during a held-button drag (for example an editor's I-beam).
    -- Leave the pointer alone when there is no overlay to draw its replacement.
    if not cached_qs_id then return end
    local invisible, err = hl.get_config("cursor.invisible")
    if err or type(invisible) ~= "boolean" then return end
    cursor_visibility_before_drag = invisible
    hl.config({ cursor = { invisible = true } })
end

local function restore_native_cursor()
    if cursor_visibility_before_drag == nil then return end
    hl.config({ cursor = { invisible = cursor_visibility_before_drag } })
    cursor_visibility_before_drag = nil
end

-- Discover at most once per drag, including when Ambxst is unavailable.
-- Bound this external lookup so an unresponsive qs cannot hang the compositor.
local function get_qs_id()
    local p = io.popen("timeout 0.2s qs list --all 2>/dev/null")
    if not p then return nil end
    local output = p:read("*a")
    p:close()
    local id = nil
    for line in (output or ""):gmatch("[^\r\n]+") do
        if line:match("^Instance ") then
            id = line:match("^Instance ([^:]+):")
        elseif line:match("^%s+Shell ID: ambxst%s*$") then
            return id
        end
    end
    return nil
end

local function cursor_on_monitor()
    local cursor = hl.get_cursor_pos()
    local monitor = cursor and hl.get_monitor_at_cursor()
    if not cursor or not monitor then return nil end
    -- Use logical desktop coordinates consistently, including on scaled monitors.
    return cursor, monitor,
        math.floor(cursor.x - monitor.position.x + 0.5),
        math.floor(cursor.y - monitor.position.y + 0.5)
end

local function overlay_ipc(action, args)
    if cached_qs_id then
        hl.exec_cmd("qs ipc -i " .. shell_quote(cached_qs_id) .. " call dragOverlay " .. action .. (args or ""))
    end
end

local function on_start_monitor(monitor)
    return monitor and monitor.name == start_monitor
        and monitor.position.x == start_origin_x
        and monitor.position.y == start_origin_y
end

-- Cancellation never creates a terminal, even if the mouse is released later.
function M.dragCancel()
    if not is_dragging and not pending_terminal then return end
    is_dragging = false
    pending_terminal = nil
    if drag_timer then drag_timer:set_enabled(false) end
    if spawn_timeout then
        spawn_timeout:set_enabled(false)
        spawn_timeout = nil
    end
    restore_native_cursor()
    overlay_ipc("stop")
    cached_qs_id = nil
    start_monitor = nil
    last_overlay_x = nil
    last_overlay_y = nil
end

local function update_drag_overlay()
    if not is_dragging then return end
    local _, monitor, x, y = cursor_on_monitor()
    -- Cancel before sending coordinates from a different monitor or layout.
    if not on_start_monitor(monitor) then
        M.dragCancel()
        return
    end
    if not cached_qs_id or (x == last_overlay_x and y == last_overlay_y) then return end
    last_overlay_x, last_overlay_y = x, y
    overlay_ipc("update", string.format(" %d %d", x, y))
end

function M.dragStart()
    M.dragCancel()
    local _, monitor, x, y = cursor_on_monitor()
    if not monitor or x == nil or y == nil then return end

    start_x, start_y = x, y
    start_monitor = monitor.name
    start_origin_x, start_origin_y = monitor.position.x, monitor.position.y
    is_dragging = true
    cached_qs_id = get_qs_id()
    last_overlay_x, last_overlay_y = x, y
    overlay_ipc("start", string.format(" %d %d", x, y))
    hide_native_cursor()

    -- Reuse one timer; it also watches monitor boundaries without an overlay.
    if drag_timer then
        drag_timer:set_enabled(true)
    else
        drag_timer = hl.timer(update_drag_overlay, { timeout = 16, type = "repeat" })
    end
end

-- Called only by the mouse-release binding in keybinds.lua.
function M.dragEnd()
    if not is_dragging then return end
    local _, monitor, cursor_x, cursor_y = cursor_on_monitor()
    if not on_start_monitor(monitor) then
        M.dragCancel()
        return
    end

    local x = math.min(start_x, cursor_x)
    local y = math.min(start_y, cursor_y)
    local w = math.abs(start_x - cursor_x)
    local h = math.abs(start_y - cursor_y)
    -- Ignore clicks and thin selections rather than launch unusable windows.
    if w < MIN_DRAG_SIZE or h < MIN_DRAG_SIZE then
        M.dragCancel()
        return
    end

    -- Use the release position for both the final rectangle and the window;
    -- the last timer update can be one frame behind a fast mouse movement.
    overlay_ipc("update", string.format(" %d %d", cursor_x, cursor_y))

    -- Finish selection, but keep the rectangle until the replacement window
    -- maps. Keyboard releases after the mouse no longer cancel this handoff.
    is_dragging = false
    if drag_timer then drag_timer:set_enabled(false) end
    launch_number = launch_number + 1
    local terminal_class = DRAG_TERMINAL_PREFIX .. os.time() .. "-" .. launch_number
    pending_terminal = terminal_class
    spawn_timeout = hl.timer(function()
        if pending_terminal == terminal_class then M.dragCancel() end
    end, { timeout = 3000, type = "oneshot" })

    local result = hl.dispatch(
        hl.dsp.exec_cmd(
            "kitty --class " .. terminal_class,
            {
                float = true,
                move  = { x, y },
                size  = { w, h },
                no_anim   = true,
            }
        )
    )
    if result and result.ok == false then
        M.dragCancel()
        error(result.error or "Could not launch drag-selected terminal")
    end
end

hl.on("window.open", function(window)
    if window.initial_class:sub(1, #DRAG_TERMINAL_PREFIX) ~= DRAG_TERMINAL_PREFIX then return end
    if window.initial_class == pending_terminal then M.dragCancel() end

    -- Let the first frame render at full opacity and final geometry before
    -- returning this terminal to the desktop's normal animation rules.
    local address = window.address
    hl.timer(function()
        local current = hl.get_window("address:" .. address)
        if current then
            hl.dispatch(hl.dsp.window.set_prop({ window = current, prop = "no_anim", value = "0" }))
            hl.dispatch(hl.dsp.window.set_prop({
                window = current, prop = "no_wobble", value = current.floating and "0" or "1",
            }))
        end
    end, { timeout = 100, type = "oneshot" })
end)

-- Releasing any keyboard key before the mouse cancels this drag.
hl.on("input.keyboard.key", function(_, _, state)
    if state == 0 and is_dragging then M.dragCancel() end
end)

-- Hide the external overlay when the Lua configuration is reloaded or exits.
hl.on("config.reloaded", M.dragCancel)
hl.on("hyprland.shutdown", M.dragCancel)

return M
