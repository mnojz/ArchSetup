local M = {}

-- ==============================================================================
-- hardware.lua: Monitors, Inputs, Devices, Gestures, and Hardware Scripts
-- ==============================================================================

-- Personal hardware settings; keep connector/device names in one place.
local INTERNAL_DISPLAY = "eDP-1"
local EXTERNAL_DISPLAY = "HDMI-A-1"
local TOUCHPAD_NAME = "elan0307:00-04f3:3282-touchpad"
local MIN_DRAG_SIZE = 16

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
    if not is_dragging then return end
    is_dragging = false
    if drag_timer then drag_timer:set_enabled(false) end
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
    M.dragCancel()
    -- Ignore clicks and thin selections rather than launch unusable windows.
    if w < MIN_DRAG_SIZE or h < MIN_DRAG_SIZE then return end

    hl.dispatch(
        hl.dsp.exec_cmd(
            "kitty",
            {
                float = true,
                move  = { x, y },
                size  = { w, h },
            }
        )
    )
end

-- Releasing any keyboard key before the mouse cancels this drag.
hl.on("input.keyboard.key", function(_, _, state)
    if state == 0 then M.dragCancel() end
end)

-- Hide the external overlay when the Lua configuration is reloaded or exits.
hl.on("config.reloaded", M.dragCancel)
hl.on("hyprland.shutdown", M.dragCancel)

return M
