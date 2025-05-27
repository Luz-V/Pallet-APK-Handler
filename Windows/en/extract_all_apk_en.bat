REM Pallet APK Handler - Extractor of packages in APK/APKS format

REM Extract ALL user packages installed on the android device connected as apk and apks files.
REM Also creates a file "packages_extracted.txt" listing detected user packages.

@echo off
chcp 1252 >nul
setlocal enabledelayedexpansion

:: Definition of directories
set "OUTPUT_DIR=%CD%\apks_extracted"
set "LIST_FILE_0=%OUTPUT_DIR%\packages_tmp.txt"
set "LIST_FILE_1=%OUTPUT_DIR%\packages_extracted.txt"

:: Creating destination directory
if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"

:: Verification of ADB connection
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

echo Extracting the list of user applications...
adb shell pm list packages -3 > "%LIST_FILE_0%"
echo.

:: Cleaning the output format
(for /f "tokens=2 delims=:" %%p in ('type "%LIST_FILE_0%"') do echo %%p) > "%LIST_FILE_1%"
del "%LIST_FILE_0%"

echo Extracting APK files ...
echo.
:: Extraction of APK/APKS
for /f "usebackq delims=" %%p in ("%LIST_FILE_1%") do (
    echo Extraction of %%p...
	:: Recover path of APK(s)
	set "COUNT=0"
	for /f "tokens=2 delims=:" %%a in ('adb shell pm path "%%p"') do (
		set /a COUNT+=1
		set "APK_PATH!COUNT!=%%a"
	)
	
	:: Single APK case
	if !COUNT! equ 1 (
		set "APK_PATH=!APK_PATH1:~1!"
		adb pull "!APK_PATH!" "%OUTPUT_DIR%\%%p.apk" >nul
	) else (
		echo Split APK application: %%p
		for /l %%i in (1,1,!COUNT!) do (
			set "CUR_PATH=!APK_PATH%%i!"
			set "CUR_PATH=!CUR_PATH:~1!"
			adb pull "!CUR_PATH!" "%OUTPUT_DIR%\%%p_split%%i.apk" >nul
		)
		:: Group the extracted APK files into a single .apks file
		echo Creating .apks file for %%p...
		7z a "%OUTPUT_DIR%\%%p.apks" "%OUTPUT_DIR%\%%p_split*.apk" >nul
		echo .apks file created: %%p.apks
		del /Q "%OUTPUT_DIR%\%%p_split*.apk"
	)
	echo.
)

echo Extraction completed. Files are saved in "%OUTPUT_DIR%".
exit /b
