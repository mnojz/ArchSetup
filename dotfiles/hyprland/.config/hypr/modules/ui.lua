-- ==============================================================================
-- ui.lua: Look & Feel, Window Rules, Layer Rules, and Animations
-- ==============================================================================

---- LOOK AND FEEL ----
hl.config({
    general = {
        gaps_in          = 3,
        gaps_out         = 5,
        border_size      = 1,

        col              = {
            active_border   = "rgba(95BCFB55)",
            inactive_border = "rgba(FFFFFF20)",
        },

        resize_on_border = true,
        allow_tearing    = false,
        layout           = "dwindle",
    },

    decoration = {
        rounding         = 10,
        rounding_power   = 10,
        active_opacity   = 1.0,
        inactive_opacity = 1.0,

        shadow           = {
            enabled = false,
        },

        blur             = {
            enabled  = true,
            size     = 2,
            passes   = 2,
            vibrancy = 0.12,
        },

        wobble           = {
            enabled   = true,
            mesh      = 32,
            stiffness = 140,
            damping   = 10,
            mass      = 0.6,
            intensity = 0.9,
        },
    },

    dwindle = {
        preserve_split = true,
    },

    misc = {
        force_default_wallpaper      = 0,
        disable_hyprland_logo        = true,
        vrr                          = 1,
        animate_manual_resizes       = true,
        animate_mouse_windowdragging = true,
    },

    animations = {
        enabled = true,
    },
})

---- ANIMATION CURVES ----
hl.curve("easeOutQuint",   { type = "bezier", points = { { 0.23, 1 }, { 0.32, 1 } } })
hl.curve("easeInOutCubic", { type = "bezier", points = { { 0.65, 0.05 }, { 0.36, 1 } } })
hl.curve("easeInCubic",    { type = "bezier", points = { { 0.32, 0 }, { 0.67, 0 } } })
hl.curve("linear",         { type = "bezier", points = { { 0, 0 }, { 1, 1 } } })
hl.curve("almostLinear",   { type = "bezier", points = { { 0.5, 0.5 }, { 0.75, 1 } } })
hl.curve("quick",          { type = "bezier", points = { { 0.15, 0 }, { 0.1, 1 } } })
hl.curve("easy",           { type = "spring", mass = 1, stiffness = 71.2633, dampening = 15.8273644 })
hl.curve("snappySpring",   { type = "spring", mass = 1, stiffness = 160, dampening = 22 })

---- ANIMATIONS ----
hl.animation({ leaf = "global",         enabled = true,  speed = 4,    bezier = "easeOutQuint" })
hl.animation({ leaf = "border",         enabled = true,  speed = 5,    bezier = "linear" })
hl.animation({ leaf = "windows",        enabled = true,  speed = 4,    bezier = "easeOutQuint" })
-- Keep tiled layout changes and entering/leaving windows on the same curve.
hl.animation({ leaf = "windowsIn",      enabled = true,  speed = 4,    bezier = "easeOutQuint", style = "slide" })
hl.animation({ leaf = "windowsMove",    enabled = true,  speed = 4,    bezier = "easeOutQuint" })
hl.animation({ leaf = "windowsOut",     enabled = true,  speed = 4,    bezier = "easeOutQuint", style = "slide" })
hl.animation({ leaf = "fadeIn",         enabled = false, speed = 2,    bezier = "almostLinear" })
hl.animation({ leaf = "fadeOut",        enabled = false, speed = 2,    bezier = "almostLinear" })
hl.animation({ leaf = "fade",           enabled = true,  speed = 3.03, bezier = "quick" })
hl.animation({ leaf = "layers",         enabled = true,  speed = 3.81, bezier = "easeOutQuint" })
hl.animation({ leaf = "layersIn",       enabled = true,  speed = 4,    bezier = "easeOutQuint", style = "fade" })
hl.animation({ leaf = "layersOut",      enabled = true,  speed = 1.5,  bezier = "linear",       style = "fade" })
hl.animation({ leaf = "fadeLayersIn",   enabled = true,  speed = 1.79, bezier = "almostLinear" })
hl.animation({ leaf = "fadeLayersOut",  enabled = true,  speed = 1.39, bezier = "almostLinear" })
hl.animation({ leaf = "workspaces",     enabled = true,  speed = 3.5,  bezier = "easeOutQuint", style = "slidefade 20%" })
hl.animation({ leaf = "zoomFactor",     enabled = true,  speed = 7,    bezier = "quick" })

