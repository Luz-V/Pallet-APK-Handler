REM Pallet APK Handler - Installateur d'APK/APKS automatisé via liste txt

REM Installe les fichiers apk et apks présents dans le répertoire ./apks qui sont :
REM - Listés dans le fichier "packages_to_install.txt" 
REM - Absents de l'appareil android connecté

REM Attention : N'effectue pas les mise à jour

@echo off
chcp 1252 >nul
setlocal enabledelayedexpansion

:: Définition des répertoires et fichiers
set "APK_DIR=%CD%\apks"
set "TMP_DIR=%APK_DIR%\tmp"
set "LIST_FILE=%CD%\packages_to_install.txt"
:: set "7z=C:\Program Files\7-Zip\7z.exe"

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

:: Vérification du fichier liste de packages à installer
if not exist "%LIST_FILE%" (
    echo "packages_to_install.txt" introuvable.
    exit /b
)
:: Lecture de la liste de packages à installer
echo Lecture des packages à autoriser...
set "PKG_LIST="
for /f "delims=" %%L in ('type "%LIST_FILE%"') do (
    set "PKG_LIST=!PKG_LIST! %%L"
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
echo Début de l'installation conditionnelle des packages ...
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
            set "FOUND=0"
            for %%K in (!PKG_LIST!) do (
                if "!PKG_NAME!"=="%%K" set "FOUND=1"
            )
            if !FOUND! == 1 (
				:: Cas 1.a => package non installé et listé à installé
                set "INSTALL=1"
            ) else (
				:: Cas 1.b => package non installé et non listé
                echo !PKG_NAME! non listé - ignoré.
            )
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