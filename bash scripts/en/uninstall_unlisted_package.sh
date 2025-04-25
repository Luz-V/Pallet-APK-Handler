# !/bin/bash

# Pallet APK Handler - Automated User Package Uninstaller

# Uninstall ALL user packages that are NOT listed in the "packages.txt" file.
# If the file "packages_utiles.txt" is not detected, the script is interrupted
# If the file "packages_utiles.txt" is empty, all user packages will be uninstalled

# Definition of files and folders
LIST_FILE="$(pwd)/packages_usefull.txt"
TMP_FILE="$(pwd)/installed_packages.tmp"

# Verification of ADB connection
if ! adb devices | grep -q "device$"; then
    echo "Error: No ADB device detected."
    exit 1
fi

# Checking the existence of the package_usefull.txt file
if [ ! -f "$LIST_FILE" ]; then
    echo "\"packages_usefull.txt\": file not found"
    exit 1
fi

echo "Read the list of applications to keep..."
PKG_LIST_KEEP=()
while IFS= read -r line; do
    PKG_LIST_KEEP+=("$line")
done < "$LIST_FILE"
echo

# Recovery of the list of installed user applications
echo "Recovery of the list of installed user applications..."
adb shell pm list packages -3 > "$TMP_FILE"
echo

# Comparison and removal of unnecessary applications
echo "Deleting unnecessary applications..."
while IFS= read -r line; do
    PACKAGE_NAME=$(echo "$line" | cut -d':' -f2 | xargs)  # Clean the package name
    FOUND=0
    for pkg in "${PKG_LIST_KEEP[@]}"; do
        if [ "$PACKAGE_NAME" == "$pkg" ]; then
            FOUND=1
            break
        fi
    done
    if [ "$FOUND" -eq 0 ]; then
        echo "Deletion of $PACKAGE_NAME..."
        adb uninstall "$PACKAGE_NAME"
    fi
done < "$TMP_FILE"
echo

# Cleaning
rm "$TMP_FILE"
echo "Disinstallations completed. "
exit 0