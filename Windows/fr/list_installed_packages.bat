REM Pallet APK Handler - Détecteur de packages utilisateurs installés

REM Crée une liste "installed_packages.txt" des packages utilisateurs installés sur l'appareil android connecté.

@echo off
chcp 1252 >nul
setlocal enabledelayedexpansion

:: Définition du fichier de sortie
set "LIST_FILE=%CD%\lists\installed_packages.txt"

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

:: Extraction des applications utilisateur
echo Extraction de la liste des applications utilisateur...
adb shell pm list packages -3 > "%LIST_FILE%"

:: Nettoyage du format de sortie
(for /f "tokens=2 delims=:" %%p in ('type "%LIST_FILE%"') do echo %%p) > "%LIST_FILE%.tmp"
move /Y "%LIST_FILE%.tmp" "%LIST_FILE%" >nul

echo Liste des applications enregistrée dans "%LIST_FILE%".
exit /b
