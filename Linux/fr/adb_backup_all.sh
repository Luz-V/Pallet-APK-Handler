#!/bin/bash

# Pallet APK Handler - DEPRECATED Data backup for android user-installed apps by adb backup

# WARNING - The 'adb backup' command is deprecated for most applications starting from Android 10

# Backs up the data of EVERY user application detected on the connected Android device.
# Creates a backup in the adb-backup-data folder
# Creates a list "packages_extracted.txt" of user packages installed on the connected Android device.

# Define folder and variable
AB_PATH="$(pwd)/adb-backup-data"
TMP_PATH="$(pwd)/tmp"
PKG_FILE="$TMP_PATH/packages_extracted.txt"

# Check ADB connection
ADB_CONNECTED=""
if adb devices | grep -q "device$"; then
    ADB_CONNECTED=1
else
    echo "Error: No ADB device detected."
    exit 1
fi

# Retrieve the list of installed user applications
echo "Retrieving the list of installed user applications..."
adb shell pm list packages -3 > "$PKG_FILE"

# Clean lines and assemble into a single line separated by spaces
PKG_LIST=""
while IFS= read -r line; do
    PKG_NAME=$(echo "$line" | cut -d':' -f2 | xargs)
    PKG_LIST="$PKG_LIST $PKG_NAME"
done < "$PKG_FILE"

# Create backup folder if it doesn't exist
mkdir -p "$AB_PATH"

# Start backup
echo "Starting backup..."
adb backup -f "$AB_PATH/backup.ab" -apk -obb -shared -nosystem $PKG_LIST
# "Simple" version
# adb backup -f "backup_all.ab" -all -apk -obb -shared

# Clean up and end
rm "$PKG_FILE"
echo
echo "Backups completed."