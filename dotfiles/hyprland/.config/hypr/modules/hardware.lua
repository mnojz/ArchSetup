local M = {}

-- ==============================================================================
-- hardware.lua: Monitors, Inputs, Devices, Gestures, and Hardware Scripts
-- ==============================================================================

---- MONITORS ----
hl.monitor({
    output   = "eDP-1",
    mode     = "preferred",
    position = "auto",
    scale    = 1,
})

hl.monitor({
    output   = "HDMI-A-1",
    mode     = "preferred",
    position = "auto",
    scale    = 1,
    mirror   = "eDP-1",
})

-- Direct in-memory monitor rotation (no circular hyprctl eval)
function M.rotate(transform)
    hl.monitor({
        output    = "eDP-1",
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
local TOUCHPAD_NAME = "elan0307:00-04f3:3282-touchpad"
local COLOR_ACCENT = "#95bcfb"   -- Catppuccin Sky Blue / Desktop Accent
local touchpad_enabled = true

hl.device({
    name          = TOUCHPAD_NAME,
    accel_profile = "flat",
    sensitivity   = 0.5,
})

-- Render custom SVG icon with dynamic accent color into RAM tmpfs
local function prepare_touchpad_icon(enabled)
    local icon_file = enabled and "touchpad.svg" or "touchpad-disabled.svg"
    local home = os.getenv("HOME") or "/home/manoj"
    local template_path = home .. "/.config/hypr/icons/" .. icon_file
    local runtime_dir = os.getenv("XDG_RUNTIME_DIR") or "/tmp"
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
    return enabled and "input-touchpad-symbolic" or "touchpad-disabled-symbolic"
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
        "notify-send -a 'Device' -i '%s' -u low -t 2000 -h string:x-canonical-private-synchronous:touchpad 'Touchpad' '%s'",
        icon_path, status_text
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
local is_dragging = false
local drag_timer = nil
local cached_qs_id = nil

local function get_qs_id()
    if cached_qs_id then return cached_qs_id end
    local p = io.popen("qs list --all 2>/dev/null | awk '/^Instance / { id=$2; sub(/:$/, \"\", id) } /^  Shell ID: ambxst$/ { print id; exit }'")
    if p then
        local id = p:read("*l")
        p:close()
        if id and id ~= "" then
            cached_qs_id = id
            return id
        end
    end
    return nil
end

local function cursor_on_monitor()
    local cursor = hl.get_cursor_pos()
    local monitor = cursor and hl.get_monitor_at_cursor()
    if not cursor or not monitor then return nil end
    return cursor, monitor, cursor.x - monitor.position.x, cursor.y - monitor.position.y
end

local function overlay_ipc(action, args)
    local id = get_qs_id()
    if id then
        hl.exec_cmd("qs ipc -i \"" .. id .. "\" call dragOverlay " .. action .. (args or ""))
    end
end

local function update_drag_overlay()
    if not is_dragging then return end
    local _, _, x, y = cursor_on_monitor()
    if not x or not y then return end
    overlay_ipc("update", string.format(" %.0f %.0f", x, y))
end

function M.dragStart()
    local _, monitor, x, y = cursor_on_monitor()
    if not monitor or not x or not y then return end

    cached_qs_id = nil -- refresh ID on new drag start
    start_x = x
    start_y = y
    start_monitor = monitor.name
    is_dragging = true

    overlay_ipc("start", string.format(" %.0f %.0f", start_x, start_y))

    if drag_timer then
        drag_timer:set_enabled(false)
    end
    drag_timer = hl.timer(update_drag_overlay, { timeout = 16, type = "repeat" })
end

function M.dragEnd()
    if not is_dragging then return end
    is_dragging = false

    if drag_timer then
        drag_timer:set_enabled(false)
        drag_timer = nil
    end

    overlay_ipc("stop")

    local _, monitor, cursor_x, cursor_y = cursor_on_monitor()
    if not monitor or monitor.name ~= start_monitor then return end

    local x = math.min(start_x, cursor_x)
    local y = math.min(start_y, cursor_y)
    local w = math.max(1, math.abs(start_x - cursor_x))
    local h = math.max(1, math.abs(start_y - cursor_y))

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

-- End drag on any key release
hl.on("input.keyboard.key", function(_, _, state)
    if state ~= 0 or not is_dragging then return end
    M.dragEnd()
end)

return M

