# Pallet APK Handler
## A Small script collection for android package managment

As there is virtually no free Android Mobile Devices Managment (MDM) tools for small non profits organisation at the moment, I decided to sharpen my own tools for backups, restore, listing and others operations on android packages. Theses python+adb scripts are draft material for more advanced operation, but they are already operationnal for android application deployment via debian+adb on rooted devices. A step combined with [Neo-Backup](https://github.com/NeoApplications/Neo-Backup) and [AppManager](https://github.com/MuntashirAkon/AppManager) backup files is planned.

Help yourself, get chunks of theses as your convenience.

## Requirements 
Executing the `install.sh` script will setup :
- 7z with Zstandard (zstd) functions, [see here](https://github.com/mcmilk/7-Zip-zstd)
- [aapt](https://stackoverflow.com/questions/28234671/what-is-aapt-android-asset-packaging-tool-and-how-does-it-work) for some specific parts
- ADB
- Python and python venv

Usb debug mode should be activated on android devices (preferably rooted for data restore operations)

## What already works
### Adb basic operations
- Scanning devices, showing packages and versions, with research filter
- Export a list of user-installed packages
- Extract user-installed packages installer archives (apk/apks)
- Package name extraction from apk with aapt
### Batch install/uninstall and restore operations
- Batch install/uninstall packages based on a given package list or found apk(s) in a directory
- **[Not UI-implemented yet]** Batch install+restore backups for [Neo-Backup](https://github.com/NeoApplications/Neo-Backup) and [AppManager](https://github.com/MuntashirAkon/AppManager) backups files on a given package list or found backups in a directory 

## What is planned
- Packages data advanced backup restoration with Neo-Backup (and/or AppManager)
- Smoothing UI
