:: Pallet APK Handler - Automated User Package Uninstaller

:: Uninstall ALL user packages that are NOT listed in the "packages.txt" file.
:: If the file "packages_utiles.txt" is not detected, the script is interrupted
:: If the file "packages_utiles.txt" is empty, all user packages will be uninstalled

@echo off
chcp 1252 >nul
setlocal enabledelayedexpansion

:: Definition of files and folders
set "LIST_FILE=%CD%\packages_usefull.txt"
set "TMP_FILE=%CD%\installed_packages.tmp"

:: Verification of ADB connection
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

:: Checking the existence of the package.txt file
if not exist "%LIST_FILE%" (
    echo "packages_usefull.txt": file not found
    exit /b
)

echo Reading the list of applications to keep...
set "PKG_LIST_KEEP="
for /f "delims=" %%a in ('type "%LIST_FILE%"') do (
    set "PKG_LIST_KEEP=!PKG_LIST_KEEP! %%a"
)
echo.

:: Recovery of the list of installed user applications
echo Recovery of the list of installed user applications...
adb shell pm list packages -3 > "%TMP_FILE%"
echo.

:: Comparison and removal of unnecessary applications
echo Removal of unnecessary applications...
for /f "tokens=2 delims=:" %%p in ('type "%TMP_FILE%"') do (
    set "FOUND=0"
    for %%k in (!PKG_LIST_KEEP!) do (
        if "%%p"=="%%k" set "FOUND=1"
    )
    if !FOUND! == 0 (
        echo Removal of %%p...
        adb uninstall %%p
    )
)
echo.

:: Cleaning
del "%TMP_FILE%"
echo Disinstallations completed.
exit /b