@echo off
chcp 1252 >nul
cd /d "%~dp0"
setlocal

:: === Vérification des droits administrateur ===
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo ? Ce script nécessite les droits administrateur.
    echo Faites un clic droit sur ce fichier .bat et choisissez "Exécuter en tant qu'administrateur".
    pause
    exit /b
)

echo ? Droits administrateur détectés.

echo.
echo === Étape 1 : Installation d'ADB ===
if exist "Latest-ADB-Installer.bat" (
    call "Latest-ADB-Installer.bat"
) else (
    echo ? Erreur : Latest-ADB-Installer.bat introuvable.
    pause
    exit /b 1
)

echo.
echo === Étape 2 : Installation de 7-Zip Zstandard ===
if exist "7z24.09-zstd-x64.exe" (
    "7z24.09-zstd-x64.exe" /S
) else (
    echo ? Erreur : 7z24.09-zstd-x64.exe introuvable.
    pause
    exit /b 1
)

echo.
echo === Étape 3 : Ajout du dossier 7-Zip-Zstandard au PATH ===

set "SEVENZIP_DIR=C:\Program Files\7-Zip-Zstandard"

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
"$envPath = [Environment]::GetEnvironmentVariable('Path', 'Machine'); ^
if (-not $envPath.ToLower().Contains('%SEVENZIP_DIR%'.ToLower())) { ^
    [Environment]::SetEnvironmentVariable('Path', $envPath + ';%SEVENZIP_DIR%', 'Machine'); ^
    Write-Host '? Chemin ajouté avec succès.' ^
} else { ^
    Write-Host '?? Chemin déjà présent dans le PATH.' ^
}"

echo.
echo === Étape 4 : Vérification des installations ===
echo.

:: Vérification d'ADB
echo Vérification d'ADB :
where adb >nul 2>&1 && adb version || echo ? ADB non trouvé.

echo.
:: Vérification de 7-Zip (affiche juste les premières lignes)
echo Vérification de 7-Zip :
where 7z >nul 2>&1 && echo ? 7z trouvé. || echo ? 7z non trouvé (vérifiez que le chemin est bien ajouté au PATH).

echo.
echo ? Script terminé.
pause
exit /b
