local M = {}

-- ==============================================================================
-- power.lua: Native Hyprland Auto Refresh Rate & Power Management Module
--
-- Features:
-- - Automatically switches display refresh rate based on power state (AC / Battery)
-- - 100% in-process: native hl.monitor calls, zero external background daemons
-- - Auto-detects internal laptop panel (eDP-*) and available refresh rates
-- - Dynamically tints speedometer SVG icons ({COLOR}) into RAM tmpfs
-- - Listens to compositor events (config.reloaded, monitor.added)
-- - Provides M.toggle() for keybindings (e.g. XF86Tools) with override support
-- ==============================================================================

-- Configuration
local COLOR_AC              = "#95bcfb"   -- Catppuccin Sky Blue (High Refresh Rate)
local COLOR_BAT             = "#fab387"   -- Catppuccin Peach (Battery Eco)
local NOTIFICATION_TIMEOUT  = 3500        -- Notification duration in ms
local CHECK_INTERVAL_MS     = 1000        -- Power state polling interval (ms)

-- State cache
local last_hardware_ac      = nil
local ac_online_path        = nil
local bat_status_path       = nil
local is_laptop             = false

--------------------------------------------------------------------------------
-- Helpers
--------------------------------------------------------------------------------

local function read_file(path)
    if not path then return nil end
    local f = io.open(path, "r")
    if not f then return nil end
    local content = f:read("*a")
    f:close()
    return content and content:match("^%s*(.-)%s*$")
end

-- Discover power supply sysfs paths dynamically
local function init_power_paths()
    local common_ac = {
        "/sys/class/power_supply/ADP1/online",
        "/sys/class/power_supply/AC/online",
        "/sys/class/power_supply/ACAD/online",
    }
    for _, p in ipairs(common_ac) do
        local f = io.open(p, "r")
        if f then f:close(); ac_online_path = p; break end
    end

    local common_bat = {
        "/sys/class/power_supply/BAT1/status",
        "/sys/class/power_supply/BAT0/status",
    }
    for _, p in ipairs(common_bat) do
        local f = io.open(p, "r")
        if f then f:close(); bat_status_path = p; is_laptop = true; break end
    end

    -- If not found in common names, scan /sys/class/power_supply
    if not ac_online_path or not bat_status_path then
        local p = io.popen("ls -1 /sys/class/power_supply 2>/dev/null")
        if p then
            for name in p:lines() do
                local type_val = read_file("/sys/class/power_supply/" .. name .. "/type")
                if type_val == "Mains" and not ac_online_path then
                    ac_online_path = "/sys/class/power_supply/" .. name .. "/online"
                elseif type_val == "Battery" and not bat_status_path then
                    bat_status_path = "/sys/class/power_supply/" .. name .. "/status"
                    is_laptop = true
                end
            end
            p:close()
        end
    end
end

-- Determine if AC mains is connected (true = AC, false = Battery)
local function is_ac_connected()
    if not is_laptop then
        return true -- Desktop PCs always considered on mains power
    end

    if ac_online_path then
        local mains = read_file(ac_online_path)
        if mains == "1" then return true end
        if mains == "0" then return false end
    end

    if bat_status_path then
        local status = read_file(bat_status_path)
        if status == "Discharging" then return false end
        if status == "Charging" or status == "Full" then return true end
    end

    return true
end

-- Auto-detect internal laptop display profile and available modes
local function get_display_profile()
    local monitors = hl.get_monitors()
    if not monitors or #monitors == 0 then
        return nil
    end

    -- Find internal eDP monitor, or fallback to first active monitor
    local mon = nil
    for _, m in ipairs(monitors) do
        if m.name:match("^eDP") then
            mon = m
            break
        end
    end
    if not mon then
        mon = monitors[1]
    end

    local high_mode = nil
    local low_mode = nil
    local max_rate = 0
    local min_rate = 999999

    for _, mode in ipairs(mon.available_modes) do
        local rate = mode.refresh_rate
        if rate > max_rate then
            max_rate = rate
            high_mode = mode.width .. "x" .. mode.height .. "@" .. math.floor(rate + 0.5)
        end
        if rate < min_rate and rate >= 50 then
            min_rate = rate
            low_mode = mode.width .. "x" .. mode.height .. "@" .. math.floor(rate + 0.5)
        end
    end

    local high_label = math.floor(max_rate + 0.5) .. "Hz"
    local low_label  = math.floor(min_rate + 0.5) .. "Hz"

    return {
        name        = mon.name,
        high_mode   = high_mode,
        low_mode    = low_mode,
        high_label  = high_label,
        low_label   = low_label,
        is_fixed    = (high_mode == low_mode),
    }
