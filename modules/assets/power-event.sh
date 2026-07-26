#!/bin/bash

export XDG_RUNTIME_DIR=/run/user/1000
export HYPRLAND_INSTANCE_SIGNATURE=$(ls /run/user/1000/hypr | head -n1)

if [ "$(cat /sys/class/power_supply/ADP1/online)" = "1" ]; then
    powerprofilesctl set performance
else
    powerprofilesctl set power-saver
fi

runuser -u manoj -- hyprctl reload
