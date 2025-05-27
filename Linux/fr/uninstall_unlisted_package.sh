#!/bin/bash

# Pallet APK Handler - Désinstallateur de packages utilisateur automatisé

# Désinstalle TOUS les packages utilisateurs qui ne sont PAS listés dans le fichier "packages.txt".
# Si le fichier "packages_utiles.txt" n'est pas détecté, le script est interrompu
# Si le fichier "packages_utiles.txt" est vide, tous les packages utilisateurs seront désinstallés

# Définition des fichiers et dossiers
LIST_FILE="$(pwd)/packages_usefull.txt"
TMP_FILE="$(pwd)/installed_packages.tmp"

# Vérification de la connexion ADB
if ! adb devices | grep -q "device$"; then
    echo "Erreur : Aucun appareil ADB détecté."
    exit 1
fi

# Vérification de l'existence du fichier packages_usefull.txt
if [ ! -f "$LIST_FILE" ]; then
    echo "\"packages_usefull.txt\" : fichier introuvable"
    exit 1
fi

echo "Lecture de la liste des applications à conserver..."
PKG_LIST_KEEP=()
while IFS= read -r line; do
    PKG_LIST_KEEP+=("$line")
done < "$LIST_FILE"
echo

# Récupération de la liste des applications utilisateur installées
echo "Récupération de la liste des applications utilisateur installées..."
adb shell pm list packages -3 > "$TMP_FILE"
echo

# Comparaison et suppression des applications inutiles
echo "Suppression des applications inutiles..."
while IFS= read -r line; do
    PACKAGE_NAME=$(echo "$line" | cut -d':' -f2 | xargs)  # Clean the package name
    FOUND=0
    for pkg in "${PKG_LIST_KEEP[@]}"; do
        if [ "$PACKAGE_NAME" == "$pkg" ]; then
            FOUND=1
            break
        fi
    done
    if [ "$FOUND" -eq 0 ]; then
        echo "Suppression de $PACKAGE_NAME..."
        adb uninstall "$PACKAGE_NAME"
    fi
done < "$TMP_FILE"
echo

# Nettoyage
rm "$TMP_FILE"
echo "Désinstallations terminées."
exit 0