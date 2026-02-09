import logging
import os
import subprocess

from pathlib import Path
from PyQt5.QtCore import Qt, QEventLoop
from PyQt5.QtWidgets import QProgressDialog, QApplication

import pah_callbacks as pahc
import pah_workers as pahw
import pah_utils as pahu

def on_backup_clicked(main_window):
    logging.debug("on_backup_clicked triggered")
    adb_check = pahu.check_adb_connection()
    if not adb_check:
        logging.error("\nNo adb connection detected : operation canceled")
        return 1

    # Status bar
    main_window.progress_dialog = QProgressDialog("Importing APK(s) ...", "Cancel", 0, 100, main_window)
    main_window.progress_dialog.setModal(True)
    main_window.progress_dialog.setValue(0)
    main_window.progress_dialog.setWindowTitle("ADB pull")
    main_window.progress_dialog.setCancelButtonText("Cancel")
    main_window.progress_dialog.setWindowModality(Qt.WindowModal)
    main_window.progress_dialog.show()

    # 2 FORCE paint
    main_window.progress_dialog.repaint()
    QApplication.processEvents(QEventLoop.ExcludeUserInputEvents)

    apk_dir = Path(__file__).parent / 'extracted_apks'
    backup_list = []

    # Checking PackageMap instead of table
    for (pkg, vcode_int), info in main_window.package_map.get_all_packages().items():
        vcode = str(vcode_int)
        is_checked = info.checked

        # Filtering :
        # Excluding unchecked packages,
        if not is_checked:
            continue
        # Excluding not installed packages,
        elif not info.android:
            logging.error(
                f"\nNo android package to import for {pkg} vcode {vcode}. Consider android rescan")
            continue
        # Excluding saved packages
        elif info.local:
            logging.info(f"package {pkg} vcode {vcode} already saved, skipping.")
            continue
        else:
            backup_list.append((pkg, vcode))

    if not backup_list:
        logging.info("No package to import.")
        main_window.progress_dialog.close()
        return

    # Lauching worker
    main_window.worker = pahw.BackupWorker(backup_list, apk_dir)
    main_window.worker.progress.connect(
        lambda msg, percent: pahc.update_progress_dialog_percent(main_window, msg, percent))
    main_window.worker.success.connect(
        lambda pkg_name_bak, vcode_bak: _mark_saved(main_window, pkg_name_bak, vcode_bak))
    main_window.worker.finished.connect(main_window.progress_dialog.close)
    main_window.worker.finished.connect(lambda: _clear_selection(main_window))
    main_window.worker.error.connect(
        lambda errmsg: pahc.on_action_failed(main_window, "Import", errmsg))
    main_window.progress_dialog.canceled.connect(main_window.worker.request_cancel)
    main_window.worker.cancelled.connect(main_window.progress_dialog.close)
    main_window.worker.start()

    # 2 FORCE paint
    main_window.progress_dialog.repaint()
    QApplication.processEvents(QEventLoop.ExcludeUserInputEvents)


def on_delete_clicked(main_window):
    logging.debug("on_delete_clicked triggered")
    apk_dir = Path(__file__).parent / 'extracted_apks'
    pkg_map = main_window.package_map
    # 0 : no error
    # 1 : File not found
    # 2 : table or dictionnary error
    # 3 : internal function error
    errcode = 0

    # Listing the entries to delete
    del_list = []  # tuples (package_name, version_code, file_path)

    # Checking PackageMap instead of table
    for (pkg, vcode_int), info in list(pkg_map.get_all_packages().items()):
        vcode = str(vcode_int)
        is_saved_and_checked = info.local and info.checked
        if is_saved_and_checked:
            fname = f"{pkg}_{vcode}.apk"
            # trying .apk
            file_path = apk_dir / fname
            if not file_path.exists():
                # trying .apks
                file_path = file_path.with_suffix(file_path.suffix + "s")
                if not file_path.exists():
                    logging.error(
                        f"Apk(s) file not found for {pkg} vcode {vcode}.\nThe file may have been renamed, consider local rescan")
                    # marking error and continuing list
                    errcode = 1  # File not found
                else:
                    del_list.append((pkg, vcode, file_path))
            else:
                del_list.append((pkg, vcode, file_path))

    if not del_list:
        logging.info("No package to delete.")
        return errcode

    # Deleting file and UI + pkg_map Update
    for pkg, vcode, path in del_list:
        try:
            os.remove(path)
            logging.debug(f"[PAH]\nDeleted file {path}")
        except FileNotFoundError:
            logging.error(f"[PAH]\nFile not found: {path}")
            errcode = 1 if errcode <= 1 else errcode
        except Exception as e:
            errcode = 3
            pahc.on_action_failed(main_window, "Deletion", f"Error deleting {path}:\n{e}")

        # Update data in table AND PackageMap
        # If the pkg,vcode is not installed and deleted on PC, delete from pkg_map and table
        _mark_deleted(main_window, pkg, vcode)
        if pkg_map.exists(pkg, vcode) and not pkg_map.get(pkg, vcode).android and not pkg_map.get(pkg, vcode).local:
            logging.warning(
                f"\nInconsistent values for {pkg} vcode {vcode} :\nconsider android or local rescan")
            errcode = 2

    _clear_selection(main_window)
    return errcode


