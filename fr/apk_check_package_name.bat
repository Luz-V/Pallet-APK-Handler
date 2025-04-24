:: Pallet APK Handler - Vérificateur de nom de package pour fichers APK/APKS.

:: Indique via aapt le nom de package d'un fichier .apk ou apks donné
:: Syntaxe : apk_check_package_name.bat $FICHIER_APK(S)

@echo off
chcp 1252 >nul
setlocal enabledelayedexpansion

REM Vérification que l'argument est fourni
if "%~1"=="" (
    echo Erreur : Aucun fichier APK(S) fourni en argument.
    exit /b
)

REM Définir le fichier d'entrée
set "INPUT_FILE=%~1"

REM Vérifier que le fichier existe
if not exist "%INPUT_FILE%" (
    echo Erreur : Le fichier "%INPUT_FILE%" n'existe pas.
    exit /b
)

REM Définir le chemin de l'exécutable aapt (à adapter si nécessaire)
set "AAPT_CMD=D:\Android_SDK\build-tools\36.0.0\aapt"

REM Vérifier que l'extension est .apk ou apks
if /I "%~x1"==".apk" goto apk_file
if /I "%~x1"==".apks" goto apks_file
echo Erreur : Ce script supporte uniquement les fichiers APK ou APKS.
exit /b

:apk_file
REM Exécuter aapt dump badging et extraire le nom du package en utilisant ' comme délimiteur.
for /f "tokens=2 delims='" %%A in ('%AAPT_CMD% dump badging "%INPUT_FILE%" ^| findstr /C:"package: name="') do (
	set "PACKAGE_NAME=%%A"
)
goto correct_end

:apks_file
REM Extraction des apk dans un dossier temporaire
mkdir tmp >nul 2>&1
7z x "%INPUT_FILE%" -o"%CD%\tmp" -y >nul 2>&1

REM Exécuter aapt dump badging et extraire le nom du package en utilisant ' comme délimiteur.
for /f "delims=" %%A in ('dir /b /a:-d "%CD%\tmp\*.apk" ^| sort') do (
	REM Arrêt dès qu'un package_name est trouvé
	if not defined PKG_NAME (
		for /f "tokens=2 delims=='" %%P in ('%AAPT_CMD% dump badging "%CD%\tmp\%%A" ^| findstr /C:"package: name="') do (
			set "PACKAGE_NAME=%%P"
		)
	)
)
REM suppression du dossier temporaire
del /Q tmp\ 
goto correct_end

REM fin
:correct_end
echo Nom du package : !PACKAGE_NAME!
endlocal
exit /b
