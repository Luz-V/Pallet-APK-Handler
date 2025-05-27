@echo off
chcp 1252 >nul
cd /d "%~dp0"
setlocal

:: === V�rification des droits administrateur ===
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo ? Ce script n�cessite les droits administrateur.
    echo Faites un clic droit sur ce fichier .bat et choisissez "Ex�cuter en tant qu'administrateur".
    pause
    exit /b
)

echo ? Droits administrateur d�tect�s.

echo.
echo === �tape 1 : Installation d'ADB ===
if exist "Latest-ADB-Installer.bat" (
    call "Latest-ADB-Installer.bat"
) else (
    echo ? Erreur : Latest-ADB-Installer.bat introuvable.
    pause
    exit /b 1
)

echo.
echo === �tape 2 : Installation de 7-Zip Zstandard ===
if exist "7z24.09-zstd-x64.exe" (
    "7z24.09-zstd-x64.exe" /S
) else (
    echo ? Erreur : 7z24.09-zstd-x64.exe introuvable.
    pause
    exit /b 1
)

echo.
echo === �tape 3 : Ajout du dossier 7-Zip-Zstandard au PATH ===

set "SEVENZIP_DIR=C:\Program Files\7-Zip-Zstandard"

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
"$envPath = [Environment]::GetEnvironmentVariable('Path', 'Machine'); ^
if (-not $envPath.ToLower().Contains('%SEVENZIP_DIR%'.ToLower())) { ^
    [Environment]::SetEnvironmentVariable('Path', $envPath + ';%SEVENZIP_DIR%', 'Machine'); ^
    Write-Host '? Chemin ajout� avec succ�s.' ^
} else { ^
    Write-Host '?? Chemin d�j� pr�sent dans le PATH.' ^
}"

echo.
echo === �tape 4 : V�rification des installations ===
echo.

:: V�rification d'ADB
echo V�rification d'ADB :
where adb >nul 2>&1 && adb version || echo ? ADB non trouv�.

echo.
:: V�rification de 7-Zip (affiche juste les premi�res lignes)
echo V�rification de 7-Zip :
where 7z >nul 2>&1 && echo ? 7z trouv�. || echo ? 7z non trouv� (v�rifiez que le chemin est bien ajout� au PATH).

echo.
echo ? Script termin�.
pause
exit /b
