REM Pallet APK Handler - Installateur d'APK/APKS automatisé

REM Installe TOUS les fichiers apk et apks présents dans le répertoire ./apks 
REM qui sont absents de l'appareil android connecté
REM Attention : N'effectue pas les mise à jour

@echo off
chcp 1252 >nul
setlocal enabledelayedexpansion

:: Définition des répertoires et fichiers
set "APK_DIR=%CD%\apks"
set "TMP_DIR=%APK_DIR%\tmp"

:: Vérification ADB
set "ADB_CONNECTED="
for /f "skip=1 tokens=1" %%D in ('adb devices') do (
    if "%%D" neq "" (
        set "ADB_CONNECTED=1"
    )
)
if not defined ADB_CONNECTED (
    echo Erreur : Aucun appareil ADB détecté.
    exit /b
)

:: Récupération des packages déjà installés
echo Lecture des packages installés...
set "INSTALLED_LIST="
for /f "tokens=2 delims=:" %%p in ('adb shell pm list packages') do (
    set "INSTALLED_LIST=!INSTALLED_LIST! %%p"
)

:: Création du dossier temporaire si non existant
if not exist "%TMP_DIR%" mkdir "%TMP_DIR%"

echo.
echo Début de l'installation des packages ...
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
		:: Première extraction via 7z
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
    echo !FILE_NAME! - Package détecté : !PKG_NAME!

	:: Vérification si le package est à installer
    set "INSTALL=0"
    if defined PKG_NAME (
        set "IS_INSTALLED=0"
		:: Recherche du package dans la liste des packages installés
        for %%I in (!INSTALLED_LIST!) do (
            if "!PKG_NAME!"=="%%I" set "IS_INSTALLED=1"
        )
        if !IS_INSTALLED! == 0 (
			:: Cas 1 => package non installé
            set "INSTALL=1"
        ) else (
			:: Cas 2 => package déja installé
            echo !PKG_NAME! déjà installé.
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
	:: Nettoyage du répertoire temporaire
    del /Q "%TMP_DIR%\*"
    echo.
)

echo Fin des installations.
exit /b