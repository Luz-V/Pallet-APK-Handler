#!/bin/bash

# Pallet APK Handler - Détecteur de packages utilisateurs installés

# Crée une liste "installed_packages.txt" des packages utilisateurs installés sur l'appareil android connecté.

# Définition du fichier de sortie
LIST_FILE="$(pwd)/installed_packages.txt"

# Vérification de la connexion ADB
ADB_CONNECTED=""
if adb devices | grep -q "device$"; then
    ADB_CONNECTED=1
else
    echo "Erreur : Aucun appareil ADB détecté."
    exit 1
fi

# Extraction des applications utilisateur
echo "Extraction de la liste des applications utilisateur..."
adb shell pm list packages -3 > "$LIST_FILE"

# Nettoyage du format de sortie
# This will extract the package names and overwrite the original file
awk -F':' '{print $2}' "$LIST_FILE" | xargs > "$LIST_FILE"

echo "Liste des applications enregistrée dans \"$LIST_FILE\"."