def _mark_saved(main_window, pkg: str, vcode: str) -> None:
    pkg_map = main_window.package_map
    info = pkg_map.get(pkg, vcode)
    if info:
        info.local = True
    if hasattr(main_window, "table_adapter"):
        main_window.table_adapter.refresh()
    save_file = pkg_map.get_save_file_path()
    pkg_map.save_to_file(save_file)


def _mark_deleted(main_window, pkg: str, vcode: str) -> None:
    pkg_map = main_window.package_map
    info = pkg_map.get(pkg, vcode)
    if info:
        info.local = False
        info.file_name = ""
        info.file_hash = ""
        if not info.android:
            pkg_map.remove(pkg, vcode)
    if hasattr(main_window, "table_adapter"):
        main_window.table_adapter.refresh()
    save_file = pkg_map.get_save_file_path()
    pkg_map.save_to_file(save_file)


# === APK Extraction related functions ===

def extract_single_apk(package: str, apk_path: str, out_dir: Path) -> Path:
    """Pull a single APK via adb and return (apk_file) path."""
    out_dir.mkdir(parents=True, exist_ok=True)
    dst = out_dir / f"{package}.apk"
    process = subprocess.run(["adb", "pull", apk_path, str(dst)],
               capture_output=True,text=True)
    # Single apk extraction
    if process.stdout:
        logging.debug(f"[adb pull stdout] {process.stdout.strip()}")
    if process.stderr:
        logging.error(f"[adb pull stderr] {process.stderr.strip()}")
    return dst if process.returncode == 0 else False

def extract_split_apks(package: str, apk_paths: list[str], out_dir: Path) -> Path:
    """Pull split APK, concatenate to .apks, and return (apks_file) path."""
    # Multiple APK pull
    out_dir.mkdir(parents=True, exist_ok=True)
    split_files = []
    for idx, path in enumerate(apk_paths, start=1):
        dst = out_dir / f"{package}_split{idx}.apk"
        process = subprocess.run(["adb", "pull", path, str(dst)],
                       capture_output=True,text=True)
        # APKs extraction
        if process.stdout:
            logging.debug(f"[adb pull stdout] {process.stdout.strip()}")
        if process.stderr:
            logging.error(f"[adb pull stderr] {process.stderr.strip()}")
        split_files.append(dst)
    # APKS Concatenation
    apks_dst = out_dir / f"{package}.apks"
    process = subprocess.run(["7z", "a", str(apks_dst)] + [str(f) for f in split_files],
                   capture_output=True,check=True)
    if process.stdout:
        logging.debug(f"[7z stdout] {process.stdout.strip()}")
    if process.stderr:
        logging.error(f"[7z stderr] {process.stderr.strip()}")
        if not pahu.DEBUG_FLAG:
            pahu.raise_error("APKS concatenation failed for package "+package)
    # cleanup splits
    for f in split_files:
        f.unlink()
    return apks_dst if apks_dst.is_file() else False

def extract_package(package: str, versioncode: str, out_dir: Path) -> str:
    """Extract APK or APKS from android via adb and return the apk_file path."""
    # get paths via adb
    result = subprocess.run([
        "adb", "shell", "pm", "path", package],
        capture_output=True, text=True, check=True)
    if result.stdout:
        logging.debug(f"[adb pm stdout] {result.stdout.strip()}")
    if result.stderr:
        logging.error(f"[adb pm stderr] {result.stderr.strip()}")
    package_file_name = package +"_"+ versioncode
    paths = [line.split(':')[1] for line in result.stdout.splitlines()]
    if len(paths) == 1:
        apk_dst = extract_single_apk(package_file_name, paths[0], out_dir)
    else:
        apk_dst = extract_split_apks(package_file_name, paths, out_dir)
    return str(apk_dst) if apk_dst.is_file() else False