---- WINDOW RULES ----
-- Tiled neighbors should keep straight edges while the layout makes room.
-- Floating windows continue to use the global wobble effect.
hl.window_rule({
    name      = "no-wobble-for-tiled-windows",
    match     = { float = false },
    no_wobble = true,
})

hl.window_rule({
    name      = "wobble-for-floating-windows",
    match     = { float = true },
    no_wobble = false,
})

-- Suppress deformation only during the first frames of a selected terminal.
-- hardware.lua releases this override after the window has appeared.
hl.window_rule({
    name      = "drag-terminal-opening-wobble",
    match     = { class = "^archsetup-drag-terminal-.*$" },
    no_wobble = true,
})

hl.window_rule({
    name           = "suppress-maximize-events",
    match          = { class = ".*" },
    suppress_event = "maximize",
})

hl.window_rule({
    name     = "fix-xwayland-drags",
    match    = {
        class      = "^$",
        title      = "^$",
        xwayland   = true,
        float      = true,
        fullscreen = false,
        pin        = false,
    },
    no_focus = true,
})

hl.window_rule({
    name  = "move-hyprland-run",
    match = { class = "hyprland-run" },
    move  = "20 monitor_h-120",
    float = true,
})

hl.window_rule({
    name  = "gnome-calculator",
    match = { class = "org.gnome.Calculator" },
    move  = "monitor_w-450 80",
    float = true,
})

hl.window_rule({
    name   = "Amberol",
    match  = { class = "io.bassi.Amberol" },
    center = true,
    size   = "360 660",
    float  = true,
})

hl.window_rule({
    name   = "portal file dialogs",
    match  = { class = "^xdg-desktop-portal-.*$" },
    center = true,
    size   = "800 550",
    float  = true,
})

hl.window_rule({
    name   = "kdenlive splash screen",
    match  = { class = "org.kde.kdenlive", title = "^Kdenlive$" },
    center = true,
    float  = true,
})

hl.window_rule({
    name   = "app manager",
    match  = { class = "com.github.AppManager" },
    center = true,
    float  = true,
})

hl.window_rule({
    name   = "kdeconnect",
    match  = { class = "org.kde.kdeconnect.app" },
    center = true,
    float  = true,
    size   = "600 460",
})

hl.window_rule({
    name   = "cine",
    match  = { class = "io.github.diegopvlk.Cine" },
    center = true,
    float  = true,
})

hl.window_rule({
    name   = "satty",
    match  = { class = "com.gabm.satty" },
    center = true,
    float  = true,
    size   = "700 600",
})

hl.window_rule({
    name   = "shelly",
    match  = { class = "com.shellyorg.shelly" },
    center = true,
    float  = true,
    size   = "1060 710",
})

hl.window_rule({
    name   = "dolphin-dialogs",
    match  = {
        class = "org.kde.dolphin",
        title = "^(Progress Dialog|Copying.*|Moving.*|Properties for.*|Configure.*)$",
    },
    center = true,
    float  = true,
})

-- Keep the floating-only policy when an existing window is tiled or floated.
-- Remember state before setting a property: that update can emit rules again.
local window_floating_states = {}
local function update_window_wobble(window, opening)
    local address, floating = window.address, window.floating
    if window_floating_states[address] == floating then return end
    window_floating_states[address] = floating
    if opening and window.initial_class:sub(1, #"archsetup-drag-terminal-") == "archsetup-drag-terminal-" then
        return -- hardware.lua releases this window's opening override.
    end
    hl.dispatch(hl.dsp.window.set_prop({
        window = window, prop = "no_wobble", value = floating and "0" or "1",
    }))
end

hl.on("window.open", function(window) update_window_wobble(window, true) end)
hl.on("window.update_rules", function(window)
    if window_floating_states[window.address] ~= nil then update_window_wobble(window, false) end
end)
hl.on("window.close", function(window) window_floating_states[window.address] = nil end)
hl.on("config.reloaded", function()
    for _, window in ipairs(hl.get_windows()) do update_window_wobble(window, false) end
end)

---- LAYER RULES ----
hl.layer_rule({
    match        = { namespace = "quickshell" },
    no_anim      = true,
    blur         = true,
    blur_popups  = true,
    ignore_alpha = 1.00,
})

hl.layer_rule({
    match   = { namespace = "selection" },
    no_anim = true,
})

hl.layer_rule({
    match        = { namespace = "fabric" },
    blur         = true,
    ignore_alpha = 0.40,
})

hl.layer_rule({
    match        = { namespace = "^ambxst(:.*)?$" },
    no_anim      = true,
    blur         = true,
    blur_popups  = true,
    ignore_alpha = 0.20,
})

