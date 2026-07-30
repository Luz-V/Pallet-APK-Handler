import pah_logger
import logging
import csv
import platform
import subprocess

from PyQt5 import uic
from PyQt5.QtCore import QTimer, Qt, QModelIndex, QItemSelectionModel
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import QHeaderView, QMainWindow, QApplication, QShortcut, QFileDialog
from functools import partial

import pah_scan as pahsc
import pah_install as pahi
import pah_import as pahimp
import pah_data as pahd
import pah_viewer as pahvw
import pah_callbacks as pahc

class MainWindow(QMainWindow):

    def __init__(self):
        super(MainWindow, self).__init__()
        uic.loadUi('pah_gui.ui', self)
        # --- Layout colonnes ---

        self.gridLayout.setColumnStretch(0, 1)
        self.gridLayout.setColumnStretch(1, 0)
        self.gridLayout.setColumnStretch(2, 0)

        self.setStatusBar(self.statusbar)
        self.statusBar().showMessage("TEST OK")
        print("statusbar parent:", self.statusbar.parent())
        print("is visible:", self.statusbar.isVisible())

        # --- PackageMap centralisé ---
        self.package_map = pahd.PackageMap()

        # Charger les données sauvegardées depuis le JSON
        save_file = self.package_map.get_save_file_path()
        loaded_count = self.package_map.load_from_file(save_file)
        if loaded_count > 0:
            logging.info(f"Loaded {loaded_count} packages from save file")

        # --- Init PackageTableAdapter ---
        self.table_adapter = pahvw.PackageTableAdapter(
            self.tableWidget_2,
            self.package_map
        )

        # Rafraîchir la table pour afficher les données chargées
        self.table_adapter.refresh()

        # Connection lineEdit_search
        self.lineEdit_search.textChanged.connect(
            self.table_adapter.set_filter
        )

        # --- Init main table widget ---
        self.init_main_tablewidget()

        # --- Boutons ---
        self.pushButton_Scan.clicked.connect(lambda: pahsc.on_scan_device_clicked(self))
        self.pushButton_Downgrade.clicked.connect(lambda: pahi.on_downgrade_clicked(self))
        self.pushButton_sel_all.clicked.connect(lambda: self.table_adapter.toggle_all_checked())
        self.pushButton_Install.clicked.connect(lambda: pahi.on_install_clicked(self))
        self.pushButton_Keep_only.clicked.connect(lambda: pahi.on_uninstall_clicked(self, invert=True))
        self.pushButton_Uninstall.clicked.connect(lambda: pahi.on_uninstall_clicked(self))
        self.pushButton_Backup.clicked.connect(lambda: pahimp.on_backup_clicked(self))
        self.pushButton_Delete.clicked.connect(lambda: pahimp.on_delete_clicked(self))
        self.pushButton_Explore_Apk.clicked.connect(lambda: self.on_explore_apk_clicked())
        self.pushButton_Export.clicked.connect(lambda: self.on_export_clicked())
        self.pushButton_Update.clicked.connect(lambda: pahi.on_update_clicked(self))

        # --- Menus ---
        # File
        self.actionRefresh.triggered.connect(lambda: self.table_adapter.refresh())
        self.actionClear_filter.triggered.connect(lambda: self.clear_filter())
        self.actionExport_table.triggered.connect(lambda: self.on_export_clicked())
        self.actionClose.triggered.connect(lambda: self.close_window())

        # Edit
        self.actionSelect_all.triggered.connect(lambda: self.table_adapter.select_and_check_all())
        self.actionSelect_none.triggered.connect(lambda: self.table_adapter.clear_selection())
        self.actionInvert_Selection.triggered.connect(lambda: self.table_adapter.invert_all())
        self.actionCopy_selection_to_clipboard.triggered.connect(self.copy_selection_to_clipboard)

        # Scan
        self.actionGlobal_scan.triggered.connect(
            partial(pahsc.on_scan_device_clicked, self, scan_android=True, scan_local=True)
        )
        self.actionRescan_android.triggered.connect(
            partial(pahsc.on_scan_device_clicked, self, scan_android=True, scan_local=False)
        )
        self.actionRescan_backups.triggered.connect(
            partial(pahsc.on_scan_device_clicked, self, scan_android=False, scan_local=True)
        )
        self.actionRebuild_local_dictionnary.triggered.connect(
            partial(pahsc.on_scan_device_clicked, self, scan_android=False, scan_local=True, reset_appt_dict=True)
        )

        # --- Actions ---
        # Local
        self.actionInstall_selected.triggered.connect(lambda: pahi.on_install_clicked(self))
        self.actionUpdate.triggered.connect(lambda: pahi.on_update_clicked(self))
        self.actionDowngrade_unstable.triggered.connect(lambda: pahi.on_downgrade_clicked(self))
        self.actionUninstall_selected.triggered.connect(lambda: pahi.on_uninstall_clicked(self))
        self.actionKeep_only_selected.triggered.connect(lambda: pahi.on_uninstall_clicked(self, invert=True))
        # Android
        self.actionImport.triggered.connect(lambda: pahimp.on_backup_clicked(self))
        self.actionDelete.triggered.connect(lambda: pahimp.on_delete_clicked(self))

        # --- Clipboard copy shortcut ---
        self.copy_shortcut = QShortcut(QKeySequence("Ctrl+C"), self)
        self.copy_shortcut.activated.connect(self.copy_selection_to_clipboard)

        # --- Display window ---
        self.show()

        # --- Initial scan ---
        QTimer.singleShot(
            0,
            lambda: pahsc.on_scan_device_clicked(
                self,
                scan_android=True,
                scan_local=True,
            ),
        )

    # Initialization methods

    def init_main_tablewidget(self) -> None:
        self.tableWidget_2.setSortingEnabled(False)
        self.tableWidget_2.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tableWidget_2.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)

        self.tableWidget_2.setColumnWidth(2, 100)
        self.tableWidget_2.setColumnWidth(3, 70)
        self.tableWidget_2.setColumnWidth(4, 70)
        self.tableWidget_2.horizontalHeader().setSectionResizeMode(3, QHeaderView.Fixed)
        self.tableWidget_2.horizontalHeader().setSectionResizeMode(4, QHeaderView.Fixed)

        self.tableWidget_2.setColumnWidth(5, 80)
        self.tableWidget_2.horizontalHeader().setSectionResizeMode(5, QHeaderView.Fixed)

    def rebuild_index_map(self):
        """Reconstruit PackageMap depuis la table après un tri."""
        self.package_map.update_from_table(self.tableWidget_2)

    # def init_tablewidget_low(self):
    #     self.tableWidget.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
    #     self.tableWidget.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)

    def copy_selection_to_clipboard(self):
        selection = self.tableWidget_2.selectedIndexes()
        if not selection:
            return

        selection = sorted(selection, key=lambda x: (x.row(), x.column()))
        min_row = selection[0].row()
        max_row = selection[-1].row()
        min_col = selection[0].column()
        max_col = selection[-1].column()

        model = self.tableWidget_2.model()
        lines = []

        for row in range(min_row, max_row + 1):
            row_data = []
            for col in range(min_col, max_col + 1):
                index = model.index(row, col)
                if not index.isValid():
                    row_data.append("")
                    continue

                if col == 5:
                    row_data.append("✓" if index.data(Qt.CheckStateRole) == Qt.Checked else "")
                else:
                    value = index.data(Qt.DisplayRole)
                    row_data.append("" if value is None else str(value))

            lines.append("\t".join(row_data))

        QApplication.clipboard().setText("\n".join(lines))
        logging.info("[PAH] tables value in system clipboard")

    def clear_filter(self):
        self.lineEdit_search.clear()
        self.table_adapter.clear_selection()

        sel = self.tableWidget_2.selectionModel()
        if sel:
            sel.clearSelection()
            sel.setCurrentIndex(QModelIndex(), QItemSelectionModel.NoUpdate)

    def close_window(self):
        if hasattr(self, "worker") and self.worker.isRunning():
            self.worker.requestInterruption()
            self.worker.wait()
        
        # Sauvegarder PackageMap avant de fermer
        save_file = self.package_map.get_save_file_path()
        self.package_map.save_to_file(save_file)
        
        self.close()

    def on_export_clicked(self):
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getSaveFileName(
            self,
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
                for (pkg, vcode_int), info in self.package_map.get_all_packages().items():
                    vcode = str(vcode_int)
                    label = info.label
                    android = "✓" if info.android else ""
                    local = "✓" if info.local else ""
                    writer.writerow([label, pkg, vcode, android, local])
            logging.info(f"Export CSV succeeded : {file_path}")
        except Exception as e:
            logging.error(f"\nError during CSV export:\n{e}")

    def on_explore_apk_clicked(self):
        from pathlib import Path
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
                pahc.on_action_failed(self,"Explore","Unsupported file system.")
                return 2
        except Exception as errmsg:
            pahc.on_action_failed(self, "Explore", errmsg)
            return 1
        return 0


app = QApplication([])
window = MainWindow()
app.exec_()