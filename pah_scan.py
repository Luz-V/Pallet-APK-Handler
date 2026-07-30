import logging
import subprocess
import time

from pathlib import Path
from PyQt5.QtCore import QTimer, QThread, pyqtSignal

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
    finished = pyqtSignal(str)

    def __init__(self, apk_installer_path: Path, package_map=None,
                 parent=None, android_scan=True, local_scan=True, rebuild_aapt_dict=False):
        super().__init__(parent)
        self.apk_installer_path = apk_installer_path
        self.package_map = package_map
        self.android_scan = android_scan
        self.local_scan = local_scan
        self.rebuild_aapt_dict = rebuild_aapt_dict


    # -----------------------------
    # APK processing (LOCAL ONLY)
    # -----------------------------
    def _process_apk_file(self, working_map, apk_file: Path):
        try:
            filename = apk_file.name
            file_hash = pahu.get_fast_apk_hash(apk_file)

            # 1. fast match (filename / hash)
            matched_key = None
            if not self.rebuild_aapt_dict:
                if file_hash:
                    matched_key = working_map.find_by_hash(file_hash)
                if matched_key is None:
                    matched_key = working_map.find_by_filename(filename)

                if matched_key:
                    pkg, vcode_int = matched_key
                    info = working_map.get(pkg, str(vcode_int))
                    if info:
                        info.local = True
                        info.file_name = filename
                        if file_hash:
                            info.file_hash = file_hash
                    return

            # 2. fallback aapt extraction
            tmp_dir = Path(__file__).parent / "tmp"
            pkg, vcode, label = extract_pkg_version_label(apk_file, tmp_dir)
            existing = working_map.get(pkg, vcode)

            if existing and not self.rebuild_aapt_dict:
                existing.label = label or existing.label
                existing.local = True
                existing.file_name = filename
                if file_hash:
                    existing.file_hash = file_hash
            else:
                working_map.add(
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
            logging.error(f"Error scanning {apk_file.name}: {e}")

    # -----------------------------
    # MAIN
    # -----------------------------
    def run(self):
        try:
            # =========================================================
            # 0. WORKING COPY (CRITICAL FIX)
            # =========================================================
            working_map = pahd.PackageMap()

            for (pkg, vcode_int), info in self.package_map.get_all_packages().items():
                working_map.add(
                    pkg,
                    str(vcode_int),
                    label=info.label,
                    android=False,
                    local=info.local,
                    checked=False,
                    file_hash=info.file_hash,
                    file_name=info.file_name,
                )

            apk_dir = Path(__file__).parent / "extracted_apks"
            apk_dir.mkdir(exist_ok=True)

            tmp_dir = Path(__file__).parent / "tmp"
            tmp_dir.mkdir(exist_ok=True)

            # =========================================================
            # 1. ANDROID SCAN
            # =========================================================
            self.installed_list = []

            if self.android_scan:
                is_adb_connected = pahu.check_adb_connection()
                self.progress.emit("Scanning Android installed applications...")

                if is_adb_connected:
                    self.installed_list = extract_packages_labels_version(
                        self.apk_installer_path
                    )
                    self.android_scan_finished.emit("Android scan complete")
                else:
                    logging.error("No adb connection detected")

                installed_keys = set()

                for pkg, vcode, label in self.installed_list:
                    key = (pkg, int(vcode))

                    if key in installed_keys:
                        continue
                    installed_keys.add(key)

                    existing = working_map.get(pkg, vcode)

                    if existing:
                        existing.android = True
                        if label and not existing.label:
                            existing.label = label
                    else:
                        working_map.add(
                            pkg,
                            vcode,
                            label=label,
                            android=True,
                            local=False,
                            checked=False,
                        )
                for (_, _), info in working_map.get_all_packages().items():
                    info.local = False

                installed_keys = {(pkg, int(vcode)) for pkg, vcode, _ in self.installed_list}
                for (pkg, vcode_int), info in working_map.get_all_packages().items():
                    if (pkg, vcode_int) not in installed_keys:
                        info.android = False
                self.progress.emit(f"Android scan successful")


            # =========================================================
            # 2. LOCAL SCAN
            # =========================================================
            self.saved_list = []
            self.progress_switch_percent.emit()

            if self.local_scan:
                self.progress.emit("Scanning local APK files...")
                self.progress_switch_percent.emit()

                apk_files = list(apk_dir.glob("*.apk")) + list(apk_dir.glob("*.apks"))
                total = len(apk_files)
                existing_files = {f.name for f in apk_files}

                # purge des références mortes
                for (_, _), info in working_map.get_all_packages().items():
                    if info.file_name and info.file_name not in existing_files:
                        info.file_name = ""
                        info.file_hash = ""
                        info.local = False

                # reset local flag ONLY
                for (_, _), info in working_map.get_all_packages().items():
                    info.local = False

                for i, apk_file in enumerate(apk_files, 1):
                    self._process_apk_file(working_map, apk_file)

                    percent = int((i / total) * 100) if total else 0
                    self.progress_percent.emit(f"Scanning {apk_file.name} ({i}/{total})...", percent)

                self.saved_list = [
                    (pkg, str(vcode_int), info.label)
                    for (pkg, vcode_int), info in working_map.get_all_packages().items()
                    if info.local
                ]
                self.progress.emit(f"Local scan successful")

            # =========================================================
            # 3. RESULT CLEANUP (NO GLOBAL MUTATION)
            # =========================================================
            working_map.remove_orphans()

            # =========================================================
            # 4. EMIT RESULT (SAFE COPY)
            # =========================================================
            result_map = pahd.PackageMap()

            for (pkg, vcode_int), info in working_map.get_all_packages().items():
                result_map.add(
                    pkg,
                    str(vcode_int),
                    label=info.label,
                    android=info.android,
                    local=info.local,
                    checked=info.checked,
                    file_hash=info.file_hash,
                    file_name=info.file_name,
                )


            self.result_ready.emit(result_map)
            if self.android_scan and self.local_scan:
                self.finished.emit(
                    f"Combined scan finished : "
                    f"{len(self.saved_list)} local backups and "
                    f"{len(self.installed_list)} installed packages.")
            elif self.android_scan and not self.local_scan:
                self.finished.emit(
                    f"Android scan finished : "
                    f"{len(self.installed_list)} installed packages.")
            elif not self.android_scan and self.local_scan:
                self.finished.emit(
                    f"Local scan finished : "
                    f"{len(self.saved_list)} local backups.")
            logging.info("Scan finished successfully")


        except Exception as e:
            self.error_occurred.emit(f"Scan error: {str(e)}")
            logging.error(f"Scan error: {str(e)}")

# === Name, Label, VersionCode functions ===
def on_scan_device_clicked(main_window, scan_android=True, scan_local=True, reset_appt_dict=False):

    pahc.set_progress_indeterminate(main_window)  # ← dès le départ
    pahc.set_status(main_window, "Starting applications scan...")

    current_dir = Path(__file__).parent
    apk_path = current_dir / 'assets' / 'app-release.apk'

    main_window.worker = ScanWorker(
        apk_path,
        package_map=main_window.package_map,
        android_scan=scan_android,
        local_scan=scan_local,
        rebuild_aapt_dict=reset_appt_dict,
    )

    main_window.worker.progress.connect(
        lambda msg: pahc.set_status(main_window, msg)
    )
    main_window.worker.progress_switch_percent.connect(
        lambda: pahc.set_progress_determinate(main_window)
    )
    main_window.worker.progress_percent.connect(
        lambda msg, percent: (
            pahc.set_progress_determinate(main_window),
            pahc.set_progress_value(main_window, percent),
            pahc.set_status(main_window, msg)
        )
    )
    main_window.worker.android_scan_finished.connect(
        lambda msg: pahc.set_status(main_window, msg)
    )
    main_window.worker.result_ready.connect(
        lambda pkg_dico: pahd.on_scan_finished(main_window, pkg_dico)
    )
    main_window.worker.finished.connect(
        lambda msg: (QTimer.singleShot(0, lambda: (
            pahc.set_status(main_window, msg),
            pahc.reset_progress(main_window),
            main_window.table_adapter.clear_selection)
        ))
    )
    main_window.worker.error_occurred.connect(
        lambda errmsg: pahc.on_scan_failed(main_window, errmsg)
    )

    QTimer.singleShot(50, main_window.worker.start)

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
    logging.debug(f"cleaning tmpdir")
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

    # Strating main activity from miniapp
    try:
        subprocess.run([
            "adb", "shell", "am", "start", "-n",
            "com.pah.miniapp/.MainActivity"
        ], capture_output=True, check=True)
        logging.info("miniapp launched (main activity).")
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to launch miniapp: {e}") from e

    # Wait before reading list file
    max_attempts = 10
    delay = 1.0
    last_size = -1
    for attempt in range(max_attempts):
        time.sleep(delay)
        logging.debug(f"adb check repport size via [shell stat -c %s]")
        logging.debug(f"Attempt {attempt+1}/{max_attempts}")
        res = subprocess.run(
            ["adb", "shell", "stat", "-c", "%s", remote_path],
            capture_output=True,
            text=True
        )
        try:
            size = int(res.stdout.strip())
        except:
            logging.debug(f"Scan repport not ready yet ({attempt+1}/{max_attempts})")
            continue
        logging.debug(f"file size : {size} bytes")

        if size > 0 and size == last_size:
            logging.info("File is stable, ready to pull")
            break
        last_size = size
    else:
        raise RuntimeError("Timeout (30s): Scan repport miniapp_package_list.txt not found on device.")

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

# Not used yet (NeoBackup)
def read_meta_info(meta_file: Path) -> tuple[str, bool]:
    """Read package_name and is_split_apk from a meta_v2.am.json file."""
    import json
    data = json.loads(meta_file.read_text())
    pkg = data.get("package_name", "")
    is_split = bool(data.get("is_split_apk", False))
    return pkg, is_split
