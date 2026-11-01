-- ==============================================================================
-- system.lua: System Environment, Permissions, and Autostart
-- ==============================================================================

---- ENVIRONMENT VARIABLES ----
hl.env("HYPRCURSOR_THEME", "Catppuccin Mocha Blue")
hl.env("HYPRCURSOR_SIZE", "24")
hl.env("XCURSOR_SIZE", "24")
hl.env("QT_QPA_PLATFORMTHEME", "qt6ct")

---- SECURITY PERMISSIONS ----
hl.permission({ binary = "/usr/bin/hyprpm", type = "plugin", mode = "allow" })

---- AUTOSTART SERVICES ----
hl.on("hyprland.start", function()
    hl.exec_cmd("sh -c 'ambxst >/dev/null 2>&1 &'")
    hl.exec_cmd("sh -c '/usr/lib/polkit-gnome/polkit-gnome-authentication-agent-1 >/dev/null 2>&1 &'")
end)

