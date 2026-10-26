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

        -- Change transparency of focused and unfocused windows
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
    },

    animations = {
        enabled = true,
    },
})

hl.curve("easeOutQuint", { type = "bezier", points = { { 0.23, 1 }, { 0.32, 1 } } })
hl.curve("easeInOutCubic", { type = "bezier", points = { { 0.65, 0.05 }, { 0.36, 1 } } })
hl.curve("easeInCubic", { type = "bezier", points = { { 0.32, 0 }, { 0.67, 0 } } })
hl.curve("linear", { type = "bezier", points = { { 0, 0 }, { 1, 1 } } })
hl.curve("almostLinear", { type = "bezier", points = { { 0.5, 0.5 }, { 0.75, 1 } } })
hl.curve("quick", { type = "bezier", points = { { 0.15, 0 }, { 0.1, 1 } } })

hl.curve("easy", { type = "spring", mass = 1, stiffness = 71.2633, dampening = 15.8273644 })
hl.curve("snappySpring", { type = "spring", mass = 1, stiffness = 160, dampening = 22 })

hl.animation({ leaf = "global", enabled = true, speed = 10, bezier = "default" })
hl.animation({ leaf = "border", enabled = true, speed = 5.39, bezier = "easeOutQuint" })
hl.animation({ leaf = "windows", enabled = false, speed = 1, bezier = "linear" })
hl.animation({ leaf = "windowsIn", enabled = false, speed = 1, bezier = "linear" })
hl.animation({ leaf = "windowsMove", enabled = false, speed = 1, bezier = "linear" })
hl.animation({ leaf = "windowsOut", enabled = false, speed = 1, bezier = "linear" })
hl.animation({ leaf = "fadeIn", enabled = false, speed = 1, bezier = "almostLinear" })
hl.animation({ leaf = "fadeOut", enabled = false, speed = 1, bezier = "almostLinear" })
hl.animation({ leaf = "fade", enabled = true, speed = 3.03, bezier = "quick" })
hl.animation({ leaf = "layers", enabled = true, speed = 3.81, bezier = "easeOutQuint" })
hl.animation({ leaf = "layersIn", enabled = true, speed = 4, bezier = "easeOutQuint", style = "fade" })
hl.animation({ leaf = "layersOut", enabled = true, speed = 1.5, bezier = "linear", style = "fade" })
hl.animation({ leaf = "fadeLayersIn", enabled = true, speed = 1.79, bezier = "almostLinear" })
hl.animation({ leaf = "fadeLayersOut", enabled = true, speed = 1.39, bezier = "almostLinear" })
hl.animation({ leaf = "workspaces", enabled = true, speed = 3.5, bezier = "easeOutQuint", style = "slidefade 20%" })
hl.animation({ leaf = "zoomFactor", enabled = true, speed = 7, bezier = "quick" })

hl.config({
    dwindle = {
        preserve_split = true, -- You probably want this
    }
})

hl.config({
    misc = {
        force_default_wallpaper = 0,
        disable_hyprland_logo   = true,
        vrr                     = 1
    },
})