end

-- Render custom SVG icon with dynamic color into RAM tmpfs
local function prepare_icon(is_ac)
    local color = is_ac and COLOR_AC or COLOR_BAT
    local icon_file = is_ac and "speedometer-high.svg" or "speedometer-low.svg"
    local home = os.getenv("HOME") or "/home/manoj"
    local template_path = home .. "/.config/hypr/icons/" .. icon_file
    local runtime_dir = os.getenv("XDG_RUNTIME_DIR") or "/tmp"
    local out_path = runtime_dir .. "/refresh_rate_speedometer_" .. (is_ac and "high" or "low") .. ".svg"

    local f = io.open(template_path, "r")
    if f then
        local content = f:read("*a")
        f:close()
        if content then
            local colored = content:gsub("{COLOR}", color)
            local out_f = io.open(out_path, "w")
            if out_f then
                out_f:write(colored)
                out_f:close()
                return out_path
            end
        end
    end
    return "preferences-desktop-display-symbolic"
end

-- Send minimalist notification
local function send_notification(is_ac, label)
    local icon_path = prepare_icon(is_ac)
    hl.exec_cmd(string.format(
        "notify-send -a 'Display' -i '%s' -u low -t %d -h string:x-canonical-private-synchronous:refresh-rate 'Refresh Rate' '%s'",
        icon_path, NOTIFICATION_TIMEOUT, label
    ))
end

--------------------------------------------------------------------------------
-- Core Operations
--------------------------------------------------------------------------------

-- Apply refresh rate mode directly via native Hyprland API
local function apply_mode(is_ac, notify)
    local profile = get_display_profile()
    if not profile or profile.is_fixed then
        return
    end

    local target_mode  = is_ac and profile.high_mode or profile.low_mode
    local target_label = is_ac and profile.high_label or profile.low_label

    hl.monitor({
        output   = profile.name,
        mode     = target_mode,
        position = "auto",
        scale    = 1,
    })

    if notify then
        send_notification(is_ac, target_label)
    end
end

-- Polling tick (checks physical power supply changes in microseconds)
local function check_power()
    local hw_ac = is_ac_connected()
    if hw_ac ~= last_hardware_ac then
        last_hardware_ac = hw_ac
        apply_mode(hw_ac, true)
    end
end

-- Manual toggle function (can be invoked by keybinds)
function M.toggle()
    local profile = get_display_profile()
    if not profile or profile.is_fixed then return end

    local mon = hl.get_monitor(profile.name)
    local currently_high = mon and mon.refresh_rate >= 100 or false
    local target_is_ac = not currently_high

    apply_mode(target_is_ac, true)
end

--------------------------------------------------------------------------------
-- Initialization & Event Listeners
--------------------------------------------------------------------------------

init_power_paths()

if is_laptop then
    -- Background timer inside Hyprland's native event loop (epoll / timerfd)
    -- Reading 1 byte from sysfs once a second takes ~5 microseconds with zero overhead
    hl.timer(check_power, { timeout = CHECK_INTERVAL_MS, type = "repeat" })
end

-- Immediately apply initial refresh rate on Hyprland startup / module load
last_hardware_ac = is_ac_connected()
apply_mode(last_hardware_ac, false)

-- Re-apply on compositor reload
hl.on("config.reloaded", function()
    last_hardware_ac = is_ac_connected()
    apply_mode(last_hardware_ac, false)
end)

-- Re-apply on monitor hotplug/add
hl.on("monitor.added", function()
    last_hardware_ac = is_ac_connected()
    apply_mode(last_hardware_ac, false)
end)

return M
