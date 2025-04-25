REM Pallet APK Handler - DEPRECATED Data backup for android user-installed apps by adb backup

REM WARNING - The 'adb backup' command is defined for most applications starting from Android 10

REM Backs up the data of EVERY user application detected on the connected Android device.
REM Creates a backup in the adb-backup-data folder
REM Creates a list "packages_extracted.txt" of user packages installed on the connected Android device.

@echo off
chcp 1252 >nul
setlocal enabledelayedexpansion

:: Define folder and variable
set "AB_PATH=%CD%\adb-backup-data"
set "TMP_PATH=%CD%\tmp"
set "PKG_FILE=%TMP_PATH%\packages_extracted.txt"

:: Check ADB connection
set "ADB_CONNECTED="
for /f "skip=1 tokens=1" %%D in ('adb devices') do (
    if "%%D" neq "" (
        set "ADB_CONNECTED=1"
    )
)
if not defined ADB_CONNECTED (
    echo Error: No ADB device detected.
    exit /b
)

:: Retrive the list of installed users applications
echo Retrieving the list of installed users applications...
adb shell pm list packages -3 > "%PKG_FILE%"

:: Clean lines and assemble into a single line separated by spaces
set "PKG_LIST="
for /f "tokens=2 delims=:" %%P in ("%PKG_FILE%") do (
    set "PKG_LIST=!PKG_LIST! %%P"
)

:: Create backup folder if it doesn't exist
if not exist "%AB_PATH%" (
    mkdir "%AB_PATH%"
)

:: Start backup
echo Starting backup...
adb backup -f "%AB_PATH%\backup.ab" -apk -obb -shared -nosystem !PKG_LIST!
:: "Simple" version
:: adb backup -f "backup_all.ab" -all -apk -obb -shared

:: Clean up and end
del "%PKG_FILE%"
echo.
echo Backups completed.
exit /b
