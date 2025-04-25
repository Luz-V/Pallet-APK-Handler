REM Pallet APK Handler - Désinstallateur de packages utilisateur automatisé

REM Désinstalle TOUS les packages utilisateurs qui SONT listés dans le fichier "packages.txt".
REM Si le fichier "packages_inutiles.txt" n'est pas détecté, le script est interrompu
REM Si le fichier "packages_inutiles.txt" est vide, rien ne se passe

@echo off
chcp 1252 >nul
setlocal enabledelayedexpansion

:: Définition des fichiers et dossiers
set "LIST_FILE=%CD%\packages_useless.txt"

:: Vérification de la connexion ADB
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

:: Vérification de l'existence du fichier packages.txt
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

:: Suppression des applications inutiles
echo Removal of listed applications ...
for %%k in (!PKG_LIST_DEL!) do (
    echo Remove %%k...
    adb uninstall %%k
)
echo.

:: Fin
echo Disinstallations completed.
exit /b