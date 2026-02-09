import pah_logger
import logging
import subprocess
import shlex

from pathlib import Path
from PyQt5.QtCore import Qt, QTimer, QEventLoop, QThread, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import QProgressDialog, QApplication

import pah_callbacks as pahc
import pah_utils as pahu
import pah_data as pahd

class ScanWorker(QThread):
    progress = pyqtSignal(str)
    progress_switch_percent = pyqtSignal()
    progress_percent = pyqtSignal(str, int)
    result_ready = pyqtSignal(object)
    error_occurred = pyqtSignal(str)
    android_scan_finished = pyqtSignal(str)

    def __init__(self, apk_installer_path: Path, package_map=None, parent=None,
                 installed_list=[], saved_list=[], android_scan=True, local_scan=True):
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
                is_adb_connected = pahu.check_adb_connection()
                if is_adb_connected:
                    self.progress.emit(
                        "Scanning Android installed applications...\n"
                        "Unlocking the device may help."
                    )
                    # 1) Scan device
                    self.installed_list = extract_packages_labels_version(
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

                    mapping = pahd.map_apk_files_to_packages(self.package_map, apk_dir, files_to_hash)
                    mapped_files = set(mapping.keys())

                    # Découvrir les nouveaux fichiers non mappés
                    unmapped_files = present_files - mapped_files

                    # Résoudre chaque fichier local : filename -> hash -> aapt
                    if unmapped_files:
                        tmp_dir = Path(__file__).parent / "tmp"
                        tmp_dir.mkdir(exist_ok=True)

                        for i, filename in enumerate(unmapped_files):
                            self.progress.emit(f"Scanning {filename} ({i + 1}/{len(unmapped_files)})")
                            apk_file = apk_dir / filename

                            try:
                                # 1) lookup par filename dans le JSON
                                matched_key = self.package_map.find_by_filename(filename)

                                # 2) fallback: lookup par hash
                                file_hash = pahu.get_fast_apk_hash(apk_file)
                                if not matched_key and file_hash:
                                    matched_key = self.package_map.find_by_hash(file_hash)

                                if matched_key:
                                    pkg, vcode_int = matched_key
                                    vcode_str = str(vcode_int)

                                    info = self.package_map.get(pkg, vcode_str)
                                    if info and not info.label:
                                        try:
                                            # tentative douce : extraire le label si possible
                                            _, _, label = extract_pkg_version_label(apk_file, tmp_dir)
                                            if label:
                                                info.label = label
                                        except Exception:
                                            pass  # surtout ne rien casser ici

                                    self.package_map.update_file_name(pkg, vcode_str, filename)
                                    if file_hash:
                                        self.package_map.update_file_hash(pkg, vcode_str, file_hash)
                                    continue

                                # 3) aapt scan si inconnu
                                pkg, vcode, label = extract_pkg_version_label(apk_file, tmp_dir)
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
                        file_hash = pahu.get_fast_apk_hash(apk_file)
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
                                        file_hash = pahu.get_fast_apk_hash(apk_file)
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
                        self.progress_percent.emit(f"Scanning unregistered local APK(s) files …\n{fname}",
                                                   int(index / total_rescans * 100))
                        apk = apk_dir / fname
                        logging.debug(f"scanning for {fname}")
                        try:
                            pkg, vcode, label = extract_pkg_version_label(apk, tmp_dir)
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


def on_scan_device_clicked(main_window, scan_android=True, scan_local=True, preserve_android_on_local_scan=True):
    main_table = main_window.tableWidget_2
    row_count = main_table.rowCount()
    local_saved_list = []  # tuples (package_name, version_code, label)
    android_installed_list = []  # tuples (package_name, version_code, label)

    # In case previous data needs to be saved before scan
    if not scan_android or not scan_local:
        for row in range(row_count):
            item_col3 = main_table.item(row, 3)  # android-installed check
            item_col4 = main_table.item(row, 4)  # local-backup check
            is_installed = item_col3 and item_col3.text().strip() == "✓"
            has_backup = item_col4 and item_col4.text().strip() == "✓"
            if scan_android and has_backup:
                # list local-saved packages in table and flush the rest
                package = main_table.item(row, 1).text().strip()
                version = main_table.item(row, 2).text().strip()
                label = main_table.item(row, 0).text().strip()
                local_saved_list.append((package, version, label))
            elif scan_local and is_installed and preserve_android_on_local_scan:
                # list android-installed packages in table and flush the rest
                package = main_table.item(row, 1).text().strip()
                version = main_table.item(row, 2).text().strip()
                label = main_table.item(row, 0).text().strip()
                android_installed_list.append((package, version, label))

    # Flush the table
    main_window.tableWidget_2.setRowCount(0)

    # Display progress bar
    main_window.progress_dialog = QProgressDialog(
        "Starting Applications scan ...", "Cancel", 0, 100, main_window
    )
    main_window.progress_dialog.setValue(0)
    main_window.progress_dialog.setWindowTitle("Scanning devices")
    main_window.progress_dialog.setWindowModality(Qt.WindowModal)
    main_window.progress_dialog.setCancelButtonText("Cancel")
    main_window.progress_dialog.show()

    # FORCE paint
    main_window.progress_dialog.repaint()
    QApplication.processEvents(QEventLoop.ExcludeUserInputEvents)

    # launching scan thread
    current_dir = Path(__file__).parent
    apk_path = current_dir / 'assets' / 'app-release.apk'

    main_window.worker = ScanWorker(
        apk_path,
        package_map=main_window.package_map,
        installed_list=android_installed_list,
        saved_list=local_saved_list,
        android_scan=scan_android,
        local_scan=scan_local,
    )

    main_window.worker.progress.connect(
        lambda msg: pahc.update_progress_dialog(main_window, msg)
    )
    main_window.worker.progress_switch_percent.connect(
        lambda: pahc.switch_progress_to_percent(main_window)
    )
    main_window.worker.progress_percent.connect(
        lambda msg, percent: pahc.update_progress_dialog_percent(main_window, msg, percent)
    )
    main_window.worker.android_scan_finished.connect(
        lambda msg: pahc.update_scan_message(main_window, msg)
    )
    main_window.worker.result_ready.connect(
        lambda pkg_dico: pahd.on_scan_finished(main_window, pkg_dico)
    )
    main_window.worker.error_occurred.connect(
        lambda errmsg: pahc.on_scan_failed(main_window, errmsg)
    )

    # START WORKER SAFELY
    QTimer.singleShot(50, main_window.worker.start)


# === Name, Label, VersionCode functions ===

def parse_aapt_output(aapt_output: str) -> tuple[str, str, str]:
    """
    Parse the output of 'aapt dump badging' to extract package name, version name, and label.
    Returns empty strings if not found.
    """
    package_name = ""
    version_code = ""
    label = ""
    for line in aapt_output.splitlines():
        if line.startswith("package:"):
            parts = line.split()
            for part in parts:
                if part.startswith("name=") and not package_name:
                    package_name = part.split("=")[1].strip("'")
                elif part.startswith("versionCode=") and not version_code:
                    version_code = part.split("=")[1].strip("'")
        elif "application-label:" in line and not label:
            label = line.split(":", 1)[1].strip().strip("'")
    return package_name, version_code, label

def extract_pkg_version_label(apk_file: Path, tmpdir: Path) -> tuple[str, str, str]:
    """
    Extract package name, version code, and application label from a local .apk or .apks file.
    For .apks, unzip and analyze all .apk inside.
    Args:
    - apk_file: Path to the .apk or .apks file.
    - tmpdir: Path to a temporary directory for extraction.
    Returns:
    - Tuple of (package_name, version_code, label).
    Raises:
    - PAHError if extraction fails.
    """
    pahu.clean_tmp_dir(tmpdir)
    
    # Variables locales à cette fonction - réinitialisées à chaque appel
    package_name = ""
    version_code = ""
    label = ""

    if apk_file.suffix == ".apk":
        result = subprocess.run(
            ["aapt", "dump", "badging", str(apk_file)],
            capture_output=True, text=True, check=True
        )
        aapt_output = result.stdout
        package_name, version_code, label = parse_aapt_output(aapt_output)

    elif apk_file.suffix == ".apks":
        pahu.unzip_apks_to_tmpdir(apk_file, tmpdir)
        apk_files_inside = list(tmpdir.glob("*.apk"))
        if not apk_files_inside:
            pahu.clean_tmp_dir(tmpdir)
            pahu.raise_error("No .apk found inside the .apks archive.")

        # Loop on all extracted APKs to find info (stop early if all found)
        for apk_inside in apk_files_inside:
            result = subprocess.run(
                ["aapt", "dump", "badging", str(apk_inside)],
                capture_output=True, text=True
            )
            aapt_output = result.stdout
            p, v, l = parse_aapt_output(aapt_output)
            if not package_name and p:
                package_name = p
            if not version_code and v:
                version_code = v
            if not label and l:
                label = l
            if package_name and version_code and label:
                break
    else:
        pahu.raise_error(f"Unsupported file type: {apk_file.suffix}")
    pahu.clean_tmp_dir(tmpdir)
    if not package_name:
        pahu.raise_error("Failed to extract package name.")
    if not version_code:
        logging.warning(f"VersionCode not found in {apk_file}. Version check disabled.")
    if not version_code:
        logging.warning(f"label not found in {apk_file}.")
    return package_name, version_code, label

def extract_user_packages_list() -> list[str]:
    """Return a list of all user-installed packages on the connected device."""
    adb_connect = pahu.check_adb_connection()
    if adb_connect:
        result = subprocess.run(
            ["adb", "shell", "pm", "list", "packages", "-3"],
            capture_output=True, text=True
        )
        lines = result.stdout.strip().splitlines()
        return [line.split(":")[1] for line in lines]
    else:
        logging.warning("Skipping android install listing.")
        return []

def extract_packages_labels_version(apk_installer_path: Path) -> list[tuple[str, str, str]]:
    """
    use miniapp on the android device to extract a list of installed packages.
    Return a tuple list : (package_name, version_code, label).
    """
    pkg_name = "com.pah.miniapp"
    remote_path = f"/storage/emulated/0/Android/data/{pkg_name}/files/miniapp_package_list.txt"
    local_file = Path(__file__).parent / "extracted_apks" / "android_extracted_list.txt"
    results = []

    installed = extract_user_packages_list()
    if not installed:
        logging.warning("No user-installed packages detected on device.")
        return results

    # Vérifie si miniapp est installée
    if pkg_name not in installed:
        try:
            subprocess.run(["adb", "install", str(apk_installer_path)], check=True)
            logging.info("miniapp installed successfully.")
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to install miniapp: {e}") from e

    # Lancer l’activité principale
    try:
        subprocess.run([
            "adb", "shell", "monkey", "-p", pkg_name,
            "-c", "android.intent.category.LAUNCHER", "1"
        ], capture_output=True, check=True)
        logging.info("miniapp launched.")
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to launch miniapp: {e}") from e

    # Wait before reading list file
    max_attempts = 10
    delay = 2.0
    for attempt in range(max_attempts):
        time.sleep(delay)
        res = subprocess.run(["adb", "shell", "ls", remote_path],
                             capture_output=True, text=True)
        logging.debug(f"[shell ls] {res.stdout.strip()}")
        if "No such file" not in res.stdout:
            break
        logging.debug(f"Waiting for file... ({attempt+1}/{max_attempts})")
    else:
        raise RuntimeError("Timeout (10s): miniapp_package_list.txt not found on device.")

    # Pull list file
    try:
        res2 = subprocess.run(["adb", "pull", remote_path, str(local_file)],
                             capture_output=True, check=True)
        logging.debug(f"[adb pull] {res2.stdout.strip()}")
        logging.info(f"Pulled file {local_file.name}")
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to pull file: {e}") from e

    # Reading and parsing
    try:
        with local_file.open('r', encoding='utf-8') as f:
            for line in f:
                parts = line.strip().split(None, 2)
                if len(parts) >= 2:
                    pkg = parts[0]
                    version = parts[1]
                    label = parts[2] if len(parts) > 2 else ""
                    results.append((pkg, version, label))
    except Exception as e:
        raise RuntimeError(f"Failed to parse pulled file: {e}") from e

    return results


def read_meta_info(meta_file: Path) -> tuple[str, bool]:
    """Read package_name and is_split_apk from a meta_v2.am.json file."""
    import json
    data = json.loads(meta_file.read_text())
    pkg = data.get("package_name", "")
    is_split = bool(data.get("is_split_apk", False))
    return pkg, is_split
