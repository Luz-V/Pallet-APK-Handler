import pah_logger
import logging
import tempfile
import subprocess

from pathlib import Path
from PyQt5.QtCore import Qt, QTimer, QEventLoop, QThread, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import QProgressDialog, QApplication

import pah_callbacks as pahc
import pah_utils as pahu

class InstallWorker(QThread):
    progress = pyqtSignal(str, int)  # message, percentage
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
            total = len(self.install_list)
            for i, (apk_path, pkg_name, version_code) in enumerate(self.install_list):
                progress = int((i / total) * 100)
                self.progress.emit(f"Installing {pkg_name}...", progress)

                success = install_package(Path(apk_path), Path(self.tmp_dir), self.downgrade_flag)
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

                success = uninstall_package(pkg_name)
                if success:
                    self.success.emit(pkg_name, version_code)
                else:
                    self.error.emit(f"Failed to uninstall {pkg_name} v{version_code}")

            self.progress.emit("Uninstallation complete", 100)

        except Exception as e:
            self.error.emit(f"Uninstallation error: {str(e)}")
        finally:
            self.finished.emit()


def on_install_clicked(main_window):
    logging.debug("on_install_clicked triggered")
    adb_check = pahu.check_adb_connection()
    if not adb_check:
        logging.error("\nNo adb connection detected : operation canceled")
        return 1
    pkg_map = main_window.package_map
    apk_dir = Path(__file__).parent / 'extracted_apks'
    tmp_dir = Path(tempfile.mkdtemp())
    install_list = []  # List of (apk_path, package_name, version_code)
    # Checking PackageMap instead of table
    for (pkg, vcode_int), info in pkg_map.get_all_packages().items():
        vcode = str(vcode_int)
        # List checked + not installed
        is_pkg_installed_or_unchecked = (
                not info.checked
                or info.android
        )
        is_pkg_installed_and_checked = (
                not info.checked
                and info.android
        )
        # Skip the unchecked
        if is_pkg_installed_or_unchecked:
            continue
        # Skip the check + installed with info
        # Skip the unchecked and the installed packages
        if is_pkg_installed_and_checked:
            if info.android:
                logging.info(f"{pkg} vcode {vcode} already installed, skipping.")
            continue
        # Consider the not installed + checked
        else:
            # check if newer version is installed
            newer_versions_installed = any(
                (other_pkg == pkg and other_vcode_int > vcode_int and other_info.android)
                for (other_pkg, other_vcode_int), other_info in pkg_map.get_all_packages().items()
            )
            # If so, suggest the downgrade option instead of install
            if newer_versions_installed:
                logging.info(
                    f"{pkg} v{vcode} ignored :\nnewer version installed, use the downgrade fonction if necessary")
                continue
            # If missing backups files
            elif not info.local:
                logging.error(f"\nNo local Apk(s) file for{pkg} v{vcode} : consider local rescan")
                continue
            # All conditions okay
            else:
                apk_name = f"{pkg}_{vcode}.apk"
                apk_path = apk_dir / apk_name
                apks_path = apk_path.with_suffix(apk_path.suffix + "s")
                if apk_path.exists():
                    install_list.append((apk_path, pkg, vcode))
                elif apks_path.exists():
                    install_list.append((apks_path, pkg, vcode))
                else:
                    logging.error(f"\nAPK/APKS not found for {pkg} v{vcode}")
    # Empty install_list
    if not install_list:
        logging.info("No packages to install.")
        return

    # 1 Displaying progress bar
    main_window.progress_dialog = QProgressDialog(
        "Installing on the device via ADB...\nUnlocking may help", "Cancel", 0, 100, main_window)
    main_window.progress_dialog.setWindowTitle("ADB Install")
    main_window.progress_dialog.setCancelButtonText("Cancel")
    main_window.progress_dialog.setWindowModality(Qt.WindowModal)
    main_window.progress_dialog.show()

    # 2 FORCE paint
    main_window.progress_dialog.repaint()
    QApplication.processEvents(QEventLoop.ExcludeUserInputEvents)

    # 3 Lauching worker
    main_window.worker = InstallWorker(install_list, tmp_dir, downgrade_flag=False)
    main_window.worker.progress.connect(
        lambda msg, percent: pahc.update_progress_dialog_percent(main_window, msg, percent))
    main_window.worker.error.connect(lambda errmsg: pahc.on_action_failed(main_window, "Install", errmsg))
    main_window.worker.success.connect(
        lambda pkg_installed, vcode_installed: _mark_installed(main_window, pkg_installed, vcode_installed))
    main_window.worker.finished.connect(main_window.progress_dialog.close)
    main_window.worker.finished.connect(lambda: _clear_selection(main_window))

    # 4 START WORKER SAFELY
    QTimer.singleShot(50, main_window.worker.start)


