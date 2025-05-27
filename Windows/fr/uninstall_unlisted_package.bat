:: Pallet APK Handler - D�sinstallateur de packages utilisateur automatis�

:: D�sinstalle TOUS les packages utilisateurs qui ne sont PAS list�s dans le fichier "packages.txt".
:: Si le fichier "packages_utiles.txt" n'est pas d�tect�, le script est interrompu
:: Si le fichier "packages_utiles.txt" est vide, tous les packages utilisateurs seront d�sinstall�s

@echo off
chcp 1252 >nul
setlocal enabledelayedexpansion

:: D�finition des fichiers et dossiers
set "LIST_FILE=%CD%\lists\packages_usefull.txt"
set "TMP_FILE=%CD%\installed_packages.tmp"

:: V�rification de la connexion ADB
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

:: V�rification de l'existence du fichier packages.txt
if not exist "%LIST_FILE%" (
    echo "packages_usefull.txt" : fichier introuvable
    exit /b
)

echo Lecture de la liste des applications � conserver...
set "PKG_LIST_KEEP="
for /f "delims=" %%a in ('type "%LIST_FILE%"') do (
    set "PKG_LIST_KEEP=!PKG_LIST_KEEP! %%a"
)
echo.

:: R�cup�ration de la liste des applications utilisateur install�es
echo R�cup�ration de la liste des applications utilisateur install�es...
adb shell pm list packages -3 > "%TMP_FILE%"
echo.

:: Comparaison et suppression des applications inutiles
echo Suppression des applications inutiles...
for /f "tokens=2 delims=:" %%p in ('type "%TMP_FILE%"') do (
    set "FOUND=0"
    for %%k in (!PKG_LIST_KEEP!) do (
        if "%%p"=="%%k" set "FOUND=1"
    )
    if !FOUND! == 0 (
        echo Suppression de %%p...
        adb uninstall %%p
    )
)
echo.

:: Nettoyage
del "%TMP_FILE%"
echo D�sinstallations termin�es.
exit /b