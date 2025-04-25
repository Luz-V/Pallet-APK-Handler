@echo off
chcp 1252 >nul
setlocal enabledelayedexpansion

:: R�pertoires principaux
set "ROOT_DIR=%CD%"
set "TMP_DIR=%ROOT_DIR%\tmp"
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

:: Cr�ation du r�pertoire temporaire
if not exist "%TMP_DIR%" mkdir "%TMP_DIR%"

:: R�cup�ration de la liste des applications utilisateur install�es
echo R�cup�ration de la liste des applications utilisateur install�es...
adb shell pm list packages -3 > "%TMP_FILE%"
echo.

echo.
echo D�but de la restauration Neo Backup...
echo.

:: Boucle sur les dossiers de package
for /d %%P in ("%ROOT_DIR%\*") do (
    set "PKG_NAME=%%~nxP"
    set "PKG_PATH=%%~fP"

    :: Recherche du sous-dossier de sauvegarde
    for /d %%S in ("!PKG_PATH!\*-user_0") do (
        set "SAVE_DIR=%%~fS"
        set "SAVE_NAME=%%~nxS"

        echo !PKG_NAME! : Traitement du package ...
        REM echo Dossier de sauvegarde : !SAVE_NAME!
        
		set "INSTALLED=0"
		for /f "tokens=2 delims=:" %%I in ('type "!TMP_FILE!"') do (
			if "%%I"=="!PKG_NAME!" (
				set "INSTALLED=1"
				echo !PKG_NAME! : Package d�j� install�.
			)
		)
		if !INSTALLED! == 0 (
			echo !PKG_NAME! : Installation
			:: Extraction et installation des APK
			set "APK_LIST="
			for %%A in ("!SAVE_DIR!\*.apk") do (
				set "APK_LIST=!APK_LIST! "%%~fA""
			)
			if defined APK_LIST (
				echo Installation de !PKG_NAME! ...
				REM echo APK d�tect�s : !APK_LIST!
				adb install-multiple !APK_LIST!
				set "INSTALLED=1"
			) else (
				echo Aucun APK trouv� pour !PKG_NAME! - Ignor�.
			)
		)

		if !INSTALLED! == 1 (
			:: Restauration des donn�es
			echo !PKG_NAME! : Recherche de sauvegardes �ventuelles ...
			set "DATA_FILE=!SAVE_DIR!\data.tar.zst"
			set "DATA_FILE_EXT=!SAVE_DIR!\external_files.tar.zst"

			:: Traitement de data.tar.zst
			if exist "!SAVE_DIR!\data.tar.zst" (
				REM echo D�compression de !DATA_FILE! ...
				7z x "!DATA_FILE!" -o"!TMP_DIR!" -y >nul
				7z x "!TMP_DIR!\data.tar" -o"!TMP_DIR!" -y >nul
				del "!TMP_DIR!\data.tar"
				REM echo Transfert des donn�es vers l�appareil...
				adb push "!TMP_DIR!\." /storage/emulated/0/neo_tmp/
				REM L�utilisateur est root, et on place tout dans /data/data/<pkg>
				REM D�placement final dans /data/data/!PKG_NAME!/ ...
				adb shell su -c "mkdir -p /data/data/!PKG_NAME!"
				adb shell su -c "cp -r /storage/emulated/0/neo_tmp/. /data/data/!PKG_NAME!"
				adb shell su -c "rm -rf /storage/emulated/0/neo_tmp"
				:: Nettoyage du TMP_DIR
				rmdir /s /q "!TMP_DIR!"
				mkdir "!TMP_DIR!"
			) else (
				REM !PKG_NAME! : Fichier data.tar.zst introuvable, ou application non install�e
			)

			:: Traitement de external_files.tar.zst
			if exist "!SAVE_DIR!\external_files.tar.zst" (
				REM echo D�compression de !DATA_FILE_EXT! ...
				7z x "!DATA_FILE_EXT!" -o"!TMP_DIR!" -y >nul
				7z x "!TMP_DIR!\external_files.tar" -o"!TMP_DIR!" -y >nul
				del "!TMP_DIR!\external_files.tar"

				REM echo Transfert des donn�es vers l�appareil...
				adb push "!TMP_DIR!\." /storage/emulated/0/neo_tmp/
				REM L�utilisateur est root, et on place tout dans /storage/emulated/0/Android/data/<pkg>
				REM D�placement final dans /storage/emulated/0/Android/data/!PKG_NAME!/ ...
				adb shell su -c "mkdir -p /storage/emulated/0/Android/data/!PKG_NAME!"
				adb shell su -c "cp -r /storage/emulated/0/neo_tmp/. /storage/emulated/0/Android/data/!PKG_NAME!"
				adb shell su -c "rm -rf /storage/emulated/0/neo_tmp"
				:: Nettoyage du TMP_DIR
				rmdir /s /q "!TMP_DIR!"
				mkdir "!TMP_DIR!"
			) else (
				REM !PKG_NAME! : Fichier external_files.tar.zst introuvable, ou application non install�e
			)
			echo !PKG_NAME! : Fin de la restauration.
		)
	echo.
	)
)
del !TMP_FILE!

echo Red�marrage du Play Store...
adb shell am force-stop com.android.vending >nul
adb shell monkey -p com.android.vending -c android.intent.category.LAUNCHER 1 >nul

echo.
echo Restaurations termin�es.
exit /b
