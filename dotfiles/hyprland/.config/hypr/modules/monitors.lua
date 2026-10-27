hl.monitor({
    output   = "eDP-1",
    mode     = "preferred",
    position = "auto",
    scale    = "1",
})

hl.monitor({
    output   = "HDMI-A-1",
    mode     = "preferred",
    position = "auto",
    scale    = "1",
    mirror   = "eDP-1",
})

-- Temporary monitor rotation: Ctrl + Alt + Arrow keys
local monitor = "eDP-1" -- Replace with your monitor name

local function rotate(transform)
    hl.exec_cmd(
        'hyprctl eval \'hl.monitor({ output = "' ..
        monitor .. '", transform = ' .. transform .. ' })\''
    )
end

hl.bind("CTRL + ALT + UP",    function() rotate(0) end)
hl.bind("CTRL + ALT + DOWN",  function() rotate(2) end)
hl.bind("CTRL + ALT + LEFT",  function() rotate(1) end)
hl.bind("CTRL + ALT + RIGHT", function() rotate(3) end)