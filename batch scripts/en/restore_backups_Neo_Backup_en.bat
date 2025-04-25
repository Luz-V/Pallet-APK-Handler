@echo off
chcp 1252 >nul
setlocal enabledelayedexpansion

:: Main directories
set "ROOT_DIR=%CD%"
set "TMP_DIR=%ROOT_DIR%\tmp"
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

:: Creation of the temporary directory
if not exist "%TMP_DIR%" mkdir "%TMP_DIR%"

:: Recovery of the list of installed user applications
echo Recovery of the list of installed user applications...
adb shell pm list packages -3 > "%TMP_FILE%"
echo.

echo.
echo Start of the Neo Backup...
echo.

:: Buckle on package folders
for /d %%P in ("%ROOT_DIR%\*") do (
    set "PKG_NAME=%%~nxP"
    set "PKG_PATH=%%~fP"

    :: Searching the backup subfolder
    for /d %%S in ("!PKG_PATH!\*-user_0") do (
        set "SAVE_DIR=%%~fS"
        set "SAVE_NAME=%%~nxS"

        echo PKG_NAME! : Treatment of the package ...
        REM echo Backup folder : !SAVE_NAME!
        
		set "INSTALLED=0"
		for /f "tokens=2 delims=:" %%I in ('type "!TMP_FILE!"') do (
			if "%%I"=="!PKG_NAME!" (
				set "INSTALLED=1"
				echo PKG_NAME!: Package already installed.
			)
		)
		if !INSTALLED! == 0 (
			echo !PKG_NAME! : Installation
			:: Extraction and installation of KPAs
			set "APK_LIST="
			for %%A in ("!SAVE_DIR!\*.apk") do (
				set "APK_LIST=!APK_LIST! "%%~fA""
			)
			if defined APK_LIST (
				echo Installation of !PKG_NAME! ...
				REM echo APK detected: !APK_LIST!
				adb install-multiple !APK_LIST!
				set "INSTALLED=1"
			) else (
				echo No APK found for !PKG_NAME! - Ignoreed.
			)
		)

		if !INSTALLED! == 1 (
			:: Data restoration
			echo !PKG_NAME! : Search for possible backups ...
			set "DATA_FILE=!SAVE_DIR!\data.tar.zst"
			set "DATA_FILE_EXT=!SAVE_DIR!\external_files.tar.zst"

			:: Data.tar.zst processing
			if exist "!SAVE_DIR!\data.tar.zst" (
				REM echo Decompression of !DATA_FILE! ...
				7z x "!DATA_FILE!" -o"!TMP_DIR!" -y >nul
				7z x "!TMP_DIR!\data.tar" -o"!TMP_DIR!" -y >nul
				del "!TMP_DIR!\data.tar"
				REM echo Data transfer to device...
				adb push "!TMP_DIR!\." /storage/emulated/0/neo_tmp/
				REM The user is root, and everything is placed in /data/data/<pkg>
				REM Final move to /data/data/!PKG_NAME!/ ...
				adb shell su -c "mkdir -p /data/data/!PKG_NAME!"
				adb shell su -c "cp -r /storage/emulated/0/neo_tmp/. /data/data/!PKG_NAME!"
				adb shell su -c "rm -rf /storage/emulated/0/neo_tmp"
				:: Cleaning TMP_DIR
				rmdir /s /q "!TMP_DIR!"
				mkdir "!TMP_DIR!"
			) else (
				REM !PKG_NAME! : Data.tar.zst file not found, or application not installed
			)

			:: Processing external_files.tar.zst
			if exist "!SAVE_DIR!\external_files.tar.zst" (
				REM echo Decompression of !DATA_FILE_EXT! ...
				7z x "!DATA_FILE_EXT!" -o"!TMP_DIR!" -y >nul
				7z x "!TMP_DIR!\external_files.tar" -o"!TMP_DIR!" -y >nul
				del "!TMP_DIR!\external_files.tar"

				REM echo Data transfer to device...
				adb push "!TMP_DIR!\." /storage/emulated/0/neo_tmp/
				REM The user is root, and everything is placed in /storage/emulated/0/Android/data/<pkg>
				REM Final move to /storage/emulated/0/Android/data/!PKG_NAME!/ ...
				adb shell su -c "mkdir -p /storage/emulated/0/Android/data/!PKG_NAME!"
				adb shell su -c "cp -r /storage/emulated/0/neo_tmp/. /storage/emulated/0/Android/data/!PKG_NAME!"
				adb shell su -c "rm -rf /storage/emulated/0/neo_tmp"
				:: Cleaning TMP_DIR
				rmdir /s /q "!TMP_DIR!"
				mkdir "!TMP_DIR!"
			) else (
				REM !PKG_NAME! : External_files.tar.zst file not found, or application not installed
			)
			echo !PKG_NAME! : End of restoration.
		)
	echo.
	)
)
del !TMP_FILE!

echo Restart Play Store...
adb shell am force-stop com.android.vending >nul
adb shell monkey -p com.android.vending -c android.intent.category.LAUNCHER 1 >nul

echo.
echo Restorations completed.
exit /b
