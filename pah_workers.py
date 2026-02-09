from pathlib import Path
from PyQt5.QtCore import Qt, QThread, pyqtSignal, pyqtSlot

import pah_import as pahim


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
                    apk_file = pahim.extract_package(pkg_name, version_code, Path(self.apk_dir))
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
