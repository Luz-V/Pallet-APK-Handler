import os
import csv
import logging
import tempfile
import platform
import subprocess

from PyQt5.QtCore import Qt, QTimer, QEventLoop
from PyQt5.QtWidgets import QCheckBox, QProgressDialog, QFileDialog, QApplication
from pathlib import Path

import pah_functions
import pah_workers as pahw
import pah_callbacks as pahc
import pah_data as pahd
import pah_viewer as pahvw

# Scan functions
# To link
# - Scan local only
# - Scan android device only

def on_scan_device_clicked(main_window, scan_android=True, scan_local=True, preserve_android_on_local_scan=True):
    main_table = main_window.tableWidget_2
    row_count = main_table.rowCount()
    local_saved_list = []  # tuples (package_name, version_code, label)
    android_installed_list = []  # tuples (package_name, version_code, label)

    # In case previous data needs to be saved before scan
    if not scan_android or not scan_local:
        for row in range(row_count):
            item_col3 = main_table.item(row, 3) # android-installed check
            item_col4 = main_table.item(row, 4) # local-backup check
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

    main_window.worker = pahw.ScanWorker(
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
        lambda pkg_dico: pahvw.on_scan_finished(main_window, pkg_dico)
    )
    main_window.worker.error_occurred.connect(
        lambda errmsg: pahc.on_scan_failed(main_window, errmsg)
    )

    # START WORKER SAFELY
    QTimer.singleShot(50, main_window.worker.start)


# Operations : install, update, uninstall, backup, delete + popups
# To implement
# - Clean older versions
# - Import new versions

def on_install_clicked(main_window):
    logging.debug("on_install_clicked triggered")
    adb_check = pah_functions.check_adb_connection()
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
                logging.info(f"{pkg} v{vcode} ignored :\nnewer version installed, use the downgrade fonction if necessary")
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
    main_window.progress_dialog = QProgressDialog("Installing on the device via ADB...\nUnlocking may help", "Cancel", 0, 100, main_window)
    main_window.progress_dialog.setWindowTitle("ADB Install")
    main_window.progress_dialog.setCancelButtonText("Cancel")
    main_window.progress_dialog.setWindowModality(Qt.WindowModal)
    main_window.progress_dialog.show()

    # 2 FORCE paint
    main_window.progress_dialog.repaint()
    QApplication.processEvents(QEventLoop.ExcludeUserInputEvents)

    # 3 Lauching worker
    main_window.worker = pahw.InstallWorker(install_list, tmp_dir, downgrade_flag=False)
    #main_window.worker.progress.connect(lambda msg: pahc.update_progress_dialog(main_window, msg))
    main_window.worker.progress.connect(lambda msg, percent: pahc.update_progress_dialog_percent(main_window, msg, percent))
    main_window.worker.error.connect(lambda errmsg: pahc.on_action_failed(main_window, "Install", errmsg))
    main_window.worker.success.connect(lambda pkg_installed, vcode_installed: pahd.mark_package_installed(main_window, pkg_installed, vcode_installed))
    main_window.worker.finished.connect(main_window.progress_dialog.close)
    main_window.worker.finished.connect(lambda: clear_selection(main_window))

    # 4 START WORKER SAFELY
    QTimer.singleShot(50, main_window.worker.start)

def on_update_clicked(main_window):
    logging.debug("Update clicked")
    adb_check = pah_functions.check_adb_connection()
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

    main_window.progress_dialog = QProgressDialog("Installing on the device via ADB...\nUnlocking may help",
            "Cancel", 0,100,main_window)
    main_window.progress_dialog.setWindowTitle("ADB Update")
    main_window.progress_dialog.setCancelButtonText("Cancel")
    #main_window.progress_dialog.canceled.connect(lambda: main_window.worker.stop())
    main_window.progress_dialog.setWindowModality(Qt.WindowModal)
    main_window.progress_dialog.show()

    # 2 FORCE paint
    main_window.progress_dialog.repaint()
    QApplication.processEvents(QEventLoop.ExcludeUserInputEvents)

    # Lauching worker

    main_window.worker = pahw.InstallWorker(update_list, tmp_dir, downgrade_flag=False)
    main_window.worker.progress.connect(lambda msg: pahc.update_progress_dialog(main_window, msg))
    main_window.worker.progress.connect(
        lambda msg, percent: pahc.update_progress_dialog_percent(main_window, msg, percent))
    main_window.worker.error.connect(lambda errmsg: pahc.on_action_failed(main_window, "Update", errmsg))
    main_window.worker.success.connect(lambda pkg_updated, vcode_updated: pahd.mark_package_installed(main_window, pkg_updated, vcode_updated))
    main_window.worker.finished.connect(main_window.progress_dialog.close)
    main_window.worker.finished.connect(lambda: clear_selection(main_window))

    # 4 START WORKER SAFELY
    QTimer.singleShot(50, main_window.worker.start)


