#!/bin/bash

# Pallet APK Handler - Restauration de sauvegarde de type Neo-Backup

# Attention - Ne gère pas les vérifications de version
# Nécessite les droits root
# Nécessite 7zip avec la fonction de décompression ZST

# Répertoires principaux
ROOT_DIR="$(pwd)"
TMP_DIR="$ROOT_DIR/tmp"
TMP_FILE="$ROOT_DIR/installed_packages.tmp"
LIST_FILE="$ROOT_DIR/packages_cibles.txt"

# Vérification de la connexion ADB
if ! adb devices | grep -q "device$"; then
    echo "Erreur : Aucun appareil ADB détecté."
    exit 1
fi

# Vérification de l'existence du fichier packages_cibles.txt
if [ ! -f "$LIST_FILE" ]; then
    echo "\"packages_cibles.txt\" : fichier introuvable"
    exit 1
fi

# Création du répertoire temporaire
mkdir -p "$TMP_DIR"

# Récupération de la liste des applications utilisateur installées
echo "Récupération de la liste des applications utilisateur installées..."
adb shell pm list packages -3 > "$TMP_FILE"
echo

echo "Début de la restauration Neo Backup..."

# Boucle sur les dossiers de package
while IFS= read -r PKG_PATH; do
    PKG_NAME=$(basename "$PKG_PATH")
    SAVE_DIR="$ROOT_DIR/$PKG_PATH"

    # Recherche du sous-dossier de sauvegarde
    for dir in "$SAVE_DIR"/*-user_0; do
        if [ -d "$dir" ]; then
            SAVE_DIR="$dir"
            echo "$PKG_NAME : Traitement du package ..."

            INSTALLED=0
            while IFS= read -r line; do
                PACKAGE_NAME=$(echo "$line" | cut -d':' -f2 | xargs)
                if [ "$PACKAGE_NAME" == "$PKG_NAME" ]; then
                    INSTALLED=1
                    echo "$PKG_NAME : Package déjà installé."
                fi
            done < "$TMP_FILE"

            if [ "$INSTALLED" -eq 0 ]; then
                echo "$PKG_NAME : Installation"
                # Extraction et installation des APK
                APK_LIST=()
                for apk in "$SAVE_DIR"/*.apk; do
                    APK_LIST+=("$apk")
                done
                if [ ${#APK_LIST[@]} -gt 0 ]; then
                    echo "Installation de $PKG_NAME ..."
                    adb install-multiple "${APK_LIST[@]}"
                    INSTALLED=1
                else
                    echo "Aucun APK trouvé pour $PKG_NAME - Ignoré."
                fi
            fi

            if [ "$INSTALLED" -eq 1 ]; then
                # Restauration des données
                echo "$PKG_NAME : Recherche de sauvegardes éventuelles ..."
                DATA_FILE="$SAVE_DIR/data.tar.zst"
                DATA_FILE_EXT="$SAVE_DIR/external_files.tar.zst"

                # Traitement de data.tar.zst
                if [ -f "$DATA_FILE" ]; then
                    echo "Décompression de $DATA_FILE ..."
                    7z x "$DATA_FILE" -o"$TMP_DIR" -y > /dev/null
                    7z x "$TMP_DIR/data.tar" -o"$TMP_DIR" -y > /dev/null
                    rm "$TMP_DIR/data.tar"
                    echo "Transfert des données vers l’appareil..."
                    adb push "$TMP_DIR/." /storage/emulated/0/neo_tmp/
                    adb shell su -c "mkdir -p /data/data/$PKG_NAME"
                    adb shell su -c "cp -r /storage/emulated/0/neo_tmp/. /data/data/$PKG_NAME"
                    adb shell su -c "rm -rf /storage/emulated/0/neo_tmp"
                    # Nettoyage du TMP_DIR
                    rm -rf "$TMP_DIR/*"
                fi

                # Traitement de external_files.tar.zst
                if [ -f "$DATA_FILE_EXT" ]; then
                    echo "Décompression de $DATA_FILE_EXT ..."
                    7z x "$DATA_FILE_EXT" -o"$TMP_DIR" -y > /dev/null
                    7z x "$TMP_DIR/external_files.tar" -o"$TMP_DIR" -y > /dev/null
                    rm "$TMP_DIR/external_files.tar"
                    echo "Transfert des données vers l’appareil..."
                    adb push "$TMP_DIR/." /storage/emulated/0/neo_tmp/
                    adb shell su -c "mkdir -p /storage/emulated/0/Android/data/$PKG_NAME"
                    adb shell su -c "cp -r /storage/emulated/0/neo_tmp/. /storage/emulated/0/Android/data/$PKG_NAME"
                    adb shell su -c "rm -rf /storage/emulated/0/neo_tmp"
                    # Nettoyage du TMP_DIR
                    rm -rf "$TMP_DIR/*"
                fi
                echo "$PKG_NAME : Fin de la restauration."
            fi
            echo
        fi
    done < "$LIST_FILE"
done

rm "$TMP_FILE"

echo "Redémarrage du Play Store..."
adb shell am force-stop com.android.vending > /dev/null
adb shell monkey -p com.android.vending -c android.intent.category.LAUNCHER 1 > /dev/null

echo
echo "Restaurations terminées."
exit 0