REM Pallet APK Handler - Neo-Backup Backup

REM Attention - Do not manage version checks
REM Require root rights
REM Requires 7zip with ZST decompression function

REM Restore backups in Neo-Backup format (and reinstall the package if not installed)
REM Neo-Backup backups are detected automatically in the tree
REM These backups include:
REM - Base.apk installer (+ possible APK splits),
REM - A metadata file [DATE].properties and configuration files "data.tar.zst" and "external_files.tar.zst"

@echo off
chcp 1252 >nul
setlocal enabledelayedexpansion

:: Definition of directories and files
set "APK_DIR=%CD%\apks"
set "TMP_DIR=%CD%\tmp"
:: set "7z.exe=C:\Program Files\7-Zip\7z.exe"

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

:: Creating the temporary folder if not existing
if not exist "%TMP_DIR%" mkdir "%TMP_DIR%"

echo.
echo Reading backups ...
echo.

:: Loop on folders
for /d %%A in ("%CD%\*") do (
	set "APP_DIR=%%~fA"
	set "DUMMY=!APP_DIR!"
	:: Exclusion of the "apks" folder, which is not a backup folder
	if "!APP_DIR!"=="!APK_DIR!" (
		echo Apks folder detected
		echo.
	) else (
		echo Folder!APP_DIR!
		:: Processing the directory of an application
		set "META_FILE=!APP_DIR!\0\meta_v2.am.json"
		if not exist "!META_FILE!" (
			echo Missing meta_v2.am.json file for !APP_DIR!
		) else (
			:: Reading meta_v2.am.json file information (to be improved)
			set "APP_PKG="
			set "IS_SPLIT_APK=false"
			:: Using findstr to extract basic data
			for /f "tokens=1,* delims=:" %%B in ('findstr "package_name" "!META_FILE!"') do (
				set "APP_PKG=%%C"
			)
			for /f "tokens=1,* delims=:" %%B in ('findstr "is_split_apk" "!META_FILE!"') do (
				set "IS_SPLIT_APK=%%C"
			)
			:: Clean names by deleting quotes, spaces at the beginning and last character
			for %%V in (APP_PKG IS_SPLIT_APK) do (
				set "%%V=!%%V:"=!"  :: Enlève les guillemets
				set "%%V=!%%V:~1!"  :: Enlève l'espace au début
				set "%%V=!%%V:~0,-1!"  :: Enlève le dernier caractère (virgule ou guillemet)
			)

			:: Using findstr to extract directory data
			set "DATA_DIRS="
			set "IN_DATA_DIRS=0"
			set "COUNT=-2"
			
			for /f "usebackq delims=" %%A in ("!META_FILE!") do (
				set "LINE=%%A"
				:: Check if you find the string "data_dirs": [
				echo LINE! Findstr /C:"\"data_dirs\": ["nul && set "IN_DATA_DIRS=1"
				:: If we're in data_dirs and we meet ']', we stop
				if !IN_DATA_DIRS! == 1 (
					echo LINE! Findstr /C:"]" >nul && set "IN_DATA_DIRS=0"
					:: Line cleaning and storage in a numbered variable
					set /a COUNT+=1
					set "LINE=!LINE:\/=/!"
					set "LINE=!LINE:    =!"
					set "LINE=!LINE: =!"
					set "LINE=!LINE:"=!"
					set "LINE=!LINE:,=!"
					set "DATA_DIR_!COUNT!=!LINE!"
				)
			)

			:: Installation
			echo Restoration of the package!APP_PKG! :
			echo.
			
			set "SOURCE_FILE=!APP_DIR!\0\source.tar.gz.0"
			:: Decompression of .apk file by 7-zip
			7z.exe x "!SOURCE_FILE!" -o"!TMP_DIR!" -y >nul 2>&1
			7z.exe x "!TMP_DIR!\source.tar.gz" -o"!TMP_DIR!" -y >nul 2>&1
			del "!TMP_DIR!\source.tar.gz"
			pause
			:: Check the list of extracted APK files
			set "APK_LIST="
			for %%F in ("!TMP_DIR!\*.apk") do (
				set "APK_LIST=!APK_LIST! "%%F""
			)
			if "!IS_SPLIT_APK!"=="true" (
				:: Multiple installation
				echo !APP_PKG! : Installation in Split APK mode...
				adb install-multiple !APK_LIST!
			) else (
				:: Simple installation
				echo !APP_PKG! : Standard installation...
				adb install "!APK_LIST!"
			)
			
			:: Cleaning of temporary directory
			del "!TMP_DIR!\*" /Q
			:: Double cleaning?
			rmdir /s "!TMP_DIR!" /Q
			mkdir "!TMP_DIR!"
			
			echo !APP_PKG! : Data transfer, !COUNT! directory detected ...
			
			set /a LAST_INDEX=!COUNT!-1			
			for /L %%I in (0,1,!LAST_INDEX!) do (
				:: echo Decompression of data0.tar.gz.%I
				7z.exe x -o"!TMP_DIR!" "!APP_DIR!\0\data%%I.tar.gz.0" -y >nul 2>&1
				7z.exe x -o"!TMP_DIR!" "!TMP_DIR!\data%%I.tar.gz" -y >nul 2>&1
				:: echo Delete compressed files
				del "!TMP_DIR!\data%%I.tar.gz" /Q
				pause
				if exist "!TMP_DIR!\*" (			
					:: echo Send files to!TMP_DIR! to /storage/emulated/0/
					adb push "!TMP_DIR!" /storage/emulated/0/
					:: echo directory creation!DATA_DIR_%%I!
					adb shell su -c "mkdir !DATA_DIR_%%I!/"
					:: echo Transfer files from /storage/emulated/0/ to!DATA_DIR_%%I! then clean /storage/emulated/0/
					adb shell su -c "cp -r /storage/emulated/0/tmp/. '!DATA_DIR_%%I!/' && rm -rf /storage/emulated/0/tmp/*"
					:: echo Cleaning temporary directory
					rmdir /s "!TMP_DIR!" /Q
					mkdir "!TMP_DIR!"
				) else (
					echo Error: Unable to uncompress data0.tar.gz.%%I
				)
				echo !APP_PKG! : End of transfer.
			)
			echo.
		)
	)
)

echo restarting the google play service...
adb shell am force-stop com.android.vending >nul 2>&1
adb shell monkey -p com.android.vending -c android.intent.category.LAUNCHER 1 >nul 2>&1
echo.

echo Restorations completed.
exit /b