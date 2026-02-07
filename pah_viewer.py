from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QCheckBox, QTableWidget, QTableWidgetItem, QWidget, QHBoxLayout
from PyQt5.QtGui import QColor
from collections import defaultdict
import pah_data as pahd

# array building
def on_scan_finished(main_window, scan_result):
    """
    Traite le résultat d'un scan Android/local et met à jour PackageMap + table.
    """
    # 0️⃣ Fermer le progress dialog si existant
    if getattr(main_window, "progress_dialog", None):
        main_window.progress_dialog.close()
        main_window.progress_dialog = None

    pkg_map = main_window.package_map

    # 1️⃣ Reconcilier scan_result avec PackageMap existant
    # scan_result: dict ou PackageMap avec packages trouvés
    if hasattr(scan_result, "get_all_packages"):
        scanned_items = scan_result.get_all_packages().items()
    else:
        scanned_items = scan_result.items()

    for entry in scanned_items:
        if isinstance(entry[0], tuple):
            pkg, vcode_int = entry[0]
            info = entry[1]
            vcode_str = str(vcode_int)
        else:
            # Ancien dict
            (pkg, vcode_str), info = entry

        # Vérifier si package existe déjà dans PackageMap
        existing = pkg_map.find_by_filename(info.file_name) or pkg_map.find_by_hash(info.file_hash)
        if existing:
            # Si trouvé dans PackageMap, mettre à jour les flags
            ex_pkg, ex_vcode = existing
            ex_info = pkg_map.get(ex_pkg, str(ex_vcode))
            if info.android:
                ex_info.android = True
            if info.local:
                ex_info.local = True
        else:
            # Nouvelle entrée
            pkg_map.add(
                pkg,
                vcode_str,
                label=getattr(info, "label", info.get("label", pkg)),
                android=getattr(info, "android", info.get("android", False)),
                local=getattr(info, "local", info.get("local", False)),
                checked=getattr(info, "checked", info.get("checked", False)),
                file_name=getattr(info, "file_name", info.get("file_name", "")),
                file_hash=getattr(info, "file_hash", info.get("file_hash", "")),
            )

    # 2️⃣ Supprimer les packages "orphans" (ni installés, ni sauvegardés)
    to_remove = [
        (pkg, vcode_int)
        for (pkg, vcode_int), info in pkg_map.get_all_packages().items()
        if not info.android and not info.local
    ]
    for pkg, vcode_int in to_remove:
        pkg_map.remove(pkg, str(vcode_int))

    # 3️⃣ Rafraîchissement unique de la table
    main_window.table_adapter.refresh()

    # 4️⃣ Sauvegarde
    save_file = pkg_map.get_save_file_path()
    pkg_map.save_to_file(save_file)



