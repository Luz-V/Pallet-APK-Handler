# !/bin/bash

# Pallet APK Handler - Check package name for APK/APKS files.

# Indicates via aapt the package name of a given .apk or apks file
# Syntax: apk_check_package_name.sh $FILE_APK(S)

# Verification that the argument is provided
if [ -z "$1" ]; then
    echo "Error: No APK(S) file provided as argument."
    exit 1
fi

# Set input file
INPUT_FILE="$1"

# Check file exists
if [ ! -f "$INPUT_FILE" ]; then
    echo "Error: The file \"$INPUT_FILE\" does not exist."
    exit 1
fi

# Set the aapt executable path (to be adapted if necessary)
AAPT_CMD="/path/to/android-sdk/build-tools/36.0.0/aapt"  # Change this to your actual path

# Check that the extension is .apk or .apks
case "${INPUT_FILE,,}" in
    *.apk) 
        # Run aapt dump badging and extract the name of the package
        PACKAGE_NAME=$($AAPT_CMD dump badging "$INPUT_FILE" | grep -oP "(?<=package: name=')[^']*")
        ;;
    *.apks) 
        # Extract apk from a temporary folder
        mkdir -p tmp
        7z x "$INPUT_FILE" -o"$PWD/tmp" -y > /dev/null 2>&1

        # Run aapt dump badging and extract the name of the package
        for apk in tmp/*.apk; do
            if [ -f "$apk" ]; then
                PACKAGE_NAME=$($AAPT_CMD dump badging "$apk" | grep -oP "(?<=package: name=')[^']*")
                break  # Arrêt dès qu'un package_name est trouvé
            fi
        done
        # Removal of the temporary file
        rm -rf tmp
        ;;
    *) 
        echo "Error: This script only supports APK or APKS files."
        exit 1
        ;;
esac

# Show package name
if [ -n "$PACKAGE_NAME" ]; then
    echo "Package Name: $PACKAGE_NAME"
else
    echo "Error: Cannot find the name of the package."
fi

exit 0