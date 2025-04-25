REM Pallet APK Handler - Installateur d'APK/APKS automatis�

REM Installe TOUS les fichiers apk et apks pr�sents dans le r�pertoire ./apks 
REM qui sont absents de l'appareil android connect�
REM Attention : N'effectue pas les mise � jour

@echo off
chcp 1252 >nul
setlocal enabledelayedexpansion

:: D�finition des r�pertoires et fichiers
set "APK_DIR=%CD%\apks"
set "TMP_DIR=%APK_DIR%\tmp"

:: V�rification ADB
set "ADB_CONNECTED="
for /f "skip=1 tokens=1" %%D in ('adb devices') do (
    if "%%D" neq "" (
        set "ADB_CONNECTED=1"
    )
)
if not defined ADB_CONNECTED (
    echo Erreur : Aucun appareil ADB d�tect�.
    exit /b
)

:: R�cup�ration des packages d�j� install�s
echo Lecture des packages install�s...
set "INSTALLED_LIST="
for /f "tokens=2 delims=:" %%p in ('adb shell pm list packages') do (
    set "INSTALLED_LIST=!INSTALLED_LIST! %%p"
)

:: Cr�ation du dossier temporaire si non existant
if not exist "%TMP_DIR%" mkdir "%TMP_DIR%"

echo.
echo D�but de l'installation des packages ...
echo.

:: Boucle sur les fichiers APK+APKS
for %%F in ("%APK_DIR%\*.apk") do (
    set "FILE_NAME=%%~nxF"
    set "PKG_NAME="

	:: Lecture de .apk
    if /I "%%~xF"==".apk" (
		:: Extracton du package name via aapt
        for /f "tokens=2 delims=='" %%A in ('D:\Android_SDK\build-tools\36.0.0\aapt dump badging "%%F" ^| findstr /C:"package: name="') do (
            set "PKG_NAME=%%A"
        )
    )
	:: Lecture de .apks
    if /I "%%~xF"==".apks" (
		:: Premi�re extraction via 7z
        7z x "%%F" -o"%TMP_DIR%" -y >nul 2>&1
		for /f "delims=" %%A in ('dir /b /a:-d "%TMP_DIR%\*.apk" ^| sort') do (
			if not defined PKG_NAME (
				:: Extracton du package name via aapt
				for /f "tokens=2 delims=='" %%P in ('D:\Android_SDK\build-tools\36.0.0\aapt dump badging "%TMP_DIR%\%%A" ^| findstr /C:"package: name="') do (
					set "PKG_NAME=%%P"
				)
			)
        )
    )
    echo !FILE_NAME! - Package d�tect� : !PKG_NAME!

	:: V�rification si le package est � installer
    set "INSTALL=0"
    if defined PKG_NAME (
        set "IS_INSTALLED=0"
		:: Recherche du package dans la liste des packages install�s
        for %%I in (!INSTALLED_LIST!) do (
            if "!PKG_NAME!"=="%%I" set "IS_INSTALLED=1"
        )
        if !IS_INSTALLED! == 0 (
			:: Cas 1 => package non install�
            set "INSTALL=1"
        ) else (
			:: Cas 2 => package d�ja install�
            echo !PKG_NAME! d�j� install�.
        )
    )

	:: Installation
    if !INSTALL! == 1 (
		:: Cas APK Simple
        if /I "%%~xF"==".apk" (
            echo !FILE_NAME! - Installation...
            adb install "%%F"
        )
		:: Cas APKS
        if /I "%%~xF"==".apks" (
            set "APK_LIST="
            for %%A in ("%TMP_DIR%\*.apk") do (
                set "APK_LIST=!APK_LIST! "%%A""
            )
            echo !FILE_NAME! - Installation multiple...
            adb install-multiple !APK_LIST!
        )
    )
	:: Nettoyage du r�pertoire temporaire
    del /Q "%TMP_DIR%\*"
    echo.
)

echo Fin des installations.
exit /b