def on_update_clicked(main_window):
    logging.debug("Update clicked")
    adb_check = pahu.check_adb_connection()
    if not adb_check:
        logging.error("\nNo adb connection detected : operation canceled")
        return 1
    logging.debug("on_update_clicked triggered")
    pkg_map = main_window.package_map
    apk_dir = Path(__file__).parent / 'extracted_apks'
    tmp_dir = Path(tempfile.mkdtemp())
    update_list = []  # List of (apk_path, package_name, version_code)

    for (pkg, vcode_int), info in pkg_map.get_all_packages().items():
        vcode = str(vcode_int)
        # Keep only checked
        if not info.checked:
            continue

        # Verify if older version is installed
        older_installed = any(
            other_pkg == pkg and other_vcode_int < vcode_int and other_info.android
            for (other_pkg, other_vcode_int), other_info in pkg_map.get_all_packages().items()
        )
        if not older_installed:
            logging.info(f"{pkg} v{vcode}: No older version installed — skipping")
            continue

        # Verify if newer or actuel version is installed
        newer_or_equal_installed = any(
            other_pkg == pkg and other_vcode_int >= vcode_int and other_info.android
            for (other_pkg, other_vcode_int), other_info in pkg_map.get_all_packages().items()
        )
        if newer_or_equal_installed:
            logging.info(f"{pkg} v{vcode}: Newer or equal version already installed — skipping")
            continue

        # Verify local file
        apk_path = apk_dir / f"{pkg}_{vcode}.apk"
        apks_path = apk_path.with_suffix(apk_path.suffix + "s")
        if not (apk_path.exists() or apks_path.exists()):
            logging.error(f"APK/APKS not found for {pkg} v{vcode}. Consider local rescan.")
            continue

        # Adding to update list
        update_list.append((apk_path if apk_path.exists() else apks_path, pkg, vcode))

    logging.info(f"Update list prepared with {len(update_list)} packages")

    if not update_list:
        logging.info("No packages to update.")
        return

    main_window.progress_dialog = QProgressDialog(
        "Installing on the device via ADB...\nUnlocking may help",
        "Cancel", 0, 100, main_window)
    main_window.progress_dialog.setWindowTitle("ADB Update")
    main_window.progress_dialog.setCancelButtonText("Cancel")
    main_window.progress_dialog.setWindowModality(Qt.WindowModal)
    main_window.progress_dialog.show()

    # 2 FORCE paint
    main_window.progress_dialog.repaint()
    QApplication.processEvents(QEventLoop.ExcludeUserInputEvents)

    # Lauching worker
    main_window.worker = InstallWorker(update_list, tmp_dir, downgrade_flag=False)
    main_window.worker.progress.connect(lambda msg: pahc.update_progress_dialog(main_window, msg))
    main_window.worker.progress.connect(
        lambda msg, percent: pahc.update_progress_dialog_percent(main_window, msg, percent))
    main_window.worker.error.connect(lambda errmsg: pahc.on_action_failed(main_window, "Update", errmsg))
    main_window.worker.success.connect(
        lambda pkg_updated, vcode_updated: _mark_installed(main_window, pkg_updated, vcode_updated))
    main_window.worker.finished.connect(main_window.progress_dialog.close)
    main_window.worker.finished.connect(lambda: _clear_selection(main_window))

    # 4 START WORKER SAFELY
    QTimer.singleShot(50, main_window.worker.start)


