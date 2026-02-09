import pah_logger
import logging
import csv
import platform
import subprocess

from PyQt5 import QtWidgets, uic
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import QCheckBox, QHeaderView, QMainWindow, QApplication, QShortcut, QFileDialog
from functools import partial

import pah_scan
import pah_install
import pah_import
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

        # --- Init main table widget ---
        self.init_main_tablewidget()

        # --- Boutons ---
        self.pushButton_Scan.clicked.connect(lambda: pah_scan.on_scan_device_clicked(self))
        self.pushButton_Downgrade.clicked.connect(lambda: pah_install.on_downgrade_clicked(self))
        self.pushButton_sel_all.clicked.connect(lambda: self.on_selectall_toggle_clicked())
        self.pushButton_Install.clicked.connect(lambda: pah_install.on_install_clicked(self))
        self.pushButton_Keep_only.clicked.connect(lambda: pah_install.on_uninstall_clicked(self, invert=True))
        self.pushButton_Uninstall.clicked.connect(lambda: pah_install.on_uninstall_clicked(self))
        self.pushButton_Backup.clicked.connect(lambda: pah_import.on_backup_clicked(self))
        self.pushButton_Delete.clicked.connect(lambda: pah_import.on_delete_clicked(self))
        self.pushButton_Explore_Apk.clicked.connect(lambda: self.on_explore_apk_clicked())
        self.pushButton_Export.clicked.connect(lambda: self.on_export_clicked())
        self.pushButton_Update.clicked.connect(lambda: pah_install.on_update_clicked(self))

        # --- Menus ---
        self.actionRescan_android.triggered.connect(
            partial(pah_scan.on_scan_device_clicked, self, scan_android=True, scan_local=False)
        )
        self.actionRescan_backups.triggered.connect(
            partial(pah_scan.on_scan_device_clicked, self, scan_android=False, scan_local=True)
        )
        self.actionClose.triggered.connect(lambda: self.close_window())

        # --- Selection Table ---
        self.tableWidget_2.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.tableWidget_2.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectItems)

        # --- Raccourci copie ---
        self.copy_shortcut = QShortcut(QKeySequence("Ctrl+C"), self)
        self.copy_shortcut.activated.connect(self.copy_selection_to_clipboard)

        # --- Affichage fenêtre ---
        self.show()

        # --- Scan initial intelligent ---
        QTimer.singleShot(
            0,
            lambda: pah_scan.on_scan_device_clicked(
                self,
                scan_android=True,
                scan_local=True,
                preserve_android_on_local_scan=True,  # <-- NE relance aapt que si hash absent
            ),
        )

    # Initialization methods

    def init_main_tablewidget(self) -> None:
        # sorting enabled
        self.tableWidget_2.setSortingEnabled(True)
        #self.tableWidget.setSortingEnabled(True)
    # Col 0,1 : stretch
        self.tableWidget_2.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tableWidget_2.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
    # Col 2 : fixed
        #self.tableWidget_2.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.tableWidget_2.setColumnWidth(2, 100)
    # Col 2,3,4 : fixed
        self.tableWidget_2.setColumnWidth(3, 85)
        self.tableWidget_2.setColumnWidth(4, 80)
        self.tableWidget_2.horizontalHeader().setSectionResizeMode(3, QHeaderView.Fixed)
        self.tableWidget_2.horizontalHeader().setSectionResizeMode(4, QHeaderView.Fixed)
        # Col 5 : checkbox activated (modifiable), fixed
        self.tableWidget_2.setColumnWidth(5, 30)
        self.tableWidget_2.horizontalHeader().setSectionResizeMode(5, QHeaderView.Fixed)
        #pahui.add_checkbox(self.tableWidget_2, row, 5, checked=False, enabled=True)

        # Connect to the sorting signal for mapping updates (désactivé pour debug)
        # header = self.tableWidget_2.horizontalHeader()
        # header.sortIndicatorChanged.connect(self.rebuild_index_map)

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
        # Trier la sélection par ligne puis colonne
        selection = sorted(selection, key=lambda x: (x.row(), x.column()))

        # Trouver les limites de la sélection
        min_row = selection[0].row()
        max_row = selection[-1].row()
        min_col = selection[0].column()
        max_col = selection[-1].column()

        # Construire le texte copié
        table_text = ''
        for row in range(min_row, max_row + 1):
            row_data = []
            for col in range(min_col, max_col + 1):
                item = self.tableWidget_2.item(row, col)
                if item:
                    row_data.append(item.text())
                else:
                    # Si cellule avec checkbox (widget), on récupère l’état
                    cell_widget = self.tableWidget_2.cellWidget(row, col)
                    if cell_widget:
                        cb = cell_widget.findChild(QCheckBox)
                        if cb:
                            row_data.append('✓' if cb.isChecked() else '')
                        else:
                            row_data.append('')
                    else:
                        row_data.append('')
            table_text += '\t'.join(row_data) + '\n'

        # Copier dans le presse-papier
        clipboard = QApplication.clipboard()
        clipboard.setText(table_text)
        logging.info(f"[PAH] tables value in system clipboard")

    def close_window(self):
        if hasattr(self, "worker") and self.worker.isRunning():
            self.worker.requestInterruption()
            self.worker.wait()
        
        # Sauvegarder PackageMap avant de fermer
        save_file = self.package_map.get_save_file_path()
        self.package_map.save_to_file(save_file)
        
        self.close()

    def on_selectall_toggle_clicked(self):
        main_table = self.tableWidget_2
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
        if not new_state: 
            logging.debug(f"All values unselected")
        else: 
            logging.debug(f"All values selected")

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