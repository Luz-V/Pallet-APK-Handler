:: Pallet APK Handler - Désinstallateur de packages utilisateur automatisé

:: Désinstalle TOUS les packages utilisateurs qui ne sont PAS listés dans le fichier "packages.txt".
:: Si le fichier "packages_utiles.txt" n'est pas détecté, le script est interrompu
:: Si le fichier "packages_utiles.txt" est vide, tous les packages utilisateurs seront désinstallés

@echo off
chcp 1252 >nul
setlocal enabledelayedexpansion

:: Définition des fichiers et dossiers
set "LIST_FILE=%CD%\lists\packages_usefull.txt"
set "TMP_FILE=%CD%\installed_packages.tmp"

:: Vérification de la connexion ADB
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

:: Vérification de l'existence du fichier packages.txt
if not exist "%LIST_FILE%" (
    echo "packages_usefull.txt" : fichier introuvable
    exit /b
)

echo Lecture de la liste des applications à conserver...
set "PKG_LIST_KEEP="
for /f "delims=" %%a in ('type "%LIST_FILE%"') do (
    set "PKG_LIST_KEEP=!PKG_LIST_KEEP! %%a"
)
echo.

:: Récupération de la liste des applications utilisateur installées
echo Récupération de la liste des applications utilisateur installées...
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
echo Désinstallations terminées.
exit /b