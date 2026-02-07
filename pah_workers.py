import logging
import shlex

from pathlib import Path
from PyQt5.QtCore import Qt, QThread, pyqtSignal, pyqtSlot

import pah_functions as pah


class ScanWorker(QThread):
    progress = pyqtSignal(str)
    progress_switch_percent = pyqtSignal()
    progress_percent = pyqtSignal(str,int)
    result_ready   = pyqtSignal(object)
    error_occurred = pyqtSignal(str)
    android_scan_finished = pyqtSignal(str)

    def __init__(self, apk_installer_path: Path, package_map=None, parent=None,
                 installed_list=[], saved_list=[],android_scan=True,local_scan=True):
        # QThread and signals init.
        super().__init__(parent)
        # Local variables
        self.apk_installer_path = apk_installer_path
        self.package_map = package_map  # NOUVEAU: PackageMap instance
        self.installed_list = installed_list
        self.saved_list = saved_list
        self.android_scan = android_scan
        self.local_scan = local_scan
        cancelled = pyqtSignal()

    def run(self):
        try:
            if self.android_scan:
                is_adb_connected = pah.check_adb_connection()
                if is_adb_connected:
                    self.progress.emit(
                        "Scanning Android installed applications...\n"
                        "Unlocking the device may help."
                    )
                    # 1) Scan device
                    self.installed_list = pah.extract_packages_labels_version(
                        self.apk_installer_path
                    )
                    self.android_scan_finished.emit("Android scan complete")
                else:
                    logging.error("\nNo adb connection detected")
                    if self.package_map:
                        for info in self.package_map.get_all_packages().values():
                            info.android = False
                    self.installed_list = []
            if self.local_scan:
                self.progress.emit("Scanning local APK files...")
                apk_dir = Path(__file__).parent / "extracted_apks"
                apk_dir.mkdir(exist_ok=True)
                
                if self.package_map:
                    # NOUVELLE APPROCHE: utiliser PackageMap avec hash fallback
                    # Forcer les flags avant le scan
                    if not self.android_scan:
                        for (pkg, vcode_int), info in self.package_map.get_all_packages().items():
                            info.android = False
                            info.local = False
                    
                    self.progress.emit("Discovering APK files...")
                    
                    # Découvrir tous les fichiers APK/APKS
                    present_files = {
                        p.name for p in apk_dir.glob("*.apk")
                    } | {
                        p.name for p in apk_dir.glob("*.apks")
                    }
                    # Fichiers déjà connus (par nom ou hash)
                    known_files = {
                                      info.file_name for (pkg, vcode), info in
                                      self.package_map.get_all_packages().items() if info.file_name
                                  } | {
                                      f"{pkg}_{vcode}.apk" for (pkg, vcode), info in
                                      self.package_map.get_all_packages().items()
                                  }

                    # Fichiers à hasher = ceux qui sont sur le disque mais inconnus
                    files_to_hash = [apk_dir / f for f in present_files if f not in known_files]

                    # Mapping des fichiers existants aux packages dans PackageMap
                    self.progress.emit("Mapping APK files to packages...")

                    mapping = pah.map_apk_files_to_packages(self.package_map, apk_dir, files_to_hash)
                    mapped_files = set(mapping.keys())

                    # Découvrir les nouveaux fichiers non mappés
                    unmapped_files = present_files - mapped_files
                    
                    # Résoudre chaque fichier local : filename -> hash -> aapt
                    if unmapped_files:
                        tmp_dir = Path(__file__).parent / "tmp"
                        tmp_dir.mkdir(exist_ok=True)

                        for i, filename in enumerate(unmapped_files):
                            self.progress.emit(f"Scanning {filename} ({i+1}/{len(unmapped_files)})")
                            apk_file = apk_dir / filename

                            try:
                                # 1) lookup par filename dans le JSON
                                matched_key = self.package_map.find_by_filename(filename)

                                # 2) fallback: lookup par hash
                                file_hash = pah.get_fast_apk_hash(apk_file)
                                if not matched_key and file_hash:
                                    matched_key = self.package_map.find_by_hash(file_hash)

                                if matched_key:
                                    pkg, vcode_int = matched_key
                                    vcode_str = str(vcode_int)

                                    info = self.package_map.get(pkg, vcode_str)
                                    if info and not info.label:
                                        try:
                                            # tentative douce : extraire le label si possible
                                            _, _, label = pah.extract_pkg_version_label(apk_file, tmp_dir)
                                            if label:
                                                info.label = label
                                        except Exception:
                                            pass  # surtout ne rien casser ici

                                    self.package_map.update_file_name(pkg, vcode_str, filename)
                                    if file_hash:
                                        self.package_map.update_file_hash(pkg, vcode_str, file_hash)
                                    continue

                                # 3) aapt scan si inconnu
                                pkg, vcode, label = pah.extract_pkg_version_label(apk_file, tmp_dir)
                                self.package_map.add(
                                    pkg,
                                    vcode,
                                    label=label,
                                    android=False,
                                    local=True,
                                    checked=False,
                                    file_hash=file_hash,
                                    file_name=filename,
                                )

                            except Exception as e:
                                logging.error(f"Error scanning {filename}: {e}")
                    
                    # Mettre à jour les hashes des fichiers mappés
                    self.progress.emit("Updating file hashes...")
                    for filename, (label, pkg, vcode) in mapping.items():
                        apk_file = apk_dir / filename
                        file_hash = pah.get_fast_apk_hash(apk_file)
                        if file_hash:
                            self.package_map.update_file_hash(pkg, vcode, file_hash)
                        self.package_map.update_file_name(pkg, vcode, filename)
                    
                    # NOUVEAU: Supprimer les packages orphelins (fichiers supprimés)
                    self.progress.emit("Removing orphaned packages...")
                    orphaned_packages = []
                    for (pkg, vcode_int), info in self.package_map.get_all_packages().items():
                        if info.local:  # Seulement les packages avec backup local
                            expected_filename = f"{pkg}_{vcode_int}.apk"
                            if expected_filename not in present_files:
                                # Vérifier si on peut le retrouver par hash
                                found_by_hash = False
                                if info.file_hash:
                                    for filename in present_files:
                                        apk_file = apk_dir / filename
                                        file_hash = pah.get_fast_apk_hash(apk_file)
                                        if file_hash == info.file_hash:
                                            found_by_hash = True
                                            break
                                
                                if not found_by_hash:
                                    orphaned_packages.append((pkg, vcode_int))
                    
                    # Supprimer les packages orphelins
                    for pkg, vcode_int in orphaned_packages:
                        self.package_map.remove(pkg, str(vcode_int))
                    
                    if orphaned_packages:
                        self.progress.emit(f"Removed {len(orphaned_packages)} orphaned packages")
                    
                    # Construire saved_list depuis PackageMap
                    self.saved_list = [
                        (pkg, str(vcode_int), info.label)
                        for (pkg, vcode_int), info in self.package_map.get_all_packages().items()
                        if info.local
                    ]
                    
                    self.progress.emit(f"Found {len(self.saved_list)} local packages")
                else:
                    # APPROCHE LEGACY: garder save.tmp pour compatibilité
                    self.progress.emit("Scanning local APK(s) files : loading save.tmp …")
                    logging.info("Local scan started")

                    # 2) Load cache
                    save_file = apk_dir / "save.tmp"
                    save_cache: dict[str, tuple[str, str, str]] = {}
                    save_file.touch(exist_ok=True)

                    for line in save_file.read_text(encoding="utf-8").splitlines():
                        try:
                            parts = shlex.split(line)
                            if len(parts) == 4:
                                fname, label, pkg, vcode = parts
                                save_cache[fname] = (label, pkg, vcode)
                        except Exception as e:
                            logging.warning(f"Ignored line in save.tmp: {line!r} ({e})")

                    # 3) Discover what's on disk
                    present = {
                                  p.name for p in apk_dir.glob("*.apk")
                              } | {
                                  p.name for p in apk_dir.glob("*.apks")
                              }

                    # 4) Purge stale entries
                    for stale in set(save_cache) - present:
                        save_cache.pop(stale)

                    self.progress.emit("Scanning unregistered local APK(s) files …")
                    # 5) Scan & rename new ones
                    tmp_dir = Path(__file__).parent / "tmp"
                    tmp_dir.mkdir(exist_ok=True)
                    self.progress_switch_percent.emit()
                    total_rescans = len(present - set(save_cache))

                    for index, fname in enumerate(present - set(save_cache)):
                        self.progress_percent.emit(f"Scanning unregistered local APK(s) files …\n{fname}",int(index / total_rescans * 100))
                        apk = apk_dir / fname
                        logging.debug(f"scanning for {fname}")
                        try:
                            pkg, vcode, label = pah.extract_pkg_version_label(apk, tmp_dir)
                            canonical = f"{pkg}_{vcode}{apk.suffix}"
                            if canonical != fname:
                                apk.rename(apk_dir / canonical)
                                fname = canonical
                            save_cache[fname] = (label, pkg, vcode)
                        except Exception as e:
                            logging.error(f"Error scanning {fname}: {e}")

                    # 6) Rewrite save.tmp
                    self.progress.emit("Updating save.tmp …")
                    with open(save_file, "w", encoding="utf-8") as f:
                        for fname, (label, pkg, vcode) in sorted(save_cache.items()):
                            f.write(f'{fname} "{label}" {pkg} {vcode}\n')

                    # 7) Build self.saved_list from save_cache
                    self.saved_list = [
                        (pkg, vcode, label)
                        for (label, pkg, vcode) in save_cache.values()
                    ]

            # 8) Fusion device + local backup apps list dans PackageMap
            if self.package_map:
                apk_dir = Path(__file__).parent / "extracted_apks"
                present_files = {p.name for p in apk_dir.glob("*.apk")} | {p.name for p in apk_dir.glob("*.apks")}

                for (pkg, vcode_int), info in self.package_map.get_all_packages().items():
                    for ext in ['.apk', '.apks']:
                        if f"{pkg}_{vcode_int}{ext}" in present_files:
                            info.local = True
                            break

                # Check installed packaged
                for pkg, vcode, label in self.installed_list:
                    key = (pkg, int(vcode))
                    if key in self.package_map.get_all_packages():
                        self.package_map.get_all_packages()[key].android = True
                    else:
                        # Cas : installé sur Android mais pas connu localement
                        self.package_map.add(
                            pkg,
                            vcode,
                            label=label,
                            android=True,
                            local=False,
                            checked=False,
                        )

                # Émettre PackageMap directement
                self.result_ready.emit(self.package_map)
            else:
                # Fallback pour compatibilité avec l'ancien système
                table_dico: dict[tuple[str, str], dict[str, Any]] = {}
                
                # Ajouter les packages installés sur Android
                for pkg, vcode, label in self.installed_list:
                    key = (pkg, vcode)
                    if key not in table_dico:
                        table_dico[key] = {"label": label, "android": False, "local": False}
                    table_dico[key]["android"] = True
                
                # Check locally found packages
                for pkg, vcode, label in self.saved_list:
                    key = (pkg, vcode)
                    if key not in table_dico:
                        table_dico[key] = {"label": label, "android": False, "local": False}
                    table_dico[key]["local"] = True

                # check android installed packages
                for pkg, vcode, label in self.installed_list:
                    key = (pkg, int(vcode))
                    if key in self.package_map.get_all_packages():
                        self.package_map.get_all_packages()[key].android = True
                    else:
                        # Adding new entry if needed
                        self.package_map.add(
                            pkg,
                            vcode,
                            label=label,
                            android=True,
                            local=False,
                            checked=False,
                        )

                self.result_ready.emit(table_dico)
            logging.info("Scan finished successfully")

        except Exception as e:
            self.error_occurred.emit(f"Scan error: {str(e)}")
            logging.error(f"Scan error: {str(e)}")


