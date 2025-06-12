REM Pallet APK Handler - D�sinstallateur de packages utilisateur automatis�

REM D�sinstalle TOUS les packages utilisateurs qui SONT list�s dans le fichier "packages.txt".
REM Si le fichier "packages_inutiles.txt" n'est pas d�tect�, le script est interrompu
REM Si le fichier "packages_inutiles.txt" est vide, rien ne se passe

@echo off
chcp 1252 >nul
setlocal enabledelayedexpansion

:: D�finition des fichiers et dossiers
set "LIST_FILE=%CD%\lists\packages_useless.txt"

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
    echo "packages_useless.txt" : fichier introuvable
    exit /b
)

echo Lecture de la liste des applications � supprimer...
set "PKG_LIST_DEL="
for /f "delims=" %%a in ('type "%LIST_FILE%"') do (
    set "PKG_LIST_DEL=!PKG_LIST_DEL! %%a"
)
echo.

:: Suppression des applications inutiles
echo Suppression des applications list�es ...
for %%k in (!PKG_LIST_DEL!) do (
    echo Suppression de %%k...
    adb uninstall %%k
)
echo.

:: Fin
echo D�sinstallations termin�es.
exit /b