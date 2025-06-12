# !/bin/bash

# Pallet APK Handler - Detector of installed user packages

# Creates a "installed_packages.txt" list of user packages installed on the connected android device.

# Definition of output file
LIST_FILE="$(pwd)/installed_packages.txt"

# Verification of ADB connection
ADB_CONNECTED=""
if adb devices | grep -q "device$"; then
    ADB_CONNECTED=1
else
    echo "Error: No ADB device detected."
    exit 1
fi

# Extracting user applications
echo "Extract from the list of user applications..."
adb shell pm list packages -3 > "$LIST_FILE"

# Cleaning the output format
# This will extract the package names and overwrite the original file
awk -F':' '{print $2}' "$LIST_FILE" | xargs > "$LIST_FILE"

echo "List of applications saved in \"$LIST_FILE\". "
