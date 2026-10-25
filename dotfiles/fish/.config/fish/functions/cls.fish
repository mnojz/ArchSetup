function cls --description 'Clear screen and scrollback'
    clear
    printf '\e[3J'
end
