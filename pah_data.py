import logging
import json

from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Dict, Tuple, Optional

import pah_utils as pahu


@dataclass
class PackageInfo:
    """Structure de données pour un package."""
    label: str
    android: bool
    local: bool
    checked: bool = False
    file_hash: str = ""  # Hash rapide pour identification fallback
    file_name: str = ""  # Nom de fichier local associé

class PackageMap:
    """Gestionnaire centralisé des données de packages.
    Remplace le dictionnaire _pkg_map avec une interface plus propre
    et prépare la migration vers QTableView.
    """

    def __init__(self):
        self._data: Dict[Tuple[str, int], PackageInfo] = {}
        self._dirty: set[Tuple[str, int]] = set()  # Track modifications

    def add(self, pkg: str, vcode: str, **info) -> None:
        key = (pkg, int(vcode))
        if key not in self._data:
            self._data[key] = PackageInfo(**info)
        else:
            for field, value in info.items():
                if field == "label":
                    if value:  # ⬅️ NE PAS écraser si vide
                        self._data[key].label = value
                elif hasattr(self._data[key], field):
                    setattr(self._data[key], field, value)
        self._dirty.add(key)

    def get(self, pkg: str, vcode: str) -> Optional[PackageInfo]:
        """Récupère les infos d'un package."""
        key = (pkg, int(vcode))
        return self._data.get(key)

    def set_check(self, pkg: str, vcode: str, is_checked: bool) -> None:
        key = (pkg, int(vcode))
        found_package = self._data.get(key)
        if not found_package:
            logging.warning(f"set_check: package not found {pkg} {vcode}")
            return
        found_package.checked = is_checked

    def remove(self, pkg: str, vcode: str) -> bool:
        """Supprime un package. Retourne True si supprimé."""
        key = (pkg, int(vcode))
        if key in self._data:
            del self._data[key]
            self._dirty.discard(key)
            return True
        return False

    def exists(self, pkg: str, vcode: str) -> bool:
        """Vérifie l'existence d'un package."""
        key = (pkg, int(vcode))
        return key in self._data

    def find_by_hash(self, file_hash: str) -> Optional[Tuple[str, int]]:
        """Trouve un package par son hash de fichier.
        Args:
            file_hash: Hash du fichier APK
        Returns:
            Tuple[str, int] ou None: (package_name, version_code) si trouvé
        """
        if not file_hash:
            return None

        for (pkg, vcode_int), info in self._data.items():
            if info.file_hash == file_hash:
                return (pkg, vcode_int)
        return None

    def find_by_filename(self, file_name: str) -> Optional[Tuple[str, int]]:
        if not file_name:
            return None

        for (pkg, vcode_int), info in self._data.items():
            if info.file_name == file_name:
                return (pkg, vcode_int)
        return None

    def update_file_hash(self, pkg: str, vcode: str, file_hash: str) -> None:
        """Met à jour le hash de fichier pour un package."""
        info = self.get(pkg, vcode)
        if info:
            info.file_hash = file_hash
            self._dirty.add((pkg, int(vcode)))

    def update_file_name(self, pkg: str, vcode: str, file_name: str) -> None:
        """Met à jour le nom de fichier local pour un package."""
        info = self.get(pkg, vcode)
        if info:
            info.file_name = file_name
            self._dirty.add((pkg, int(vcode)))

    def get_all_packages(self) -> Dict[Tuple[str, int], PackageInfo]:
        """Retourne une copie des packages."""
        return self._data.copy()

    def clear_dirty(self) -> None:
        """Marque toutes les entrées comme synchronisées."""
        self._dirty.clear()

    def is_dirty(self, pkg: str, vcode: str) -> bool:
        """Vérifie si une entrée a été modifiée."""
        key = (pkg, int(vcode))
        return key in self._dirty

    def clear(self) -> None:
        """Vide toutes les données."""
        self._data.clear()
        self._dirty.clear()

    def save_to_file(self, file_path: Path) -> None:
        """Sauvegarde PackageMap dans un fichier JSON.

        Args:
            file_path: Chemin du fichier de sauvegarde
        """
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            # Convertir les clés tuple en strings pour JSON
            serializable_data = {}
            for (pkg, vcode_int), info in self._data.items():
                key = f"{pkg}#{vcode_int}"  # Séparateur unique
                serializable_data[key] = asdict(info)

            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(serializable_data, f, indent=2, ensure_ascii=False)

            logging.info(f"PackageMap saved to {file_path}")

        except Exception as e:
            logging.error(f"Failed to save PackageMap: {e}")

    def load_from_file(self, file_path: Path) -> int:
        """Charge PackageMap depuis un fichier JSON.

        Args:
            file_path: Chemin du fichier à charger

        Returns:
            int: Nombre d'entrées chargées
        """
        if not file_path.exists():
            logging.info(f"PackageMap file {file_path} not found, starting fresh")
            return 0

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                serializable_data = json.load(f)

            loaded_count = 0
            for key, info_dict in serializable_data.items():
                # Reconvertir les clés string en tuple
                try:
                    pkg, vcode_str = key.split('#', 1)
                    vcode_int = int(vcode_str)

                    self._data[(pkg, vcode_int)] = PackageInfo(**info_dict)
                    loaded_count += 1
                except Exception as e:
                    logging.warning(f"Invalid entry {key}: {e}")
                    continue

            logging.info(f"PackageMap loaded {loaded_count} entries from {file_path}")
            return loaded_count

        except Exception as e:
            logging.error(f"Failed to load PackageMap: {e}")
            return 0

    def get_save_file_path(self) -> Path:
        """Retourne le chemin par défaut du fichier de sauvegarde."""
        return Path(__file__).parent / "extracted_apks" / "packagemap.json"

    def rebuild_from_scan(self, scan_result) -> None:
        """
        Merge le scan dans le PackageMap existant
        SANS détruire le cache local (file_hash, file_name).
        """

        if hasattr(scan_result, "get_all_packages"):
            scanned_items = scan_result.get_all_packages().items()
        else:
            scanned_items = scan_result.items()

        # Reset UNIQUEMENT android (source volatile)
        for info in self._data.values():
            info.android = False

        for (pkg, vcode_int), info in scanned_items:
            vcode_str = str(vcode_int)

            existing = self.get(pkg, vcode_str)

            if existing:
                existing.android = info.android
                existing.local = info.local

                if info.label and not existing.label:
                    existing.label = info.label

                if not existing.file_hash and info.file_hash:
                    existing.file_hash = info.file_hash

                if not existing.file_name and info.file_name:
                    existing.file_name = info.file_name

            else:
                # Nouvelle entrée
                self.add(
                    pkg,
                    vcode_str,
                    label=info.label,
                    android=info.android,
                    local=info.local,
                    checked=False,
                    file_hash=info.file_hash,
                    file_name=info.file_name,
                )

    def remove_orphans(self) -> None:
        """
        Supprime uniquement les entrées réellement mortes :
        ni installées, ni présentes localement.
        """
        to_remove = [
            (pkg, vcode_int)
            for (pkg, vcode_int), info in self._data.items()
            if not info.android and not info.local
        ]

        for pkg, vcode_int in to_remove:
            self.remove(pkg, str(vcode_int))

