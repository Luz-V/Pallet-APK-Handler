REM Pallet APK Handler - Automated User Package Uninstaller

REM Uninstall ALL user packages that are listed in the "packages.txt" file.
REM If the file "packages_inutiles.txt" is not detected, the script is interrupted
REM If the file "packages_inutiles.txt" is empty, nothing happens

@echo off
chcp 1252 >nul
setlocal enabledelayedexpansion

:: Definition of files and folders
set "LIST_FILE=%CD%\packages_useless.txt"

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
    echo "packages_useless.txt": file not found
    exit /b
)

echo Reading the list of applications to delete...
set "PKG_LIST_DEL="
for /f "delims=" %%a in ('type "%LIST_FILE%"') do (
    set "PKG_LIST_DEL=!PKG_LIST_DEL! %%a"
)
echo.

:: Removal of unnecessary applications
echo Removal of listed applications ...
for %%k in (!PKG_LIST_DEL!) do (
    echo Remove %%k...
    adb uninstall %%k
)
echo.

:: End
echo Disinstallations completed.
exit /b