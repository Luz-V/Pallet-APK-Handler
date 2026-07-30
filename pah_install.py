import logging
import tempfile
import subprocess

from pathlib import Path
from PyQt5.QtCore import QTimer, QThread, pyqtSignal

import pah_callbacks as pahc
import pah_utils as pahu

class InstallWorker(QThread):
    progress = pyqtSignal(str)  # message, percentage
    success = pyqtSignal(str, str)  # package_name, version_code
    error = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, install_list, tmp_dir, downgrade_flag=False):
        super().__init__()
        self.install_list = install_list
        self.tmp_dir = tmp_dir
        self.downgrade_flag = downgrade_flag

    def run(self):
        try:
            if not self.install_list:
                self.progress.emit("Nothing to install")
                self.finished.emit()
                return

            total = len(self.install_list)

            for i, (apk_path, pkg_name, version_code) in enumerate(self.install_list):
                self.progress.emit(f"Installing {pkg_name} ({i}/{total})...")

                success = install_package(
                    Path(apk_path),
                    Path(self.tmp_dir),
                    self.downgrade_flag
                )
                if success:
                    self.success.emit(pkg_name, version_code)
                    logging.info(f"{pkg_name} v{version_code} : Installed")
                else:
                    self.error.emit(f"{pkg_name} v{version_code} : Failed")

            self.progress.emit("Installation complete")

        except Exception as e:
            self.error.emit(f"Installation error: {str(e)}")

        finally:
            self.finished.emit()

class UninstallWorker(QThread):
    progress = pyqtSignal(str,int)
    success = pyqtSignal(str, str)
    error = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, uninstall_list):
        super().__init__()
        self.uninstall_list = uninstall_list

    def run(self):
        try:
            if not self.uninstall_list:
                self.progress.emit("Nothing to uninstall", 100)
                self.finished.emit()
                return

            total = len(self.uninstall_list)

            for i, (pkg_name, version_code) in enumerate(self.uninstall_list):
                percent = int(i / total * 100)
                self.progress.emit(f"Uninstalling {pkg_name} ({i+1}/{total})...",percent)
                success = uninstall_package(pkg_name)
                if success:
                    self.success.emit(pkg_name, version_code)
                    logging.info(f"Uninstalled {pkg_name} v{version_code}")
                else:
                    self.error.emit(f"Failed {pkg_name} v{version_code}")

            self.progress.emit("Uninstallation complete",100)

        except Exception as e:
            self.error.emit(f"Uninstallation error: {str(e)}")

        finally:
            self.finished.emit()

def _resolve_local_backup_path(apk_dir: Path, info, pkg: str, vcode: str):
    candidates = []

    if info and info.file_name:
        candidates.append(apk_dir / info.file_name)

    candidates.append(apk_dir / f"{pkg}_{vcode}.apk")
    candidates.append(apk_dir / f"{pkg}_{vcode}.apks")

    for path in candidates:
        if path.exists():
            return path

    return None

def on_install_clicked(main_window):
    logging.debug("on_install_clicked triggered")

    if not pahu.check_adb_connection():
        logging.error("No adb connection detected")
        pahc.set_status(main_window, "ADB not connected")
        return

    pkg_map = main_window.package_map
    apk_dir = Path(__file__).parent / 'extracted_apks'
    tmp_dir = Path(tempfile.mkdtemp())
    install_list = []  # List of (apk_path, package_name, version_code)

    # Checking PackageMap instead of table
    for (pkg, vcode_int), info in pkg_map.get_all_packages().items():
        vcode = str(vcode_int)

        # UI STATE ONLY
        if not main_window.table_adapter.is_checked(pkg, vcode):
            continue

        # model state (still valid)
        if info.android:
            logging.info(f"{pkg} v{vcode} already installed, skipping.")
            continue

        if not info.local:
            logging.error(f"{pkg} v{vcode} : No local APK backup, skipping.")
            continue

        newer_versions_installed = any(
            (other_pkg == pkg and other_vcode_int > vcode_int and other_info.android)
            for (other_pkg, other_vcode_int), other_info in pkg_map.get_all_packages().items()
        )
        if newer_versions_installed:
            logging.info(f"{pkg} v{vcode} : newer version installed, skipping")
            continue

        apk_path = _resolve_local_backup_path(apk_dir, info, pkg, vcode)
        if apk_path:
            install_list.append((apk_path, pkg, vcode))
        else:
            logging.error(f"\nAPK/APKS not found for {pkg} v{vcode}")

    # Empty install_list
    if not install_list:
        logging.info("No packages to install.")
        return

    # UI INIT
    pahc.set_progress_indeterminate(main_window)
    pahc.set_status(main_window, "Starting installation via ADB (Unlocking may help) ...")

    # 3 Lauching worker
    main_window.worker = InstallWorker(install_list, tmp_dir, downgrade_flag=False)
    main_window.worker.progress.connect(lambda msg: pahc.set_status(main_window, msg))
    main_window.worker.error.connect(lambda errmsg: pahc.on_action_failed(main_window, "Install", errmsg))
    main_window.worker.success.connect(
        lambda pkg_installed, vcode_installed: _mark_installed(main_window, pkg_installed, vcode_installed))
    main_window.worker.finished.connect(
        lambda: (
            pahc.set_status(main_window, "Installation finished"),
            pahc.reset_progress(main_window),
            QTimer.singleShot(0, main_window.table_adapter.clear_selection)
        )
    )
    # 4 START WORKER SAFELY
    QTimer.singleShot(50, main_window.worker.start)

