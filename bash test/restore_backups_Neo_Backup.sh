#!/bin/bash
set -e

# Répertoires principaux
ROOT_DIR="$(pwd)"
TMP_DIR="$ROOT_DIR/tmp"
TMP_FILE="$ROOT_DIR/installed_packages.tmp"

# Vérification de la connexion ADB
ADB_CONNECTED=""
if adb devices | awk 'NR>1 {print $1}' | grep -q .; then
    ADB_CONNECTED=1
fi

if [ -z "$ADB_CONNECTED" ]; then
    echo "Erreur : Aucun appareil ADB détecté."
    exit 1
fi

# Création du répertoire temporaire
mkdir -p "$TMP_DIR"

# Récupération de la liste des applications utilisateur installées
echo "Récupération de la liste des applications utilisateur installées..."
adb shell pm list packages -3 > "$TMP_FILE"
echo

echo
echo "Début de la restauration Neo Backup..."
echo

# Boucle sur les dossiers de package
for PKG_PATH in "$ROOT_DIR"/*; do
    if [ -d "$PKG_PATH" ]; then
        PKG_NAME="$(basename "$PKG_PATH")"

        # Recherche du sous-dossier de sauvegarde
        for SAVE_DIR in "$PKG_PATH"/*-user_0; do
            if [ -d "$SAVE_DIR" ]; then
                SAVE_NAME="$(basename "$SAVE_DIR")"

                echo "$PKG_NAME : Traitement du package ..."
                # echo "Dossier de sauvegarde : $SAVE_NAME"
                
                INSTALLED=0
                while IFS= read -r line; do
                    if [[ "$line" == *"$PKG_NAME"* ]]; then
                        INSTALLED=1
                        echo "$PKG_NAME : Package déjà installé."
                    fi
                done < "$TMP_FILE"

                if [ "$INSTALLED" -eq 0 ]; then
                    echo "$PKG_NAME : Installation"
                    # Extraction et installation des APK
                    APK_LIST=""
                    for APK in "$SAVE_DIR"/*.apk; do
                        if [ -f "$APK" ]; then
                            APK_LIST="$APK_LIST \"$APK\""
                        fi
                    done

                    if [ -n "$APK_LIST" ]; then
                        echo "Installation de $PKG_NAME ..."
                        # echo "APK détectés : $APK_LIST"
                        adb install-multiple $APK_LIST
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
                        # echo "Décompression de $DATA_FILE ..."
                        7z x "$DATA_FILE" -o"$TMP_DIR" -y > /dev/null
                        7z x "$TMP_DIR/data.tar" -o"$TMP_DIR" -y > /dev/null
                        rm "$TMP_DIR/data.tar"
                        # echo "Transfert des données vers l’appareil..."
                        adb push "$TMP_DIR/." /storage/emulated/0/neo_tmp/
                        # L’utilisateur est root, et on place tout dans /data/data/<pkg>
                        # Déplacement final dans /data/data/$PKG_NAME/ ...
                        adb shell su -c "mkdir -p /data/data/$PKG_NAME"
                        adb shell su -c "cp -r /storage/emulated/0/neo_tmp/. /data/data/$PKG_NAME"
                        adb shell su -c "rm -rf /storage/emulated/0/neo_tmp"
                        # Nettoyage du TMP_DIR
                        rm -rf "$TMP_DIR/*"
                        mkdir -p "$TMP_DIR"
                    else
                        # $PKG_NAME : Fichier data.tar.zst introuvable, ou application non installée
                        echo "$PKG_NAME : Fichier data.tar.zst introuvable, ou application non installée"
                    fi

                    # Traitement de external_files.tar.zst
                    if [ -f "$DATA_FILE_EXT" ]; then
                        # echo "Décompression de $DATA_FILE_EXT ..."
                        7z x "$DATA_FILE_EXT" -o"$TMP_DIR" -y > /dev/null
                        7z x "$TMP_DIR/external_files.tar" -o"$TMP_DIR" -y > /dev/null
                        rm "$TMP_DIR/external_files.tar"

                        # echo "Transfert des données vers l’appareil..."
                        adb push "$TMP_DIR/." /storage/emulated/0/neo_tmp/
                        # L’utilisateur est root, et on place tout dans /storage/emulated/0/Android/data/<pkg>
                        # Déplacement final dans /storage/emulated/0/Android/data/$PKG_NAME/ ...
                        adb shell su -c "mkdir -p /storage/emulated/0/Android/data/$PKG_NAME"
                        adb shell su -c "cp -r /storage/emulated/0/neo_tmp/. /storage/emulated/0/Android/data/$PKG_NAME"
                        adb shell su -c "rm -rf /storage/emulated/0/neo_tmp"
                        # Nettoyage du TMP_DIR
                        rm -rf "$TMP_DIR/*"
                        mkdir -p "$TMP_DIR"
                    else
                        # $PKG_NAME : Fichier external_files.tar.zst introuvable, ou application non installée
                        echo "$PKG_NAME : Fichier external_files.tar.zst introuvable, ou application non installée"
                    fi
                    echo "$PKG_NAME : Fin de la restauration."
                fi
                echo
            fi
        done
    fi
done
rm -f "$TMP_FILE"

echo "Redémarrage du Play Store..."
adb shell am force-stop com.android.vending > /dev/null
adb shell monkey -p com.android.vending -c android.intent.category.LAUNCHER 1 > /dev/null

echo
echo "Restaurations terminées."