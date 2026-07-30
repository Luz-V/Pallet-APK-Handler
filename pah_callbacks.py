import logging

from PyQt5.QtWidgets import QMessageBox, QApplication

def set_status(main_window, message: str):
    logging.info(message)
    main_window.statusbar.showMessage(message)

def clear_status(main_window):
    main_window.statusbar.clearMessage()

def set_progress_text(main_window, message: str):
    set_status(main_window, message)

def set_progress_value(main_window, value: int):
    main_window.progressBar.setValue(value)
    QApplication.processEvents()  # important pour animation fluide

def set_progress_indeterminate(main_window):
    main_window.progressBar.setRange(0, 0) # Qt indeterminate mode

def set_progress_determinate(main_window):
    main_window.progressBar.setRange(0, 100)

def reset_progress(main_window):
    main_window.progressBar.setRange(0, 100)
    main_window.progressBar.setValue(0)

def update_scan_message(main_window, message: str):
    set_status(main_window, message)

def update_progress_dialog(main_window, msg):
    set_status(main_window, msg)

def update_progress_dialog_percent(main_window, message: str, percent: float):
    set_status(main_window, f"{message} ({percent}%)")

def switch_progress_to_percent(main_window):
    set_status(main_window, "Processing...")

def on_scan_failed(main_window, error_message):
    logging.error(f"\n{error_message}")
    QMessageBox.critical(main_window, "Scan error", f"{error_message}")
    clear_status(main_window)

def on_action_failed(main_window, action, error_message):
    logging.error(error_message)
    QMessageBox.critical(main_window, f"{action} Error", f"Error log : \n{error_message}")
    clear_status(main_window)

def switch_progress_to_percentbis(main_window):
    if main_window.progress_dialog:
        main_window.progress_dialog.setMaximum(100)