def _mark_installed(main_window, pkg: str, vcode: str) -> None:
    pkg_map = main_window.package_map
    target_vcode = int(vcode)

    if not pkg_map.exists(pkg, vcode):
        pkg_map.add(pkg, vcode, label="", android=True, local=False, checked=False)

    for (other_pkg, other_vcode), info in pkg_map.get_all_packages().items():
        if other_pkg != pkg:
            continue

        if other_vcode == target_vcode:
            info.android = True
            main_window.table_adapter.set_checked(pkg, str(other_vcode), False)
        else:
            info.android = False

    for (other_pkg, other_vcode), info in list(pkg_map.get_all_packages().items()):
        if other_pkg == pkg and not info.local and not info.android:
            pkg_map.remove(other_pkg, str(other_vcode))

    main_window.table_adapter.refresh()
    pkg_map.save_to_file(pkg_map.get_save_file_path())

def on_update_clicked(main_window):
    logging.debug("Update clicked")

    if not pahu.check_adb_connection():
        logging.error("\nNo adb connection detected : operation canceled")
        return 1

    logging.debug("on_update_clicked triggered")
    pkg_map = main_window.package_map
    apk_dir = Path(__file__).parent / 'extracted_apks'
    tmp_dir = Path(tempfile.mkdtemp())
    update_list = []  # List of (apk_path, package_name, version_code)

    for (pkg, vcode_int), info in pkg_map.get_all_packages().items():
        vcode = str(vcode_int)

        if not main_window.table_adapter.is_checked(pkg, vcode):
            continue

        # On met à jour seulement si une version plus ancienne est déjà installée
        older_installed = any(
            other_pkg == pkg and other_vcode_int < vcode_int and other_info.android
            for (other_pkg, other_vcode_int), other_info in pkg_map.get_all_packages().items()
        )
        if not older_installed:
            logging.info(f"{pkg} v{vcode}: No older version installed — skipping")
            continue

        # Il faut bien une sauvegarde locale
        if not info.local:
            logging.error(f"APK/APKS not found for {pkg} v{vcode}. Consider local rescan.")
            continue

        # Verify local file
        apk_path = _resolve_local_backup_path(apk_dir, info, pkg, vcode)
        if apk_path:
            update_list.append((apk_path, pkg, vcode))
        else:
            logging.error(f"\nAPK/APKS not found for {pkg} v{vcode}")

    logging.info(f"Update list prepared with {len(update_list)} packages")

    if not update_list:
        logging.info("No packages to update.")
        return

    pahc.set_progress_indeterminate(main_window)
    pahc.set_status(main_window, "Starting update via ADB (Unlocking may help) ...")

    # Lauching worker
    main_window.worker = InstallWorker(update_list, tmp_dir, downgrade_flag=False)
    main_window.worker.progress.connect(lambda msg: pahc.set_status(main_window, msg))
    main_window.worker.error.connect(
        lambda errmsg: pahc.on_action_failed(main_window, "Update", errmsg)
    )
    main_window.worker.success.connect(
        lambda pkg_updt, vcode_updt: _mark_installed(main_window, pkg_updt, vcode_updt)
    )
    main_window.worker.finished.connect(
        lambda: (
            pahc.set_status(main_window, "Update finished"),
            pahc.reset_progress(main_window),
            QTimer.singleShot(0, main_window.table_adapter.clear_selection)
        )
    )

    # 4 START WORKER SAFELY
    QTimer.singleShot(50, main_window.worker.start)


