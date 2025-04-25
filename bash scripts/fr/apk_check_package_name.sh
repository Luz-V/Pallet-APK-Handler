#!/bin/bash

# Pallet APK Handler - Vérificateur de nom de package pour fichiers APK/APKS.

# Indique via aapt le nom de package d'un fichier .apk ou apks donné
# Syntaxe : apk_check_package_name.sh $FICHIER_APK(S)

# Vérification que l'argument est fourni
if [ -z "$1" ]; then
    echo "Erreur : Aucun fichier APK(S) fourni en argument."
    exit 1
fi

# Définir le fichier d'entrée
INPUT_FILE="$1"

# Vérifier que le fichier existe
if [ ! -f "$INPUT_FILE" ]; then
    echo "Erreur : Le fichier \"$INPUT_FILE\" n'existe pas."
    exit 1
fi

# Définir le chemin de l'exécutable aapt (à adapter si nécessaire)
AAPT_CMD="/path/to/android-sdk/build-tools/36.0.0/aapt"  # Change this to your actual path

# Vérifier que l'extension est .apk ou .apks
case "${INPUT_FILE,,}" in
    *.apk) 
        # Exécuter aapt dump badging et extraire le nom du package
        PACKAGE_NAME=$($AAPT_CMD dump badging "$INPUT_FILE" | grep -oP "(?<=package: name=')[^']*")
        ;;
    *.apks) 
        # Extraction des apk dans un dossier temporaire
        mkdir -p tmp
        7z x "$INPUT_FILE" -o"$PWD/tmp" -y > /dev/null 2>&1

        # Exécuter aapt dump badging et extraire le nom du package
        for apk in tmp/*.apk; do
            if [ -f "$apk" ]; then
                PACKAGE_NAME=$($AAPT_CMD dump badging "$apk" | grep -oP "(?<=package: name=')[^']*")
                break  # Arrêt dès qu'un package_name est trouvé
            fi
        done
        # Suppression du dossier temporaire
        rm -rf tmp
        ;;
    *) 
        echo "Erreur : Ce script supporte uniquement les fichiers APK ou APKS."
        exit 1
        ;;
esac

# Afficher le nom du package
if [ -n "$PACKAGE_NAME" ]; then
    echo "Nom du package : $PACKAGE_NAME"
else
    echo "Erreur : Impossible de trouver le nom du package."
fi

exit 0