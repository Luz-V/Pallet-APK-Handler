# !/bin/bash

# Pallet APK Handler - AppManager type backup restore

# Attention - Do not manage version checks
# Require root rights
# Requires 7zip with ZST decompression function

# Restore backups in AppManager format (and reinstall the package if not installed)
# the backups made via AppManager are detected automatically in the tree
# REM - the "base.apk" installer (+ possible APK splits),
# - A metadata file "meta_v2.am.json" and configuration files "dataX.tar.gz", X starting from 0

# Definition of directories and files
APK_DIR="$(pwd)/apks"
TMP_DIR="$(pwd)/tmp"
# 7z Executable path (update if necessary)
SEVEN_ZIP="/usr/bin/7z"  # Change this to your actual path if needed

# Verification of ADB connection
if ! adb devices | grep -q "device$"; then
    echo "Error: No ADB device detected."
    exit 1
fi

# Creating the temporary folder if not existing
mkdir -p "$TMP_DIR"

echo
echo "Read backups ..."
echo

# Loop on folders
for APP_DIR in "$PWD"/*; do
    if [ -d "$APP_DIR" ]; then
        APP_DIR=$(realpath "$APP_DIR")
        DUMMY="$APP_DIR"
        # Exclusion of the "apks" folder, which is not a backup folder
        if [ "$APP_DIR" == "$APK_DIR" ]; then
            echo "Apks file detected"
            echo
        else
            echo "$APP_DIR file"
            # Processing the directory of an application
            META_FILE="$APP_DIR/0/meta_v2.am.json"
            if [ ! -f "$META_FILE" ]; then
                echo "Meta_v2.am.json file missing for $APP_DIR"
            else
                # Reading meta_v2.am.json file information
                APP_PKG=""
                IS_SPLIT_APK=false
                # Using grep to extract basic data
                APP_PKG=$(grep -oP '"package_name":\s*"\K[^"]+' "$META_FILE")
                IS_SPLIT_APK=$(grep -oP '"is_split_apk":\s*\K[^,]+' "$META_FILE")

                # Cleaning Names
                APP_PKG=$(echo "$APP_PKG" | tr -d '"')
                IS_SPLIT_APK=$(echo "$IS_SPLIT_APK" | tr -d '"')

                # Using grep to extract directory data
                DATA_DIRS=()
                IN_DATA_DIRS=0
                COUNT=-2

                while IFS= read -r LINE; do
                    if [[ $LINE == *"\"data_dirs\": ["* ]]; then
                        IN_DATA_DIRS=1
                    fi
                    if [[ $LINE == *"]"* && $IN_DATA_DIRS -eq 1 ]]; then
                        IN_DATA_DIRS=0
                    fi
                    if [ $IN_DATA_DIRS -eq 1 ]; then
                        COUNT=$((COUNT + 1))
                        LINE=$(echo "$LINE" | tr -d '[:space:]' | tr -d ',"')
                        DATA_DIRS+=("$LINE")
                    fi
                done < "$META_FILE"

                # Installation
                echo "Restore the $APP_PKG package: "
                echo

                SOURCE_FILE="$APP_DIR/0/source.tar.gz.0"
                # Decompression of .apk file by 7-zip
                "$SEVEN_ZIP" x "$SOURCE_FILE" -o"$TMP_DIR" -y > /dev/null 2>&1
                "$SEVEN_ZIP" x "$TMP_DIR/source.tar.gz" -o"$TMP_DIR" -y > /dev/null 2>&1
                rm "$TMP_DIR/source.tar.gz"

                # Check the list of extracted APK files
                APK_LIST=()
                for APK in "$TMP_DIR"/*.apk; do
                    APK_LIST+=("$APK")
                done

                if [ "$IS_SPLIT_APK" == "true" ]; then
                    # Multiple installation
                    echo "$APP_PKG: Installation in Split APK..."
                    adb install-multiple "${APK_LIST[@]}"
                else
                    # Simple installation
                    echo "$APP_PKG: Standard installation..."
                    adb install "${APK_LIST[0]}"
                fi

                # Cleaning the temporary directory
                rm -rf "$TMP_DIR/*"
                mkdir -p "$TMP_DIR"

                echo "$APP_PKG: Data transfer, ${#DATA_DIRS[@]} directories detected ..."

                for i in "${!DATA_DIRS[@]}"; do
                    DATA_DIR="${DATA_DIRS[$i]}"
                    # Decompression of data0.tar.gz.0
                    "$SEVEN_ZIP" x -o"$TMP_DIR" "$APP_DIR/0/data${i}.tar.gz.0" -y > /dev/null 2>&1
                    "$SEVEN_ZIP" x -o"$TMP_DIR" "$TMP_DIR/data${i}.tar.gz" -y > /dev/null 2>&1
                    rm "$TMP_DIR/data${i}.tar.gz"

                    if [ -d "$TMP_DIR" ] && [ "$(ls -A $TMP_DIR)" ]; then
                        # Send files to $TMP_DIR to /storage/emulated/0/
                        adb push "$TMP_DIR/" /storage/emulated/0/
                        # Creating the directory
                        adb shell su -c "mkdir -p /storage/emulated/0/${DATA_DIR}/"
                        # File transfer
                        adb shell su -c "cp -r /storage/emulated/0/tmp/. /storage/emulated/0/${DATA_DIR}/ && rm -rf /storage/emulated/0/tmp/*"
                        # Cleaning the temporary directory
                        rm -rf "$TMP_DIR/*"
                    else
                        echo "Error: Unable to decompress data${i}.tar.gz.0"
                    fi
					
                    echo "$APP_PKG: End of Transfer."
                done
                echo
            fi
        fi
    fi
done


echo "Restarting the Google Play service..."

adb shell am force-stop com.android.vending > /dev/null 2>&1
adb shell monkey -p com.android.vending -c android.intent.category.LAUNCHER 1 > /dev/null 2>&1
echo

echo "Restores completed. "
exit 0