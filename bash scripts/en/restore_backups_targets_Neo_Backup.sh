# !/bin/bash

# Pallet APK Handler - Neo-Backup Backup

# Attention - Do not manage version checks
# Require root rights
# Requires 7zip with ZST decompression function

# Main directories
ROOT_DIR="$(pwd)"
TMP_DIR="$ROOT_DIR/tmp"
TMP_FILE="$ROOT_DIR/installed_packages.tmp"
LIST_FILE="$ROOT_DIR/packages_cibles.txt"

# Verification of ADB connection
if ! adb devices | grep -q "device$"; then
    echo "Error: No ADB device detected."
    exit 1
fi

# Checking the existence of the package_targets.txt file
if [ ! -f "$LIST_FILE" ]; then
    echo "\"target_packages.txt\": file not found"
    exit 1
fi

# Creation of the temporary directory
mkdir -p "$TMP_DIR"

# Recovery of the list of installed user applications
echo "Recovery of the list of installed user applications..."
adb shell pm list packages -3 > "$TMP_FILE"
echo

echo "Start of the Neo Backup restoration..."

# Buckle on package folders
while IFS= read -r PKG_PATH; do
    PKG_NAME=$(basename "$PKG_PATH")
    SAVE_DIR="$ROOT_DIR/$PKG_PATH"

    # Searching the backup subfolder
    for dir in "$SAVE_DIR"/*-user_0; do
        if [ -d "$dir" ]; then
            SAVE_DIR="$dir"
            echo "$PKG_NAME: Package Processing..."

            INSTALLED=0
            while IFS= read -r line; do
                PACKAGE_NAME=$(echo "$line" | cut -d':' -f2 | xargs)
                if [ "$PACKAGE_NAME" == "$PKG_NAME" ]; then
                    INSTALLED=1
                    echo "$PKG_NAME: Package already installed."
                fi
            done < "$TMP_FILE"

            if [ "$INSTALLED" -eq 0 ]; then
                echo "$PKG_NAME: Installation"
                # Extraction and installation of KPAs
                APK_LIST=()
                for apk in "$SAVE_DIR"/*.apk; do
                    APK_LIST+=("$apk")
                done
                if [ ${#APK_LIST[@]} -gt 0 ]; then
                    echo "Installation of $PKG_NAME ..."
                    adb install-multiple "${APK_LIST[@]}"
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
                    echo "$DATA_FILE Decompression..."
                    7z x "$DATA_FILE" -o"$TMP_DIR" -y > /dev/null
                    7z x "$TMP_DIR/data.tar" -o"$TMP_DIR" -y > /dev/null
                    rm "$TMP_DIR/data.tar"
                    echo "Transfer data to the device..."
                    adb push "$TMP_DIR/." /storage/emulated/0/neo_tmp/
                    adb shell su -c "mkdir -p /data/data/$PKG_NAME"
                    adb shell su -c "cp -r /storage/emulated/0/neo_tmp/. /data/data/$PKG_NAME"
                    adb shell su -c "rm -rf /storage/emulated/0/neo_tmp"
                    # Cleaning TMP_DIR
                    rm -rf "$TMP_DIR/*"
                fi

                # Processing external_files.tar.zst
                if [ -f "$DATA_FILE_EXT" ]; then
                    echo "$DATA_FILE_EXT Decompression..."
                    7z x "$DATA_FILE_EXT" -o"$TMP_DIR" -y > /dev/null
                    7z x "$TMP_DIR/external_files.tar" -o"$TMP_DIR" -y > /dev/null
                    rm "$TMP_DIR/external_files.tar"
                    echo "Transfer data to the device..."
                    adb push "$TMP_DIR/." /storage/emulated/0/neo_tmp/
                    adb shell su -c "mkdir -p /storage/emulated/0/Android/data/$PKG_NAME"
                    adb shell su -c "cp -r /storage/emulated/0/neo_tmp/. /storage/emulated/0/Android/data/$PKG_NAME"
                    adb shell su -c "rm -rf /storage/emulated/0/neo_tmp"
                    # Cleaning TMP_DIR
                    rm -rf "$TMP_DIR/*"
                fi
                echo "$PKG_NAME: End of restoration."
            fi
            echo
        fi
    done < "$LIST_FILE"
done

rm "$TMP_FILE"

echo "Restart Play Store..."
adb shell am force-stop com.android.vending > /dev/null
adb shell monkey -p com.android.vending -c android.intent.category.LAUNCHER 1 > /dev/null

echo
echo "Restores completed. "
exit 0