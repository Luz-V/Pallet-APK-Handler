:: Pallet APK Handler - Package name verifier for APK/APKS files.

:: Indicates via aapt the package name of a .apk file or apks given
:: Syntax: apk_check_package_name.bat $FILE_APK(S)

@echo off
chcp 1252 >nul
setlocal enabledelayedexpansion

REM Verification that the argument is provided
if "%~1"=="" (
    echo Error: No APK(S) file provided as argument.
    exit /b
)

REM Set Entry File
set "INPUT_FILE=%~1"

REM Check that the file exists
if not exist "%INPUT_FILE%" (
    echo Error: The file "%INPUT_FILE%" does not exist.
    exit /b
)

REM Defining the path of the aapt (to be adapted if necessary)
set "AAPT_CMD=D:\Android_SDK\build-tools\36.0.0\aapt"

REM Check that the extension is .apk or apks
if /I "%~x1"==".apk" goto apk_file
if /I "%~x1"==".apks" goto apks_file
echo Error: This script only supports APK or APKS files.
exit /b

:apk_file
REM Run aapt dump badging and extract the package name using ' as delimiter.
for /f "tokens=2 delims='" %%A in ('%AAPT_CMD% dump badging "%INPUT_FILE%" ^| findstr /C:"package: name="') do (
	set "PACKAGE_NAME=%%A"
)
goto correct_end

:apks_file
REM Extract apk from a temporary folder
mkdir tmp >nul 2>&1
7z x "%INPUT_FILE%" -o"%CD%\tmp" -y >nul 2>&1

REM Run aapt dump badging and extract the package name using ' as delimiter.
for /f "delims=" %%A in ('dir /b /a:-d "%CD%\tmp\*.apk" ^| sort') do (
	REM Stop when a_name package is found
	if not defined PKG_NAME (
		for /f "tokens=2 delims=='" %%P in ('%AAPT_CMD% dump badging "%CD%\tmp\%%A" ^| findstr /C:"package: name="') do (
			set "PACKAGE_NAME=%%P"
		)
	)
)
REM deletion of temporary folder
del /Q tmp\ 
goto correct_end

REM end
:correct_end
echo Package name: !PACKAGE_NAME!
endlocal
exit /b
