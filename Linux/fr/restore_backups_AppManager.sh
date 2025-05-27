#!/bin/bash

# Pallet APK Handler - Restauration de sauvegarde de type AppManager

# Attention - Ne gère pas les vérifications de version
# Nécessite les droits root
# Nécessite 7zip avec la fonction de décompression ZST

# Restaure les sauvegardes au format AppManager (et réinstalle le package s'il n'est pas installé)
# les sauvegardes faites via AppManager sont détectés automatiquement dans l'arborescence
#REM - L'installateur "base.apk" (+ éventuels APK splits), 
# - Un fichier de métadonnés "meta_v2.am.json" et des fichiers de configurations "dataX.tar.gz", X partant de 0

# Définition des répertoires et fichiers
APK_DIR="$(pwd)/apks"
TMP_DIR="$(pwd)/tmp"
# 7z executable path (update if necessary)
SEVEN_ZIP="/usr/bin/7z"  # Change this to your actual path if needed

# Vérification de la connexion ADB
if ! adb devices | grep -q "device$"; then
    echo "Erreur : Aucun appareil ADB détecté."
    exit 1
fi

# Création du dossier temporaire si non existant
mkdir -p "$TMP_DIR"

echo
echo "Lecture des sauvegardes ..."
echo

# Boucle sur les dossiers
for APP_DIR in "$PWD"/*; do
    if [ -d "$APP_DIR" ]; then
        APP_DIR=$(realpath "$APP_DIR")
        DUMMY="$APP_DIR"
        # Exclusion du dossier "apks", qui n'est pas un dossier de sauvegarde
        if [ "$APP_DIR" == "$APK_DIR" ]; then
            echo "Dossier apks détecté"
            echo
        else
            echo "Dossier $APP_DIR"
            # Traitement du répertoire d'une application
            META_FILE="$APP_DIR/0/meta_v2.am.json"
            if [ ! -f "$META_FILE" ]; then
                echo "Fichier meta_v2.am.json manquant pour $APP_DIR"
            else
                # Lecture des informations du fichier meta_v2.am.json
                APP_PKG=""
                IS_SPLIT_APK=false
                # Utilisation de grep pour extraire les données de base
                APP_PKG=$(grep -oP '"package_name":\s*"\K[^"]+' "$META_FILE")
                IS_SPLIT_APK=$(grep -oP '"is_split_apk":\s*\K[^,]+' "$META_FILE")

                # Nettoyage des noms
                APP_PKG=$(echo "$APP_PKG" | tr -d '"')
                IS_SPLIT_APK=$(echo "$IS_SPLIT_APK" | tr -d '"')

                # Utilisation de grep pour extraire les données de répertoires
                DATA_DIRS=()
                IN_DATA_DIRS=0
                COUNT=-2

                while IFS= read -r LINE; do
                    if [[ $LINE == *"\"data_dirs\": ["* ]]; then
                        IN_DATA_DIRS=1
                    fi
                    if [[ $LINE == *"]"* && $IN_DATA_DIRS -eq 1 ]]; then
                        IN_DATA_DIRS=0
                    fi
                    if [ $IN_DATA_DIRS -eq 1 ]; then
                        COUNT=$((COUNT + 1))
                        LINE=$(echo "$LINE" | tr -d '[:space:]' | tr -d ',"')
                        DATA_DIRS+=("$LINE")
                    fi
                done < "$META_FILE"

                # Installation
                echo "Restauration du package $APP_PKG : "
                echo

                SOURCE_FILE="$APP_DIR/0/source.tar.gz.0"
                # Décompression du/des fichier .apk par 7-zip
                "$SEVEN_ZIP" x "$SOURCE_FILE" -o"$TMP_DIR" -y > /dev/null 2>&1
                "$SEVEN_ZIP" x "$TMP_DIR/source.tar.gz" -o"$TMP_DIR" -y > /dev/null 2>&1
                rm "$TMP_DIR/source.tar.gz"

                # Vérification de la liste des fichiers APK extraits
                APK_LIST=()
                for APK in "$TMP_DIR"/*.apk; do
                    APK_LIST+=("$APK")
                done

                if [ "$IS_SPLIT_APK" == "true" ]; then
                    # Installation multiple
                    echo "$APP_PKG : Installation en mode Split APK..."
                    adb install-multiple "${APK_LIST[@]}"
                else
                    # Installation simple
                    echo "$APP_PKG : Installation standard..."
                    adb install "${APK_LIST[0]}"
                fi

                # Nettoyage du répertoire temporaire
                rm -rf "$TMP_DIR/*"
                mkdir -p "$TMP_DIR"

                echo "$APP_PKG : Transfert des données, ${#DATA_DIRS[@]} répertoires détectés ..."

                for i in "${!DATA_DIRS[@]}"; do
                    DATA_DIR="${DATA_DIRS[$i]}"
                    # Décompression de data0.tar.gz.0
                    "$SEVEN_ZIP" x -o"$TMP_DIR" "$APP_DIR/0/data${i}.tar.gz.0" -y > /dev/null 2>&1
                    "$SEVEN_ZIP" x -o"$TMP_DIR" "$TMP_DIR/data${i}.tar.gz" -y > /dev/null 2>&1
                    rm "$TMP_DIR/data${i}.tar.gz"

                    if [ -d "$TMP_DIR" ] && [ "$(ls -A $TMP_DIR)" ]; then
                        # Envoi des fichiers dans $TMP_DIR vers /storage/emulated/0/
                        adb push "$TMP_DIR/" /storage/emulated/0/
                        # Création du répertoire
                        adb shell su -c "mkdir -p /storage/emulated/0/${DATA_DIR}/"
                        # Transfert des fichiers
                        adb shell su -c "cp -r /storage/emulated/0/tmp/. /storage/emulated/0/${DATA_DIR}/ && rm -rf /storage/emulated/0/tmp/*"
                        # Nettoyage du répertoire temporaire
                        rm -rf "$TMP_DIR/*"
                    else
                        echo "Erreur : Impossible de décompresser data${i}.tar.gz.0"
                    fi
					
                    echo "$APP_PKG : Fin du transfert."
                done
                echo
            fi
        fi
    fi
done


echo "Redémarrage du service Google Play..."

adb shell am force-stop com.android.vending > /dev/null 2>&1
adb shell monkey -p com.android.vending -c android.intent.category.LAUNCHER 1 > /dev/null 2>&1
echo

echo "Restaurations terminées."
exit 0