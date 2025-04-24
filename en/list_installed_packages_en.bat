REM Pallet APK Handler - Detector of installed user packages

REM Creates a "installed_packages.txt" list of user packages installed on the connected android device.

@echo off
chcp 1252 >nul
setlocal enabledelayedexpansion

:: Definition of output file
set "LIST_FILE=%CD%\installed_packages.txt"

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

:: Extracting user applications
echo Extracting the list of user applications...
adb shell pm list packages -3 > "%LIST_FILE%"

:: Cleaning the output format
(for /f "tokens=2 delims=:" %%p in ('type "%LIST_FILE%"') do echo %%p) > "%LIST_FILE%.tmp"
move /Y "%LIST_FILE%.tmp" "%LIST_FILE%" >nul

echo List of applications saved in "%LIST_FILE%".
exit /b
