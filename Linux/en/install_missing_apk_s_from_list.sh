# !/bin/bash

# Pallet APK Handler - Automated APK/APKS installer via txt list

# Install the apk and apks files in the ./apks directory that are:
# - Listed in the file "packages_to_install.txt"
# - Absent from connected android device

# Warning: Do not update

# Definition of directories and files
APK_DIR="$(pwd)/apks"
TMP_DIR="$APK_DIR/tmp"
LIST_FILE="$(pwd)/packages_to_install.txt"
# Path to aapt (update if necessary)
AAPT_PATH="/path/to/android-sdk/build-tools/36.0.0/aapt"  # Change this to your actual path

# ADB verification
if ! adb devices | grep -q "device$"; then
    echo "Error: No ADB device detected."
    exit 1
fi

# Check the file list of packages to install
if [ ! -f "$LIST_FILE" ]; then
    echo "\"packages_to_install.txt\" not found. "
    exit 1
fi

# Reading the list of packages to install
echo "Reading packages to allow..."
PKG_LIST=()
while IFS= read -r line; do
    PKG_LIST+=("$line")
done < "$LIST_FILE"

# Recovery of already installed packages
echo "Reading installed packages..."
INSTALLED_LIST=()
while IFS= read -r line; do
    INSTALLED_LIST+=("$line")
done < <(adb shell pm list packages | cut -d':' -f2)

# Creating the temporary folder if not existing
mkdir -p "$TMP_DIR"

echo
echo "Start of the conditional installation of the packages..."
echo

# Loop on APK+APKS files
for APK_FILE in "$APK_DIR"/*; do
    FILE_NAME=$(basename "$APK_FILE")
    PKG_NAME=""

    # Reading .apk
    if [[ "$APK_FILE" == *.apk ]]; then
        # Extracting the name package via aapt
        PKG_NAME=$($AAPT_PATH dump badging "$APK_FILE" | grep -oP "(?<=package: name=')[^']+")
    fi

    # Reading .apks
    if [[ "$APK_FILE" == *.apks ]]; then
        # First extraction via 7z
        7z x "$APK_FILE" -o"$TMP_DIR" -y > /dev/null 2>&1
        for EXTRACTED_APK in "$TMP_DIR"/*.apk; do
            if [ -z "$PKG_NAME" ]; then
                # Extracting the name package via aapt
                PKG_NAME=$($AAPT_PATH dump badging "$EXTRACTED_APK" | grep -oP "(?<=package: name=')[^']+")
            fi
        done
    fi

    echo "$FILE_NAME - Package detected: $PKG_NAME"

    # Check if package is to be installed
    INSTALL=0
    if [ -n "$PKG_NAME" ]; then
        IS_INSTALLED=0
        # Search the package in the list of installed packages
        for INSTALLED_PKG in "${INSTALLED_LIST[@]}"; do
            if [ "$PKG_NAME" == "$INSTALLED_PKG" ]; then
                IS_INSTALLED=1
                break
            fi
        done

        if [ "$IS_INSTALLED" -eq 0 ]; then
            # Case 1 => package not installed
            FOUND=0
            for PKG in "${PKG_LIST[@]}"; do
                if [ "$PKG_NAME" == "$PKG" ]; then
                    FOUND=1
                    break
                fi
            done
            if [ "$FOUND" -eq 1 ]; then
                # Case 1.a => package not installed and listed to be installed
                INSTALL=1
            else
                # Case 1.b => package not installed and not listed
                echo "$PKG_NAME not listed - ignored."
            fi
        else
            # Case 2 => already installed package
            echo "$PKG_NAME already installed."
        fi
    fi

    # Installation
    if [ "$INSTALL" -eq 1 ]; then
        # Case APK Simple
        if [[ "$APK_FILE" == *.apk ]]; then
            echo "$FILE_NAME - Installation..."
            adb install "$APK_FILE"
        fi
        # APKS cases
        if [[ "$APK_FILE" == *.apks ]]; then
            APK_LIST=()
            for EXTRACTED_APK in "$TMP_DIR"/*.apk; do
                APK_LIST+=("$EXTRACTED_APK")
            done
            echo "$FILE_NAME - Multiple installation..."
            adb install-multiple "${APK_LIST[@]}"
        fi
    fi

    # Cleaning the temporary directory
    rm -rf "$TMP_DIR/*"
    echo
done

echo "End of installations."
exit 0