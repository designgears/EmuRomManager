This project was inspired by my 9yr old son who constantly wants to try different games and I got annoyed with the manual process so I made this so I can dump files on a local server, and he can click a couple of buttons and be up and running (mostly) without my help. 

It's messy, one day I will clean it up, but for now it gets the job done. :shipit:

> [!Note]
> This is used in conjuction with (none of this is require, just my use case) EmuDeck and Playnite (w/the EmuDeck addon). The resulting XCI is copied to the switch roms directory, then scanned on startup by Playnite and ready to play in most cases. Some games need settings tweaks in the emulator or mods to work correctly, that isn't covered here.

> [!IMPORTANT]
> Directory structure doesn't matter, base/update/dlc are determined from the titleid. I don't want to process the file to get the information, with a large collection, over the network, that gets very slow. (very specific to my use case)  

> [!WARNING]
> Filename matters, at a minimum you need `[<16 digit titleid>][<version>].(nsp|nsz|xci)`, the order of the version and titleid doesn't matter.

### Example Filenames: 
```
/switch_roms/base/MONSTER HUNTER RISE[0100B04011742000][US][v0].nsz
/switch_roms/update/Monster Hunter Rise[0100B04011742800][US][v2162688].nsz
/switch_roms/dlc/Floral Sleeves Hunter layered armor piece[0100B04011743065][US][v0].nsz
/switch_roms/dlc/MONSTER HUNTER RISE [0100B040117430C5][v0][DLC 197].nsz
/switch_roms/dlc/Canyne Mask Hunter layered armor piece[0100B04011743054][US][v0].nsz
/switch_roms/dlc/MONSTER HUNTER RISE [0100B0401174307A][v0][DLC].nsz
...
```

> [!CAUTION]
> Games with large amounts of DLC take a considerable amount of time to process, even when being read locally from the same system. This is a limitation of Squirrel, I'm looking for alternatives or fixes that could speed it up.

## Screenshots: 
![image](https://github.com/designgears/EmuRomManager/assets/799451/04dea1bc-1297-436d-b989-adfd920f6976)
![image](https://github.com/designgears/EmuRomManager/assets/799451/dc8ddaf5-2efa-4729-8fb5-1b176e2ed4a7)
