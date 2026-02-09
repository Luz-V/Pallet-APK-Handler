import os
import csv
import logging
import platform
import subprocess

from PyQt5.QtWidgets import QCheckBox, QFileDialog
from pathlib import Path

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