class InstallWorker(QThread):
    progress = pyqtSignal(str, int)  # message, percentage
    success = pyqtSignal(str, str)   # package_name, version_code
    error = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, install_list, tmp_dir, downgrade_flag=False):
        super().__init__()
        self.install_list = install_list
        self.tmp_dir = tmp_dir
        self.downgrade_flag = downgrade_flag

    def run(self):
        try:
            total = len(self.install_list)
            for i, (apk_path, pkg_name, version_code) in enumerate(self.install_list):
                progress = int((i / total) * 100)
                self.progress.emit(f"Installing {pkg_name}...", progress)
                
                success = pah.install_package(Path(apk_path), Path(self.tmp_dir), self.downgrade_flag)
                if success:
                    self.success.emit(pkg_name, version_code)
                    logging.info(f"Successfully installed {pkg_name} v{version_code}")
                else:
                    self.error.emit(f"Failed to install {pkg_name} v{version_code}")
                    
            self.progress.emit("Installation complete", 100)
            
        except Exception as e:
            self.error.emit(f"Installation error: {str(e)}")
        finally:
            self.finished.emit()


class UninstallWorker(QThread):
    progress = pyqtSignal(str, int)
    success = pyqtSignal(str, str)
    error = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, uninstall_list):
        super().__init__()
        self.uninstall_list = uninstall_list

    def run(self):
        try:
            total = len(self.uninstall_list)
            for i, (pkg_name, version_code) in enumerate(self.uninstall_list):
                progress = int((i / total) * 100)
                self.progress.emit(f"Uninstalling {pkg_name}...", progress)
                
                success = pah.uninstall_package(pkg_name)
                if success:
                    self.success.emit(pkg_name, version_code)
                else:
                    self.error.emit(f"Failed to uninstall {pkg_name} v{version_code}")
                    
            self.progress.emit("Uninstallation complete", 100)
            
        except Exception as e:
            self.error.emit(f"Uninstallation error: {str(e)}")
        finally:
            self.finished.emit()