class PackageTableAdapter:
    """Adaptateur pour synchroniser un PackageMap avec un QTableWidget."""

    def __init__(self, table: QTableWidget, pkg_map: pahd.PackageMap):
        self.table = table
        self.pkg_map = pkg_map

        # Décocher tri automatique pour l'instant
        self.table.setSortingEnabled(False)

    def refresh(self) -> None:
        """Reconstruit la table depuis le modèle."""
        self.table.setRowCount(len(self.pkg_map.get_all_packages()))

        pkg_name_to_rows = defaultdict(list)

        for row, ((pkg, vcode_int), info) in enumerate(
                sorted(self.pkg_map.get_all_packages().items(), key=lambda x: (x[0][0], x[0][1]))
        ):
            self._populate_row(row, pkg, vcode_int, info)
            pkg_name_to_rows[pkg].append(row)

        # Appliquer les couleurs pour les versions multiples
        self._apply_version_colors(pkg_name_to_rows)

        self.table.setSortingEnabled(True)
        self.pkg_map.clear_dirty()

    def _populate_row(self, row: int, pkg: str, vcode_int: int, info: pahd.PackageInfo) -> None:
        """Remplit une ligne de la table pour un package."""
        vcode_str = str(vcode_int)

        # Col 0 : label
        item = QTableWidgetItem(info.label)
        item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
        self.table.setItem(row, 0, item)

        # Col 1 : package
        item = QTableWidgetItem(pkg)
        item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
        self.table.setItem(row, 1, item)

        # Col 2 : version
        item = QTableWidgetItem(vcode_str)
        item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
        self.table.setItem(row, 2, item)

        # Col 3 : Android installed
        chk_text = "✓" if info.android else ""
        item = QTableWidgetItem(chk_text)
        item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
        item.setTextAlignment(Qt.AlignCenter)
        self.table.setItem(row, 3, item)

        # Col 4 : Local saved
        chk_text = "✓" if info.local else ""
        item = QTableWidgetItem(chk_text)
        item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
        item.setTextAlignment(Qt.AlignCenter)
        self.table.setItem(row, 4, item)

        # Col 5 : checkbox
        self._add_checkbox(row, 5, info.checked, (pkg, vcode_str))

    def _add_checkbox(self, row: int, col: int, checked: bool, pkg_key: tuple) -> None:
        """Ajoute un QCheckBox centré et synchronisé avec le PackageMap."""
        cb = QCheckBox()
        cb.setChecked(checked)

        container = QWidget()
        layout = QHBoxLayout(container)
        layout.addWidget(cb)
        layout.setAlignment(Qt.AlignCenter)
        layout.setContentsMargins(0, 0, 0, 0)
        self.table.setCellWidget(row, col, container)

        # Item invisible pour le tri
        sort_item = QTableWidgetItem()
        sort_item.setForeground(Qt.transparent)
        sort_item.setTextAlignment(Qt.AlignCenter)
        sort_item.setData(Qt.UserRole, checked)
        sort_item.setFlags(Qt.ItemIsEnabled)
        self.table.setItem(row, col, sort_item)

        # Connect checkbox → PackageMap
        def on_state_changed(state: int):
            is_checked = (state == Qt.Checked)
            pkg, vcode = pkg_key
            info = self.pkg_map.get(pkg, vcode)
            self.pkg_map.set_checked(pkg, vcode, is_checked)
            sort_item.setText("1" if is_checked else "0")
            sort_item.setData(Qt.UserRole, is_checked)

        cb.stateChanged.connect(on_state_changed)

    def _apply_version_colors(self, pkg_name_to_rows: dict) -> None:
        """Colorie les lignes selon les versions d’un même package."""
        for pkg_name, rows in pkg_name_to_rows.items():
            if len(rows) <= 1:
                for row in rows:
                    for col in range(self.table.columnCount()):
                        item = self.table.item(row, col)
                        if item:
                            item.setBackground(QColor("white"))
            else:
                # Tri par version croissante
                version_entries = []
                for row in rows:
                    vcode = int(self.table.item(row, 2).text())
                    version_entries.append((row, vcode))
                version_entries.sort(key=lambda x: x[1])

                for idx, (row, _) in enumerate(version_entries):
                    if idx == 0:
                        color = QColor(255, 230, 180)  # Orange (oldest)
                    elif idx == len(version_entries) - 1:
                        color = QColor(200, 255, 200)  # Green (latest)
                    else:
                        color = QColor(255, 255, 180)  # Yellow (intermediate)

                    for col in range(self.table.columnCount()):
                        item = self.table.item(row, col)
                        if item:
                            item.setBackground(color)

    def items(self):
        return self._data.items()

    def set_checked(self, pkg: str, vcode: str, checked: bool):
        info = self.get(pkg, vcode)
        if info and info.checked != checked:
            info.checked = checked
            self._dirty.add((pkg, int(vcode)))

    def find_row(self, pkg: str, vcode: str) -> int:
        """Retourne la ligne correspondant à pkg + version, -1 si non trouvé."""
        for row in range(self.table.rowCount()):
            pkg_item = self.table.item(row, 1)
            vcode_item = self.table.item(row, 2)
            if pkg_item and vcode_item:
                if pkg_item.text().strip() == pkg and vcode_item.text().strip() == vcode:
                    return row
        return -1

    def remove_orphans(self):
        to_remove = [
            (pkg, vcode)
            for (pkg, vcode), info in self._data.items()
            if not info.android and not info.local
        ]
        for pkg, vcode in to_remove:
            self.remove(pkg, str(vcode))