def on_downgrade_clicked(main_window):
    logging.debug("on_downgrade_clicked triggered")

    if not pahu.check_adb_connection():
        logging.error("\nNo adb connection detected : operation canceled")
        return 1
    pkg_map = main_window.package_map
    apk_dir = Path(__file__).parent / 'extracted_apks'
    tmp_dir = Path(tempfile.mkdtemp())
    downgrade_list = []  # List of (apk_path, package_name, version_code)
    # Checking PackageMap instead of table
    for (pkg, vcode_int), info in pkg_map.get_all_packages().items():
        vcode = str(vcode_int)

        # Only checked packages
        if not main_window.table_adapter.is_checked(pkg, vcode):
            continue
        if info.android:
            continue
        if not info.local:
            logging.error(f"{pkg} v{vcode} : No local Apk(s) file")
            continue
        newer_versions_installed = any(
            (other_pkg == pkg and other_vcode_int > vcode_int and other_info.android)
            for (other_pkg, other_vcode_int), other_info in pkg_map.get_all_packages().items()
        )
        if not newer_versions_installed:
            logging.info(
                f"{pkg} v{vcode}: No newer installed version (or not at all)."
                f"use the install function instead"
            )
            continue

        apk_path = _resolve_local_backup_path(apk_dir, info, pkg, vcode)
        if apk_path:
            downgrade_list.append((apk_path, pkg, vcode))
        else:
            logging.error(f"{pkg} v{vcode} : APK/APKS not found for .Consider local rescan")

    # Empty downgrade list
    if not downgrade_list:
        logging.info("No packages to downgrade.")
        return

    # Displaying progress bar
    pahc.set_progress_determinate(main_window)
    pahc.set_progress_value(main_window, 0)
    pahc.set_status(main_window, "Starting downgrade...")

    # launching worker
    main_window.worker = InstallWorker(downgrade_list, tmp_dir, downgrade_flag=True)
    main_window.worker.progress.connect(lambda msg: pahc.set_status(main_window, msg))
    main_window.worker.error.connect(lambda errmsg: pahc.on_action_failed(main_window, "Downgrade", errmsg))
    main_window.worker.success.connect(
        lambda pkg_downed, vcode_downed: _mark_installed(main_window, pkg_downed, vcode_downed))

    main_window.worker.finished.connect(
        lambda: (
            pahc.set_status(main_window, "Installation finished"),
            pahc.reset_progress(main_window),
            QTimer.singleShot(0, main_window.table_adapter.clear_selection)
        )
    )

    # 4 START WORKER SAFELY
    QTimer.singleShot(50, main_window.worker.start)

def install_package(file: Path, tmpdir: Path, down_flag) -> bool:
    """Install an .apk or .apks file via adb. Returns True on success."""
    try:
        if file.suffix == ".apk":
            if not down_flag:
                logging.debug(f"ADB : adb install {file}")
                process = subprocess.run(
                    ["adb", "install", str(file)],
                    capture_output=True,
                    text=True,
                )
            else:
                logging.debug(f"Downgrade {file} : may be unstable")
                logging.debug(f"ADB : adb push {file} /data/local/tmp")
                subprocess.run(
                    ["adb", "push", str(file), "/data/local/tmp"],
                    capture_output=True,
                    text=True,
                )
                logging.debug(f"ADB : adb shell su -c  pm install -r -d /data/local/tmp/{file.name}")
                process = subprocess.run(
                    ["adb", "shell", "su", "-c", f"pm install -r -d /data/local/tmp/{file.name}"],
                    capture_output=True,
                    text=True,
                )

        elif file.suffix == ".apks":
            logging.debug(f"apks file : preparing install-multiple")
            pahu.clean_tmp_dir(tmpdir)
            pahu.unzip_apks_to_tmpdir(file, tmpdir)
            apks_list = [str(p) for p in tmpdir.glob("*.apk")]

            if not down_flag:
                logging.debug(f"ADB : adb install-multiple [...]")
                process = subprocess.run(
                    ["adb", "install-multiple"] + apks_list,
                    capture_output=True,
                    text=True,
                )
            else:
                logging.debug(f"Downgrade {file} : may be unstable")
                logging.debug(f"ADB : adb push {file} /data/local/tmp")
                subprocess.run(
                    ["adb", "push", str(file), "/data/local/tmp"],
                    capture_output=True,
                    text=True,
                )
                logging.debug(f"ADB : adb shell su -c  pm install-multiple -r -d /data/local/tmp/{file.name}")
                process = subprocess.run(
                    ["adb", "shell", "su", "-c", f"pm install-multiple -r -d /data/local/tmp/{file.name}"],
                    capture_output=True,
                    text=True,
                )
            pahu.clean_tmp_dir(tmpdir)
        else:
            logging.error(f"Unsupported file type: {file}")
            return False

        out = (process.stdout or "").strip()
        err = (process.stderr or "").strip()

        if out:
            logging.debug(f"[adb stdout]\n{out}")
        if err:
            logging.debug(f"[adb stderr]\n{err}")

        # adb can sent "Success" to stdout
        if process.returncode == 0 and ("Success" in out or not err):
            logging.debug(f"install successful")
            return True

        logging.error(f"Install failed for {file.name}: {out or err}")
        return False

    except Exception as e:
        logging.error(f"Install error for {file.name}: {e}")
        return False

