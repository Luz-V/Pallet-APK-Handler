import logging

from PyQt5.QtWidgets import QMessageBox

# popup 1
def update_scan_message(main_window, message: str):
    if main_window.progress_dialog:
        logging.info("" + message)
        main_window.progress_dialog.setLabelText("Scanning local folder\nextracted_apks")
# popup 2
def on_scan_failed(main_window, error_message):
    main_window.progress_dialog.close()
    logging.error(f"\n{error_message}")
    QMessageBox.critical(main_window, "Scan error", f"{error_message}")

def on_action_failed(main_window, action, error_message):
    logging.error(error_message)
    #if main_window.progress_dialog:
    #    main_window.progress_dialog.close()
    QMessageBox.critical(main_window, f"{action} Error", f"Error log : \n{error_message}")

def update_progress_dialog(main_window, msg):
    if not hasattr(main_window, "progress_dialog"):
        return
    if main_window.progress_dialog:
        main_window.progress_dialog.setLabelText(msg)

def update_progress_dialog_percent(main_window, message: str, percent: float):
    if main_window.progress_dialog:
        main_window.progress_dialog.setLabelText(message)
        main_window.progress_dialog.setValue(percent)
        #if main_window.progress_dialog.wasCanceled():
        #    main_window.worker.terminate()  # Terminate worker if canceled is clicked

def switch_progress_to_percent(main_window):
    if main_window.progress_dialog:
        main_window.progress_dialog.setMaximum(100)
