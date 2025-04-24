REM Pallet APK Handler - Restauration de sauvegarde de type Neo-Backup

REM Attention - Ne g�re pas les v�rifications de version
REM N�cessite les droits root
REM N�cessite 7zip avec la fonction de d�compression ZST

REM Restaure les sauvegardes au format Neo-Backup (et r�installe le package s'il n'est pas install�)
REM les sauvegardes faites via Neo-Backup sont d�tect�s automatiquement dans l'arborescence
REM Ces sauvegardes incluent :
REM - L'installateur "base.apk" (+ �ventuels APK splits), 
REM - Un fichier de m�tadonn�s [DATE].properties et des fichiers de configurations "data.tar.zst" et "external_files.tar.zst" 

@echo off
chcp 1252 >nul
setlocal enabledelayedexpansion

:: D�finition des r�pertoires et fichiers
set "APK_DIR=%CD%\apks"
set "TMP_DIR=%CD%\tmp"
:: set "7z.exe=C:\Program Files\7-Zip\7z.exe"

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

:: Cr�ation du dossier temporaire si non existant
if not exist "%TMP_DIR%" mkdir "%TMP_DIR%"

echo.
echo Lecture des sauvegardes ...
echo.

:: Boucle sur les dossiers
for /d %%A in ("%CD%\*") do (
	set "APP_DIR=%%~fA"
	set "DUMMY=!APP_DIR!"
	:: Exclusion du dossier "apks", qui n'est pas un dossier de sauvegarde
	if "!APP_DIR!"=="!APK_DIR!" (
		echo Dossier apks d�tect�
		echo.
	) else (
		echo Dossier !APP_DIR!
		:: Traitement du r�pertoire d'une application
		set "META_FILE=!APP_DIR!\0\meta_v2.am.json"
		if not exist "!META_FILE!" (
			echo Fichier meta_v2.am.json manquant pour !APP_DIR!
		) else (
			:: Lecture des informations du fichier meta_v2.am.json (� am�liorer)
			set "APP_PKG="
			set "IS_SPLIT_APK=false"
			:: Utilisation de findstr pour extraire les donn�es de base
			for /f "tokens=1,* delims=:" %%B in ('findstr "package_name" "!META_FILE!"') do (
				set "APP_PKG=%%C"
			)
			for /f "tokens=1,* delims=:" %%B in ('findstr "is_split_apk" "!META_FILE!"') do (
				set "IS_SPLIT_APK=%%C"
			)
			:: Nettoyage des noms en supprimant guillemets, espaces en d�but et dernier caract�re
			for %%V in (APP_PKG IS_SPLIT_APK) do (
				set "%%V=!%%V:"=!"  :: Enl�ve les guillemets
				set "%%V=!%%V:~1!"  :: Enl�ve l'espace au d�but
				set "%%V=!%%V:~0,-1!"  :: Enl�ve le dernier caract�re (virgule ou guillemet)
			)

			:: Utilisation de findstr pour extraire les donn�es de r�pertoires
			set "DATA_DIRS="
			set "IN_DATA_DIRS=0"
			set "COUNT=-2"
			
			for /f "usebackq delims=" %%A in ("!META_FILE!") do (
				set "LINE=%%A"
				:: V�rifier si on trouve la cha�ne de caract�res "data_dirs": [
				echo !LINE! | findstr /C:"\"data_dirs\": [" >nul && set "IN_DATA_DIRS=1"
				:: Si on est dans data_dirs et qu'on rencontre ']', on arr�te
				if !IN_DATA_DIRS! == 1 (
					echo !LINE! | findstr /C:"]" >nul && set "IN_DATA_DIRS=0"
					:: Nettoyage de la ligne et stockage dans une variable num�rot�e
					set /a COUNT+=1
					set "LINE=!LINE:\/=/!"
					set "LINE=!LINE:    =!"
					set "LINE=!LINE: =!"
					set "LINE=!LINE:"=!"
					set "LINE=!LINE:,=!"
					set "DATA_DIR_!COUNT!=!LINE!"
				)
			)

			:: Installation
			echo Restauration du package !APP_PKG! : 
			echo.
			
			set "SOURCE_FILE=!APP_DIR!\0\source.tar.gz.0"
			:: D�compression du/des fichier .apk par 7-zip
			7z.exe x "!SOURCE_FILE!" -o"!TMP_DIR!" -y >nul 2>&1
			7z.exe x "!TMP_DIR!\source.tar.gz" -o"!TMP_DIR!" -y >nul 2>&1
			del "!TMP_DIR!\source.tar.gz"
			pause
			:: V�rification de la liste des fichiers APK extraits
			set "APK_LIST="
			for %%F in ("!TMP_DIR!\*.apk") do (
				set "APK_LIST=!APK_LIST! "%%F""
			)
			if "!IS_SPLIT_APK!"=="true" (
				:: Installation multiple
				echo !APP_PKG! : Installation en mode Split APK...
				adb install-multiple !APK_LIST!
			) else (
				:: Installation simple
				echo !APP_PKG! : Installation standard...
				adb install "!APK_LIST!"
			)
			
			:: Nettoyage du repertoire temporaire
			del "!TMP_DIR!\*" /Q
			:: Double nettoyage ?
			rmdir /s "!TMP_DIR!" /Q
			mkdir "!TMP_DIR!"
			
			echo !APP_PKG! : Transfert des donnees, !COUNT! repertoires d�tect�s ...
			
			set /a LAST_INDEX=!COUNT!-1			
			for /L %%I in (0,1,!LAST_INDEX!) do (
				:: echo D�compression de data0.tar.gz.%%I
				7z.exe x -o"!TMP_DIR!" "!APP_DIR!\0\data%%I.tar.gz.0" -y >nul 2>&1
				7z.exe x -o"!TMP_DIR!" "!TMP_DIR!\data%%I.tar.gz" -y >nul 2>&1
				:: echo Suppression des fichiers compress�s
				del "!TMP_DIR!\data%%I.tar.gz" /Q
				pause
				if exist "!TMP_DIR!\*" (			
					:: echo Envoi des fichiers dans !TMP_DIR! vers /storage/emulated/0/
					adb push "!TMP_DIR!" /storage/emulated/0/
					:: echo cr�ation du r�pertoire !DATA_DIR_%%I!
					adb shell su -c "mkdir !DATA_DIR_%%I!/"
					:: echo Transfert des fichiers de /storage/emulated/0/ vers  !DATA_DIR_%%I! puis nettoyage de /storage/emulated/0/
					adb shell su -c "cp -r /storage/emulated/0/tmp/. '!DATA_DIR_%%I!/' && rm -rf /storage/emulated/0/tmp/*"
					:: echo Nettoyage du r�pertoire temporaire
					rmdir /s "!TMP_DIR!" /Q
					mkdir "!TMP_DIR!"
				) else (
					echo Erreur : Impossible de d�compresser data0.tar.gz.%%I
				)
				echo !APP_PKG! : Fin du transfert. 
			)
			echo.
		)
	)
)

echo red�marrage du service google play...
adb shell am force-stop com.android.vending >nul 2>&1
adb shell monkey -p com.android.vending -c android.intent.category.LAUNCHER 1 >nul 2>&1
echo.

echo Restaurations termin�es.
exit /b