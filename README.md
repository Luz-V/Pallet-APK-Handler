# Pallet APK Handler
## Small script collection for android package managment

As there is virtually no free Android Mobile Devices Managment (MDM) tools for small non profits organisation at the moment, I decided to sharpen my own tools for backups, restore, listing and others operations on android packages. Theses batch/adb scripts are draft material for more advanced operation, but they are already operationnal for android application deployment on rooted devices with Neo-backup and AppManager backup files.

Help yourself, get chunks of theses as your convenience.

## Requirements
- 7z with Zstandard (zstd) functions, [see here](https://github.com/mcmilk/7-Zip-zstd)
- [aapt](https://stackoverflow.com/questions/28234671/what-is-aapt-android-asset-packaging-tool-and-how-does-it-work) for some specific parts
- An android device with debug mode activated (preferably rooted for advanced backups)
- Windows : did only batch scripts for the moment, will rewrite them in bash eventually

## What already works
### Adb basic operations
- Export a list of user-installed packages
- Extract user-installed packages installer archives (apk/apks)
- Package name extraction from apk with aapt
### Batch install/uninstall and restore operations
- Batch install/uninstall packages based on a given package list or found apk(s) in a directory
- Batch install+restore backups for [Neo-Backup](https://github.com/NeoApplications/Neo-Backup) and [AppManager](https://github.com/MuntashirAkon/AppManager) backups files on a given package list or found backups in a directory 

## What is planned
- Bash rewrite
- Function-based rewrite 
- Package version checks when restoring package data
- Neo-Backup advanced backup restoration