def map_apk_files_to_packages(package_map, apk_dir: Path, files_to_hash: list[Path]) -> Dict[str, Tuple[str, str, str]]:
    """Map les fichiers APK vers les packages avec fallback hash.

    Args:
        package_map: Instance de PackageMap
        apk_dir: Répertoire contenant les APK
        files_to_hash: liste des fichiers qui nécessitent un hash

    Returns:
        Dict: {filename: (label, pkg, vcode)}
    """
    mapping = {}
    hash_to_filename = {}

    # Hasher uniquement les fichiers inconnus
    for apk_file in files_to_hash:
        file_hash = pahu.get_fast_apk_hash(apk_file)
        if file_hash:
            hash_to_filename[file_hash] = apk_file.name

    # Mapper tous les fichiers connus ou hashés
    for (pkg, vcode_int), info in package_map.get_all_packages().items():
        if not info.local:
            continue

        vcode_str = str(vcode_int)
        expected_filename = f"{pkg}_{vcode_str}.apk"

        # 1) Nom exact sauvegardé
        if info.file_name and (apk_dir / info.file_name).exists():
            mapping[info.file_name] = (info.label, pkg, vcode_str)
            continue

        # 2) Nom attendu
        if (apk_dir / expected_filename).exists():
            mapping[expected_filename] = (info.label, pkg, vcode_str)
            continue

        # 3) Fallback hash
        if info.file_hash and info.file_hash in hash_to_filename:
            filename = hash_to_filename[info.file_hash]
            mapping[filename] = (info.label, pkg, vcode_str)
            logging.info(f"Found renamed APK: {filename} -> {pkg} v{vcode_str}")

    return mapping

# array building
def on_scan_finished(main_window, scan_result):
    if getattr(main_window, "progress_dialog", None):
        main_window.progress_dialog.close()
        main_window.progress_dialog = None

    # 🔥 remplace complètement le modèle
    main_window.package_map = scan_result
    main_window.table_adapter.pkg_map = main_window.package_map

    # UI
    main_window.table_adapter.refresh()
    main_window.table_adapter.clear_all_checked()

    # persist
    save_file = main_window.package_map.get_save_file_path()
    main_window.package_map.save_to_file(save_file)