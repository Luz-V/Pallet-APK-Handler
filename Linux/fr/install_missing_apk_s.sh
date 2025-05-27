#!/bin/bash

# Pallet APK Handler - Installateur d'APK/APKS automatisé

# Installe TOUS les fichiers apk et apks présents dans le répertoire ./apks 
# qui sont absents de l'appareil android connecté
# Attention : N'effectue pas les mises à jour

# Définition des répertoires et fichiers
APK_DIR="$(pwd)/apks"
TMP_DIR="$APK_DIR/tmp"

# Vérification ADB
if ! adb devices | grep -q "device$"; then
    echo "Erreur : Aucun appareil ADB détecté."
    exit 1
fi

# Récupération des packages déjà installés
echo "Lecture des packages installés..."
INSTALLED_LIST=()
while IFS= read -r line; do
    INSTALLED_LIST+=("$line")
done < <(adb shell pm list packages | cut -d':' -f2)

# Création du dossier temporaire si non existant
mkdir -p "$TMP_DIR"

echo
echo "Début de l'installation des packages ..."
echo

# Boucle sur les fichiers APK+APKS
for APK_FILE in "$APK_DIR"/*; do
    FILE_NAME=$(basename "$APK_FILE")
    PKG_NAME=""

    # Lecture de .apk
    if [[ "$APK_FILE" == *.apk ]]; then
        # Extraction du package name via aapt
        PKG_NAME=$(/path/to/android-sdk/build-tools/36.0.0/aapt dump badging "$APK_FILE" | grep -oP "(?<=package: name=')[^']+")
    fi

    # Lecture de .apks
    if [[ "$APK_FILE" == *.apks ]]; then
        # Première extraction via 7z
        7z x "$APK_FILE" -o"$TMP_DIR" -y > /dev/null 2>&1
        for EXTRACTED_APK in "$TMP_DIR"/*.apk; do
            if [ -z "$PKG_NAME" ]; then
                # Extraction du package name via aapt
                PKG_NAME=$(/path/to/android-sdk/build-tools/36.0.0/aapt dump badging "$EXTRACTED_APK" | grep -oP "(?<=package: name=')[^']+")
            fi
        done
    fi

    echo "$FILE_NAME - Package détecté : $PKG_NAME"

    # Vérification si le package est à installer
    INSTALL=0
    if [ -n "$PKG_NAME" ]; then
        IS_INSTALLED=0
        # Recherche du package dans la liste des packages installés
        for INSTALLED_PKG in "${INSTALLED_LIST[@]}"; do
            if [ "$PKG_NAME" == "$INSTALLED_PKG" ]; then
                IS_INSTALLED=1
                break
            fi
        done

        if [ "$IS_INSTALLED" -eq 0 ]; then
            # Cas 1 => package non installé
            INSTALL=1
        else
            # Cas 2 => package déjà installé
            echo "$PKG_NAME déjà installé."
        fi
    fi

    # Installation
    if [ "$INSTALL" -eq 1 ]; then
        # Cas APK Simple
        if [[ "$APK_FILE" == *.apk ]]; then
            echo "$FILE_NAME - Installation..."
            adb install "$APK_FILE"
        fi
        # Cas APKS
        if [[ "$APK_FILE" == *.apks ]]; then
            APK_LIST=()
            for EXTRACTED_APK in "$TMP_DIR"/*.apk; do
                APK_LIST+=("$EXTRACTED_APK")
            done
            echo "$FILE_NAME - Installation multiple..."
            adb install-multiple "${APK_LIST[@]}"
        fi
    fi

    # Nettoyage du répertoire temporaire
    rm -rf "$TMP_DIR/*"
    echo
done

echo "Fin des installations."
exit 0