def on_downgrade_clicked(main_window):
    logging.debug("on_downgrade_clicked triggered")
    adb_check = pah_functions.check_adb_connection()
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
                logging.info(f"No newer installed version (ot not at all) for {pkg} vcode {vcode}: \nuse the install fonction instead")
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
                    logging.error(f"[PAH]\nAPK/APKS not found for {pkg} v{vcode}.\nConsider local rescan")
    # Empty downgrade list
    if not downgrade_list:
        logging.info("No packages to downgrade.")
        return

    # Displaying progress bar
    main_window.progress_dialog = QProgressDialog("Downgrading on the device via ADB...\nUnlocking may help", "Cancel", 0, 100, main_window)
    main_window.progress_dialog.setWindowTitle("ADB Install")
    main_window.progress_dialog.setWindowModality(Qt.WindowModal)
    main_window.progress_dialog.setCancelButtonText("Cancel")
    main_window.progress_dialog.show()

    # 2 FORCE paint
    main_window.progress_dialog.repaint()
    QApplication.processEvents(QEventLoop.ExcludeUserInputEvents)

    # launching worker
    main_window.worker = pahw.InstallWorker(downgrade_list, tmp_dir, downgrade_flag=True)
    main_window.worker.progress.connect(lambda msg,percent: pahc.update_progress_dialog_percent(main_window, msg, percent))
    main_window.worker.error.connect(lambda errmsg: pahc.on_action_failed(main_window, "Downgrade",errmsg))
    main_window.worker.success.connect(lambda pkg_downed, vcode_downed: pahd.mark_package_installed(main_window, pkg_downed, vcode_downed))
    main_window.worker.finished.connect(main_window.progress_dialog.close)
    main_window.worker.finished.connect(lambda: clear_selection(main_window))

    # 4 START WORKER SAFELY
    QTimer.singleShot(50, main_window.worker.start)

def on_uninstall_clicked(main_window, invert=False):
    logging.debug("Uninstall clicked")
    adb_check = pah_functions.check_adb_connection()
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
    main_window.progress_dialog = QProgressDialog("Uninstalling with ADB...\nUnlocking may help", "Cancel", 0, 100, main_window)
    main_window.progress_dialog.setWindowTitle("ADB Uninstall")
    main_window.progress_dialog.setCancelButtonText("Cancel")
    main_window.progress_dialog.setWindowModality(Qt.WindowModal)
    main_window.progress_dialog.show()

    # 2 FORCE paint
    main_window.progress_dialog.repaint()
    QApplication.processEvents(QEventLoop.ExcludeUserInputEvents)

    # Lauching worker
    main_window.worker = pahw.UninstallWorker(uninstall_list)
    main_window.worker.progress.connect(
        lambda msg,percent: pahc.update_progress_dialog_percent(main_window, msg, percent))
    main_window.worker.success.connect(
        lambda pkg_name_del, vcode_del: pahd.mark_package_uninstalled(main_window, pkg_name_del, vcode_del))
    main_window.worker.error.connect(
        lambda errmsg: pahc.on_action_failed(main_window, "Uninstall", errmsg))
    main_window.worker.finished.connect(main_window.progress_dialog.close)
    main_window.worker.finished.connect(lambda: clear_selection(main_window))
    main_window.worker.start()

    # 4 START WORKER SAFELY
    QTimer.singleShot(50, main_window.worker.start)

