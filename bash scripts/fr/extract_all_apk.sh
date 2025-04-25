#!/bin/bash

# Pallet APK Handler - Extracteur de packages au format APK/APKS

# Extrait TOUS les packages utilisateurs installés sur l'appareil android connecté sous forme de fichiers apk et apks. 
# Crée également un fichier "packages_extracted.txt" listant les packages utilisateurs détectés.

# Définition des répertoires
OUTPUT_DIR="$(pwd)/apks_extracted"
LIST_FILE_0="$OUTPUT_DIR/packages_tmp.txt"
LIST_FILE_1="$OUTPUT_DIR/packages_extracted.txt"

# Création du répertoire de destination
mkdir -p "$OUTPUT_DIR"

# Vérification de la connexion ADB
if ! adb devices | grep -q "device$"; then
    echo "Erreur : Aucun appareil ADB détecté."
    exit 1
fi

echo "Extraction de la liste des applications utilisateur..."
adb shell pm list packages -3 > "$LIST_FILE_0"
echo

# Nettoyage du format de sortie
awk -F':' '{print $2}' "$LIST_FILE_0" > "$LIST_FILE_1"
rm "$LIST_FILE_0"

echo "Extraction des fichiers APK ..."
echo

# Extraction des APK/APKS
while IFS= read -r package; do
    echo "Extraction de $package..."
    
    # Récupérer le chemin de(s) APK(s)
    APK_PATHS=($(adb shell pm path "$package" | awk -F':' '{print $2}'))
    COUNT=${#APK_PATHS[@]}
    
    # Cas d'un seul APK
    if [ "$COUNT" -eq 1 ]; then
        APK_PATH="${APK_PATHS[0]:1}"  # Remove leading ' '
        adb pull "$APK_PATH" "$OUTPUT_DIR/$package.apk" > /dev/null
    else
        echo "Application en Split APK : $package"
        for ((i=0; i<COUNT; i++)); do
            CUR_PATH="${APK_PATHS[i]:1}"  # Remove leading ' '
            adb pull "$CUR_PATH" "$OUTPUT_DIR/${package}_split$((i+1)).apk" > /dev/null
        done
        
        # Regrouper les fichiers APK extraits en un seul fichier .apks
        echo "Création du fichier .apks pour $package..."
        7z a "$OUTPUT_DIR/$package.apks" "$OUTPUT_DIR/${package}_split*.apk" > /dev/null
        echo "Fichier .apks créé : $package.apks"
        rm "$OUTPUT_DIR/${package}_split*.apk"
    fi
    echo
done < "$LIST_FILE_1"

echo "Extraction terminée. Les fichiers sont enregistrés dans \"$OUTPUT_DIR\"."
exit 0