def on_downgrade_clicked(main_window):
    logging.debug("on_downgrade_clicked triggered")
    adb_check = pahu.check_adb_connection()
    if not adb_check:
        logging.error("\nNo adb connection detected : operation canceled")
        return 1
    pkg_map = main_window.package_map
    apk_dir = Path(__file__).parent / 'extracted_apks'
    tmp_dir = Path(tempfile.mkdtemp())
    downgrade_list = []  # List of (apk_path, package_name, version_code)
    # Checking PackageMap instead of table
    for (pkg, vcode_int), info in pkg_map.get_all_packages().items():
        vcode = str(vcode_int)
        # List checked + not installed
        is_pkg_installed_or_unchecked = (
                not info.checked
                or info.android
        )
        # Skip the unchecked OR the installed packages
        if is_pkg_installed_or_unchecked:
            continue
        # Consider the not installed AND checked
        else:
            # check if newer version are installed
            newer_versions_installed = any(
                (other_pkg == pkg and other_vcode_int > vcode_int and other_info.android)
                for (other_pkg, other_vcode_int), other_info in pkg_map.get_all_packages().items()
            )
            # If not, no downgrade needed => suggest the instal option
            if not newer_versions_installed:
                logging.info(
                    f"No newer installed version (ot not at all) for {pkg} vcode {vcode}: \nuse the install fonction instead")
                continue
            # Ignore missing backups files
            elif not info.local:
                logging.error(f"\nNo local Apk(s) file for{pkg} v{vcode}")
                continue
            # All conditions okay
            else:
                apk_name = f"{pkg}_{vcode}.apk"
                apk_path = apk_dir / apk_name
                apks_path = apk_path.with_suffix(apk_path.suffix + "s")
                if apk_path.exists():
                    apk_name = f"{pkg}_{vcode}.apk"
                    apk_path = apk_dir / apk_name
                    apks_path = apk_path.with_suffix(apk_path.suffix + "s")
                if apk_path.exists():
                    downgrade_list.append((apk_path, pkg, vcode))
                elif apks_path.exists():
                    downgrade_list.append((apks_path, pkg, vcode))
                else:
                    logging.error(
                        f"[PAH]\nAPK/APKS not found for {pkg} v{vcode}.\nConsider local rescan")
    # Empty downgrade list
    if not downgrade_list:
        logging.info("No packages to downgrade.")
        return

    # Displaying progress bar
    main_window.progress_dialog = QProgressDialog(
        "Downgrading on the device via ADB...\nUnlocking may help", "Cancel", 0, 100, main_window)
    main_window.progress_dialog.setWindowTitle("ADB Install")
    main_window.progress_dialog.setWindowModality(Qt.WindowModal)
    main_window.progress_dialog.setCancelButtonText("Cancel")
    main_window.progress_dialog.show()

    # 2 FORCE paint
    main_window.progress_dialog.repaint()
    QApplication.processEvents(QEventLoop.ExcludeUserInputEvents)

    # launching worker
    main_window.worker = InstallWorker(downgrade_list, tmp_dir, downgrade_flag=True)
    main_window.worker.progress.connect(
        lambda msg, percent: pahc.update_progress_dialog_percent(main_window, msg, percent))
    main_window.worker.error.connect(lambda errmsg: pahc.on_action_failed(main_window, "Downgrade", errmsg))
    main_window.worker.success.connect(
        lambda pkg_downed, vcode_downed: _mark_installed(main_window, pkg_downed, vcode_downed))
    main_window.worker.finished.connect(main_window.progress_dialog.close)
    main_window.worker.finished.connect(lambda: _clear_selection(main_window))

    # 4 START WORKER SAFELY
    QTimer.singleShot(50, main_window.worker.start)


def on_uninstall_clicked(main_window, invert=False):
    logging.debug("Uninstall clicked")
    adb_check = pahu.check_adb_connection()
    if not adb_check:
        logging.error("\nNo adb connection detected : operation canceled")
        return 1
    uninstall_list = []
    # Checking PackageMap instead of table
    for (pkg, vcode_int), info in main_window.package_map.get_all_packages().items():
        vcode = str(vcode_int)
        is_installed = info.android
        is_checked = info.checked

        should_uninstall = (
                (not invert and is_installed and is_checked) or
                (invert and is_installed and not is_checked)
        )
        if should_uninstall:
            uninstall_list.append((pkg, vcode))

    if not uninstall_list:
        logging.info("No package to uninstall.")
        return

    # Displaying progress bar
    main_window.progress_dialog = QProgressDialog(
        "Uninstalling with ADB...\nUnlocking may help", "Cancel", 0, 100, main_window)
    main_window.progress_dialog.setWindowTitle("ADB Uninstall")
    main_window.progress_dialog.setCancelButtonText("Cancel")
    main_window.progress_dialog.setWindowModality(Qt.WindowModal)
    main_window.progress_dialog.show()

    # 2 FORCE paint
    main_window.progress_dialog.repaint()
    QApplication.processEvents(QEventLoop.ExcludeUserInputEvents)

    # Lauching worker
    main_window.worker = UninstallWorker(uninstall_list)
    main_window.worker.progress.connect(
        lambda msg, percent: pahc.update_progress_dialog_percent(main_window, msg, percent))
    main_window.worker.success.connect(
        lambda pkg_name_del, vcode_del: _mark_uninstalled(main_window, pkg_name_del, vcode_del))
    main_window.worker.error.connect(
        lambda errmsg: pahc.on_action_failed(main_window, "Uninstall", errmsg))
    main_window.worker.finished.connect(main_window.progress_dialog.close)
    main_window.worker.finished.connect(lambda: _clear_selection(main_window))
    main_window.worker.start()

    # 4 START WORKER SAFELY
    QTimer.singleShot(50, main_window.worker.start)

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


