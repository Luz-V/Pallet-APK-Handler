REM Pallet APK Handler - Automated APK/APKS Installer

REM Install ALL apk and apks files in the ./apks directory
REM which are missing from the connected android device
REM Warning: Do not update

@echo off
chcp 1252 >nul
setlocal enabledelayedexpansion

:: Definition of directories and files
set "APK_DIR=%CD%\apks"
set "TMP_DIR=%APK_DIR%\tmp"

:: ADB verification
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

:: Recovery of already installed packages
echo Reading installed packages...
set "INSTALLED_LIST="
for /f "tokens=2 delims=:" %%p in ('adb shell pm list packages') do (
    set "INSTALLED_LIST=!INSTALLED_LIST! %%p"
)

:: Creating the temporary folder if not existing
if not exist "%TMP_DIR%" mkdir "%TMP_DIR%"

echo.
echo Start of installation of packages ...
echo.

:: Loop on APK+APKS files
for %%F in ("%APK_DIR%\*.apk") do (
    set "FILE_NAME=%%~nxF"
    set "PKG_NAME="

	:: Reading .apk
    if /I "%%~xF"==".apk" (
		:: Extracton of the package name via aapt
        for /f "tokens=2 delims=='" %%A in ('D:\Android_SDK\build-tools\36.0.0\aapt dump badging "%%F" ^| findstr /C:"package: name="') do (
            set "PKG_NAME=%%A"
        )
    )
	:: Reading .apks
    if /I "%%~xF"==".apks" (
		:: First extraction via 7z
        7z x "%%F" -o"%TMP_DIR%" -y >nul 2>&1
		for /f "delims=" %%A in ('dir /b /a:-d "%TMP_DIR%\*.apk" ^| sort') do (
			if not defined PKG_NAME (
				:: Extracton of the package name via aapt
				for /f "tokens=2 delims=='" %%P in ('D:\Android_SDK\build-tools\36.0.0\aapt dump badging "%TMP_DIR%\%%A" ^| findstr /C:"package: name="') do (
					set "PKG_NAME=%%P"
				)
			)
        )
    )
    echo FILE_NAME! - Package detected: !PKG_NAME!

	:: Check if package is to be installed
    set "INSTALL=0"
    if defined PKG_NAME (
        set "IS_INSTALLED=0"
		:: Search the package in the list of installed packages
        for %%I in (!INSTALLED_LIST!) do (
            if "!PKG_NAME!"=="%%I" set "IS_INSTALLED=1"
        )
        if !IS_INSTALLED! == 0 (
			:: Case 1 => package not installed
            set "INSTALL=1"
        ) else (
			:: Case 2 => already installed package
            echo !PKG_NAME! already installed.
        )
    )

	:: Installation
    if !INSTALL! == 1 (
		:: Case APK Simple
        if /I "%%~xF"==".apk" (
            echo FILE_NAME! - Installation...
            adb install "%%F"
        )
		:: APKS cases
        if /I "%%~xF"==".apks" (
            set "APK_LIST="
            for %%A in ("%TMP_DIR%\*.apk") do (
                set "APK_LIST=!APK_LIST! "%%A""
            )
            echo FILE_NAME! - Multiple installation...
            adb install-multiple !APK_LIST!
        )
    )
	:: Cleaning the temporary directory
    del /Q "%TMP_DIR%\*"
    echo.
)

echo End of installations.
exit /b