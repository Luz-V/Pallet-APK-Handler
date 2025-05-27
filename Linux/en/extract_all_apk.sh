# !/bin/bash

# Pallet APK Handler - Extractor of packages in APK/APKS format

# Extract ALL user packages installed on the android device connected as apk and apks files.
# Also creates a file "packages_extracted.txt" listing detected user packages.

# Definition of directories
OUTPUT_DIR="$(pwd)/apks_extracted"
LIST_FILE_0="$OUTPUT_DIR/packages_tmp.txt"
LIST_FILE_1="$OUTPUT_DIR/packages_extracted.txt"

# Creating destination directory
mkdir -p "$OUTPUT_DIR"

# Verification of ADB connection
if ! adb devices | grep -q "device$"; then
    echo "Error: No ADB device detected."
    exit 1
fi

echo "Extract from the list of user applications..."
adb shell pm list packages -3 > "$LIST_FILE_0"
echo

# Cleaning the output format
awk -F':' '{print $2}' "$LIST_FILE_0" > "$LIST_FILE_1"
rm "$LIST_FILE_0"

echo "Extraction of APK files..."
echo

# Extraction of APK/APKS
while IFS= read -r package; do
    echo "Extraction of $package..."
    
    # Recover path of APK(s)
    APK_PATHS=($(adb shell pm path "$package" | awk -F':' '{print $2}'))
    COUNT=${#APK_PATHS[@]}
    
    # Single APK case
    if [ "$COUNT" -eq 1 ]; then
        APK_PATH="${APK_PATHS[0]:1}"  # Remove leading ' '
        adb pull "$APK_PATH" "$OUTPUT_DIR/$package.apk" > /dev/null
    else
        echo "Application in Split APK: $package"
        for ((i=0; i<COUNT; i++)); do
            CUR_PATH="${APK_PATHS[i]:1}"  # Remove leading ' '
            adb pull "$CUR_PATH" "$OUTPUT_DIR/${package}_split$((i+1)).apk" > /dev/null
        done
        
        # Group the extracted APK files into a single .apks file
        echo "Creating the .apks file for $package..."
        7z a "$OUTPUT_DIR/$package.apks" "$OUTPUT_DIR/${package}_split*.apk" > /dev/null
        echo "File .apks created: $package.apks"
        rm "$OUTPUT_DIR/${package}_split*.apk"
    fi
    echo
done < "$LIST_FILE_1"

echo "Extraction completed. Files are saved in \"$OUTPUT_DIR\". "
exit 0