def _mark_uninstalled(main_window, pkg: str, vcode: str) -> None:
    pkg_map = main_window.package_map
    target_vcode = str(vcode)

    for (other_pkg, other_vcode), info in pkg_map.get_all_packages().items():
        if other_pkg == pkg and str(other_vcode) == target_vcode:
            info.android = False

            # 🔥 si plus rien ne justifie l'existence
            if not info.local:
                pkg_map.remove(other_pkg, other_vcode)

    main_window.table_adapter.refresh()
    pkg_map.save_to_file(pkg_map.get_save_file_path())

def on_uninstall_clicked(main_window, invert=False):
    logging.debug("Uninstall clicked")

    if not pahu.check_adb_connection():
        logging.error("\nNo adb connection detected : operation canceled")
        return 1

    uninstall_list = []

    # Checking PackageMap instead of table
    for (pkg, vcode_int), info in main_window.package_map.get_all_packages().items():
        vcode = str(vcode_int)
        is_installed = info.android
        is_checked = main_window.table_adapter.is_checked(pkg, vcode)

        should_uninstall = (
                (not invert and is_installed and is_checked) or
                (invert and is_installed and not is_checked)
        )
        if should_uninstall:
            uninstall_list.append((pkg, vcode))

    if not uninstall_list:
        logging.info("No package to uninstall.")
        return

    # UI
    pahc.set_progress_determinate(main_window)
    pahc.set_progress_value(main_window, 0)
    pahc.set_status(main_window, "Starting uninstall...")

    # Lauching worker
    main_window.worker = UninstallWorker(uninstall_list)
    main_window.worker.progress.connect(lambda msg,percent: (
        pahc.set_status(main_window, msg),
        pahc.set_progress_value(main_window, percent)
        )
    )
    main_window.worker.success.connect(
        lambda pkg_name_del, vcode_del: _mark_uninstalled(main_window, pkg_name_del, vcode_del))
    main_window.worker.error.connect(
        lambda errmsg: pahc.on_action_failed(main_window, "Uninstall", errmsg))
    main_window.worker.finished.connect(
        lambda: (
            pahc.set_status(main_window, "Uninstall finished"),
            pahc.reset_progress(main_window),
            QTimer.singleShot(0, main_window.table_adapter.clear_selection)
        )
    )
    # 4 START WORKER SAFELY
    QTimer.singleShot(50, main_window.worker.start)

def uninstall_package(package_name: str) -> bool:
    """Uninstall an app via adb using its package name. Returns True on success."""
    try:
        process = subprocess.run(
            ["adb", "uninstall", package_name],
            capture_output=True,
            text=True
        )

        output = (process.stdout or "").strip()
        error = (process.stderr or "").strip()

        logging.debug(f"[adb uninstall stdout] {output}")
        if error:
            logging.debug(f"[adb uninstall stderr] {error}")

        if process.returncode == 0 and "Success" in output:
            return True

        logging.error(f"Uninstall failed for {package_name}: {output or error}")
        return False

    except Exception as e:
        logging.error(f"Uninstall exception for {package_name}: {e}")
        return False

## NOT USED
def uninstall_package_from_list(del_list: list[str], installed_list: list[str]) -> None:
    """Uninstall packages in both del_list (marked to uninstall) and installed_list (present on the device)."""
    for pkg in del_list:
        if pkg in installed_list:
            subprocess.run(["adb", "uninstall", pkg])
## NOT USED
def uninstall_package_not_in_list(keep_list: list[str], installed_list: list[str]) -> None:
    """Uninstall packages not in keep_list from installed_list."""
    for pkg in installed_list:
        if pkg not in keep_list:
            subprocess.run(["adb", "uninstall", pkg])