def on_backup_clicked(main_window):
    logging.debug("on_backup_clicked triggered")
    adb_check = pah_functions.check_adb_connection()
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
            logging.error(f"\nNo android package to import for {pkg} vcode {vcode}. Consider android rescan")
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
    main_window.worker.progress.connect(lambda msg, percent: pahc.update_progress_dialog_percent(main_window, msg, percent))
    main_window.worker.success.connect(lambda pkg_name_bak, vcode_bak: pahd.mark_package_saved(main_window, pkg_name_bak, vcode_bak))
    main_window.worker.finished.connect(main_window.progress_dialog.close)
    main_window.worker.finished.connect(lambda: clear_selection(main_window))
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
                    logging.error(f"Apk(s) file not found for {pkg} vcode {vcode}.\nThe file may have been renamed, consider local rescan")
                    # marking error and continuing list
                    errcode = 1 # File not found
                else:
                    del_list.append((pkg, vcode, file_path))
            else:
                del_list.append((pkg, vcode, file_path))


    if not del_list:
        logging.info("No package to delete.")
        return errcode

    # Deleting file and UI + pkg_map Update
    for pkg, vcode, path in del_list:
        #if path=="nofile":
        #    logging.debug("APK file not found, yet still added in delete list")
        #    break
        #else:
        try:
            os.remove(path)
            logging.debug(f"[PAH]\nDeleted file {path}")
        except FileNotFoundError:
            logging.error(f"[PAH]\nFile not found: {path}")
            errcode=1 if errcode<=1 else errcode
        except Exception as e:
            errcode=3
            pahc.on_action_failed(main_window, "Deletion", f"Error deleting {path}:\n{e}")

        # Update data in table AND PackageMap
        # If the pkg,vcode is not installed and deleted on PC, delete from pkg_map and table
        pahd.mark_package_deleted(main_window, pkg, vcode)
        if pkg_map.exists(pkg, vcode):
            info = pkg_map.get(pkg, vcode)
            if not info.android:
                # key should not be found : should be deleted already
                logging.warning(f"\nInconsistent values for {pkg} vcode {vcode} :\nconsider android or local rescan")
                errcode=2

    clear_selection(main_window)
    return errcode

# Select

def on_selectall_toggle_clicked(main_window):
    main_table = main_window.tableWidget_2
    row_count = main_table.rowCount()

    # Check if all rows are checked
    all_checked = all(
        (checkbox := main_table.cellWidget(row, 5).findChild(QCheckBox)).isChecked()
        for row in range(row_count)
        if main_table.cellWidget(row, 5)
    )

    # If so, uncheck all, else check all
    new_state = not all_checked
    for row in range(row_count):
        checkbox_widget = main_table.cellWidget(row, 5)
        if checkbox_widget:
            checkbox = checkbox_widget.findChild(QCheckBox)
            if checkbox:
                checkbox.setChecked(new_state)
    if not new_state: logging.debug(f"All values unselected")
    else: logging.debug(f"All values selected")

def clear_selection(main_window):
    # Uncheck all rows

    main_table = main_window.tableWidget_2
    row_count = main_table.rowCount()
    new_state = False
    for row in range(row_count):
        checkbox_widget = main_table.cellWidget(row, 5)
        if checkbox_widget:
            checkbox = checkbox_widget.findChild(QCheckBox)
            if checkbox:
                checkbox.setChecked(new_state)
    logging.debug(f"Selection cleared")

def on_export_clicked(main_window):
    options = QFileDialog.Options()
    file_path, _ = QFileDialog.getSaveFileName(
        main_window,
        "Export table (CSV)",
        "",
        "CSV Files (*.csv);;All files (*)",
        options=options
    )
    if not file_path:
        return  # User canceled

    if not file_path.lower().endswith('.csv'):
        file_path += '.csv'

    try:
        with open(file_path, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            # Header
            writer.writerow(["Label", "Package", "Version", "Android", "Local"])
            # Body
            for (pkg, vcode_int), info in main_window.package_map.get_all_packages().items():
                vcode = str(vcode_int)
                label = info.label
                android = "✓" if info.android else ""
                local = "✓" if info.local else ""
                writer.writerow([label, pkg, vcode, android, local])
        logging.info(f"Export CSV succeeded : {file_path}")
    except Exception as e:
        logging.error(f"\nError during CSV export:\n{e}")

def on_explore_apk_clicked(main_window):
    dir_path = Path(__file__).parent / 'extracted_apks'
    if not dir_path:
        logging.error(f"Missing Apk(s) folder {dir_path}\nAttempting creation, please verify writing rights")
        dir_path.mkdir(parents=True, exist_ok=True)
    try:
        if platform.system() == "Windows":
            subprocess.run(['start', '', dir_path], shell=True)
        elif platform.system() == "Linux":
            subprocess.run(['xdg-open', dir_path])
        elif platform.system() == "Darwin":  # macOS
            subprocess.run(['open', dir_path])
        else:
            pahc.on_action_failed(main_window,"Explore","Unsupported file system.")
            return 2
    except Exception as errmsg:
        pahc.on_action_failed(main_window, "Explore", errmsg)
        return 1
    return 0


