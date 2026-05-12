#!/usr/bin/env bash

section "Installing SDDM"

cd /tmp
git clone --depth 1 https://github.com/Darkkal44/qylock.git
cd qylock
chmod +x sddm.sh && ./sddm.sh