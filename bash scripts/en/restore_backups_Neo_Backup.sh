# !/bin/bash
set -e

# Main directories
ROOT_DIR="$(pwd)"
TMP_DIR="$ROOT_DIR/tmp"
TMP_FILE="$ROOT_DIR/installed_packages.tmp"

# Verification of ADB connection
ADB_CONNECTED=""
if adb devices | awk 'NR>1 {print $1}' | grep -q .; then
    ADB_CONNECTED=1
fi

if [ -z "$ADB_CONNECTED" ]; then
    echo "Error: No ADB device detected."
    exit 1
fi

# Creation of the temporary directory
mkdir -p "$TMP_DIR"

# Recovery of the list of installed user applications
echo "Recovery of the list of installed user applications..."
adb shell pm list packages -3 > "$TMP_FILE"
echo

echo
echo "Start of the Neo Backup restoration..."
echo

# Buckle on package folders
for PKG_PATH in "$ROOT_DIR"/*; do
    if [ -d "$PKG_PATH" ]; then
        PKG_NAME="$(basename "$PKG_PATH")"

        # Searching the backup subfolder
        for SAVE_DIR in "$PKG_PATH"/*-user_0; do
            if [ -d "$SAVE_DIR" ]; then
                SAVE_NAME="$(basename "$SAVE_DIR")"

                echo "$PKG_NAME: Package Processing..."
                # echo "Backup file: $SAVE_NAME"
                
                INSTALLED=0
                while IFS= read -r line; do
                    if [[ "$line" == *"$PKG_NAME"* ]]; then
                        INSTALLED=1
                        echo "$PKG_NAME: Package already installed."
                    fi
                done < "$TMP_FILE"

                if [ "$INSTALLED" -eq 0 ]; then
                    echo "$PKG_NAME: Installation"
                    # Extraction and installation of KPAs
                    APK_LIST=""
                    for APK in "$SAVE_DIR"/*.apk; do
                        if [ -f "$APK" ]; then
                            APK_LIST="$APK_LIST \"$APK\""
                        fi
                    done

                    if [ -n "$APK_LIST" ]; then
                        echo "Installation of $PKG_NAME ..."
                        # echo "APK detected: $APK_LIST"
                        adb install-multiple $APK_LIST
                        INSTALLED=1
                    else
                        echo "No APK found for $PKG_NAME - Ignored."
                    fi
                fi

                if [ "$INSTALLED" -eq 1 ]; then
                    # Data restoration
                    echo "$PKG_NAME: Search for possible backups ..."
                    DATA_FILE="$SAVE_DIR/data.tar.zst"
                    DATA_FILE_EXT="$SAVE_DIR/external_files.tar.zst"

                    # Data.tar.zst processing
                    if [ -f "$DATA_FILE" ]; then
                        # echo "$DATA_FILE Decompression..."
                        7z x "$DATA_FILE" -o"$TMP_DIR" -y > /dev/null
                        7z x "$TMP_DIR/data.tar" -o"$TMP_DIR" -y > /dev/null
                        rm "$TMP_DIR/data.tar"
                        # echo "Transfer data to device..."
                        adb push "$TMP_DIR/." /storage/emulated/0/neo_tmp/
                        # The user is root, and everything is placed in /data/data/<pkg>
                        # Final move to /data/data/$PKG_NAME/ ...
                        adb shell su -c "mkdir -p /data/data/$PKG_NAME"
                        adb shell su -c "cp -r /storage/emulated/0/neo_tmp/. /data/data/$PKG_NAME"
                        adb shell su -c "rm -rf /storage/emulated/0/neo_tmp"
                        # Cleaning TMP_DIR
                        rm -rf "$TMP_DIR/*"
                        mkdir -p "$TMP_DIR"
                    else
                        # $PKG_NAME: Data.tar.zst file not found, or application not installed
                        echo "$PKG_NAME: Data.tar.zst file not found, or application not installed"
                    fi

                    # Processing external_files.tar.zst
                    if [ -f "$DATA_FILE_EXT" ]; then
                        # echo "$DATA_FILE_EXT ..."
                        7z x "$DATA_FILE_EXT" -o"$TMP_DIR" -y > /dev/null
                        7z x "$TMP_DIR/external_files.tar" -o"$TMP_DIR" -y > /dev/null
                        rm "$TMP_DIR/external_files.tar"

                        # echo "Transfer data to device..."
                        adb push "$TMP_DIR/." /storage/emulated/0/neo_tmp/
                        # The user is root, and everything is placed in /storage/emulated/0/Android/data/<pkg>
                        # Final move in /storage/emulated/0/Android/data/$PKG_NAME/ ...
                        adb shell su -c "mkdir -p /storage/emulated/0/Android/data/$PKG_NAME"
                        adb shell su -c "cp -r /storage/emulated/0/neo_tmp/. /storage/emulated/0/Android/data/$PKG_NAME"
                        adb shell su -c "rm -rf /storage/emulated/0/neo_tmp"
                        # Cleaning TMP_DIR
                        rm -rf "$TMP_DIR/*"
                        mkdir -p "$TMP_DIR"
                    else
                        # $PKG_NAME : External_files.tar.zst file not found, or application not installed
                        echo "$PKG_NAME: External_files.tar.zst file not found, or application not installed"
                    fi
                    echo "$PKG_NAME: End of restoration."
                fi
                echo
            fi
        done
    fi
done
rm -f "$TMP_FILE"

echo "Restart Play Store..."
adb shell am force-stop com.android.vending > /dev/null
adb shell monkey -p com.android.vending -c android.intent.category.LAUNCHER 1 > /dev/null

echo
echo "Restores completed. "