def _clear_selection(main_window):
    try:
        clear_selection(main_window)
    except Exception:
        pass


def _mark_installed(main_window, pkg: str, vcode: str) -> None:
    pkg_map = main_window.package_map
    info = pkg_map.get(pkg, vcode)
    if info:
        info.android = True
    if hasattr(main_window, "table_adapter"):
        main_window.table_adapter.refresh()
    save_file = pkg_map.get_save_file_path()
    pkg_map.save_to_file(save_file)


def _mark_uninstalled(main_window, pkg: str, vcode: str) -> None:
    pkg_map = main_window.package_map
    info = pkg_map.get(pkg, vcode)
    if info:
        info.android = False
    # Option: remove orphans handled by viewer after scan; keep entry to preserve local backups
    if hasattr(main_window, "table_adapter"):
        main_window.table_adapter.refresh()
    save_file = pkg_map.get_save_file_path()
    pkg_map.save_to_file(save_file)

def install_package(file: Path, tmpdir: Path, down_flag) -> bool:
     """Install an .apk or .apks file via adb. Returns True on success."""
     try:
        if file.suffix == ".apk":
            if not down_flag:
                # Install or update
                process = subprocess.run(["adb", "install", str(file)],
                                         capture_output=True, text=True)
            else:
                # Push + try downgrade with su
                push_cmd = subprocess.run(["adb", "push", str(file), "/data/local/tmp"],
                                          capture_output=True, text=True)
                process = subprocess.run(
                    ["adb", "shell", "su", "-c", "'pm install -r -d /data/local/tmp/" + str(file.name) + "'"],
                    capture_output=True, text=True)
            if process.stdout:
                logging.debug(f"[adb pm stdout]\n {process.stdout.strip()}")
            if process.stderr:
                pahu.raise_error(process.stderr.strip())
        elif file.suffix == ".apks":
            pahu.clean_tmp_dir(tmpdir)
            pahu.unzip_apks_to_tmpdir(file, tmpdir)
            apks_list = [str(p) for p in tmpdir.glob("*.apk")]
            if not down_flag:
                process = subprocess.run(["adb", "install-multiple"] + apks_list,
                                    capture_output=True, text=True)
            else:
                # Push + try downgrade with
                push_cmd = subprocess.run(["adb", "push", str(file), "/data/local/tmp"],
                                        capture_output=True, text=True)
                process = subprocess.run(
                    ["adb", "shell", "su", "-c",
                    "'pm install-multiple -r -d /data/local/tmp/" + str(file.name) + "'"],
                    capture_output=True, text=True)
            if process.stdout:
                logging.debug(f"[adb pm stdout]\n {process.stdout.strip()}")
            if process.stderr:
                pahu.raise_error(process.stderr.strip())
            pahu.clean_tmp_dir(tmpdir)
        else:
            pahu.raise_error(f"Unsupported file type: {file}")
        return True
     except subprocess.CalledProcessError:
        return False

def uninstall_package(package_name: str) -> bool:
    """Uninstall an app via adb using its package name. Returns True on success."""
    # Warning : adb uninstall failure return exit code 0
    # => details are stored in stdout and not stderr
    try:
        process = subprocess.run(["adb", "uninstall", package_name],
                                capture_output=True, text=True)
        if process.stdout:
            if not "Success" in process.stdout.strip():
                pahu.raise_error(process.stdout.strip())
            else:
                logging.debug(f"[adb uninstall stdout] {process.stdout.strip()}")
        return True
    except subprocess.CalledProcessError as e:
        pahu.raise_error(str(e))
        return False
