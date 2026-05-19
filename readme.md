## things to do manually. 

1. Plymouth setting up


## some extra optional packages.

1. blender
2. kdenlive
3. freecad
4. gnome-system-monitor
5. gnome-font-viewer
6. gnome-software

### plymouth setting up

1. edit ```/boot/loader/entries/arch.conf``` file
2. look for this line ```options root=UUID=0a3407de-014b-458b-b5c1-848e92a327a3 rw quiet splash```
3. add ```quiet``` and ```splash``` as shown in above line. 
4. now configure ```initramfs```
5. open ```/etc/mkinitcpio.conf``` on text editor
6. look for a line starting with ```hooks=(...)```
7. add plymouth in the hooks array, order matters so try to add it after ```systemd``` if available, possibly in 3rd position
8. after initramfs is configured regenerate it again ```sudo mkinitcpio -P```