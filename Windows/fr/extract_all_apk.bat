REM Pallet APK Handler - Extracteur de packages au format APK/APKS

REM Extrait TOUS les packages utilisateurs install�s sur l'appareil android connect� sous forme de fichiers apk et apks. 
REM Cr�e �galement un fichier "packages_extracted.txt" listant les packages utilisateurs d�tect�s.

@echo off
chcp 1252 >nul
setlocal enabledelayedexpansion

:: D�finition des r�pertoires
set "OUTPUT_DIR=%CD%\apks_extracted"
set "LIST_FILE_0=%CD%\lists\packages_tmp.txt"
set "LIST_FILE_1=%CD%\lists\packages_extracted.txt"

:: Cr�ation du r�pertoire de destination
if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"

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

echo Extraction de la liste des applications utilisateur...
adb shell pm list packages -3 > "%LIST_FILE_0%"
echo.

:: Nettoyage du format de sortie
(for /f "tokens=2 delims=:" %%p in ('type "%LIST_FILE_0%"') do echo %%p) > "%LIST_FILE_1%"
del "%LIST_FILE_0%"

echo Extraction des fichiers APK ...
echo.
:: Extraction des APK/APKS
for /f "usebackq delims=" %%p in ("%LIST_FILE_1%") do (
    echo Extraction de %%p...
	:: R�cup�rer le chemin de(s) APK(s)
	set "COUNT=0"
	for /f "tokens=2 delims=:" %%a in ('adb shell pm path "%%p"') do (
		set /a COUNT+=1
		set "APK_PATH!COUNT!=%%a"
	)
	
	:: Cas d'un seul APK
	if !COUNT! equ 1 (
		set "APK_PATH=!APK_PATH1:~1!"
		adb pull "!APK_PATH!" "%OUTPUT_DIR%\%%p.apk" >nul
	) else (
		echo Application en Split APK : %%p
		for /l %%i in (1,1,!COUNT!) do (
			set "CUR_PATH=!APK_PATH%%i!"
			set "CUR_PATH=!CUR_PATH:~1!"
			adb pull "!CUR_PATH!" "%OUTPUT_DIR%\%%p_split%%i.apk" >nul
		)
		:: Regrouper les fichiers APK extraits en un seul fichier .apks
		echo Cr�ation du fichier .apks pour %%p...
		7z a "%OUTPUT_DIR%\%%p.apks" "%OUTPUT_DIR%\%%p_split*.apk" >nul
		echo Fichier .apks cr�� : %%p.apks
		del /Q "%OUTPUT_DIR%\%%p_split*.apk"
	)
	echo.
)

echo Extraction termin�e. Les fichiers sont enregistr�s dans "%OUTPUT_DIR%".
exit /b