class BackupWorker(QThread):
    progress = pyqtSignal(str, int)
    success = pyqtSignal(str, str)
    error = pyqtSignal(str)
    finished = pyqtSignal()
    cancelled = pyqtSignal()

    def __init__(self, backup_list, apk_dir):
        super().__init__()
        self.backup_list = backup_list
        self.apk_dir = apk_dir
        self._cancel_requested = False

    def request_cancel(self):
        self._cancel_requested = True

    def run(self):
        try:
            total = len(self.backup_list)
            for i, (pkg_name, version_code) in enumerate(self.backup_list):
                if self._cancel_requested:
                    self.cancelled.emit()
                    return
                    
                progress = int((i / total) * 100)
                self.progress.emit(f"Backing up {pkg_name}...", progress)
                
                try:
                    apk_file = pah.extract_package(pkg_name, version_code, Path(self.apk_dir))
                    if apk_file:
                        self.success.emit(pkg_name, version_code)
                    else:
                        self.error.emit(f"Failed to backup {pkg_name} v{version_code}")
                except Exception as e:
                    self.error.emit(f"Error backing up {pkg_name}: {str(e)}")
                    
            self.progress.emit("Backup complete", 100)
            
        except Exception as e:
            self.error.emit(f"Backup error: {str(e)}")
        finally:
            self.finished.emit()
