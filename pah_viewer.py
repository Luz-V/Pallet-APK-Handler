from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QCheckBox, QTableWidget, QTableWidgetItem, QWidget, QHBoxLayout
from PyQt5.QtGui import QColor
from collections import defaultdict
import pah_data as pahd


# A INVESTIGUER
def clear_selection(main_window):
    try:
        import pah_events
        pah_events.clear_selection(main_window)
    except Exception:
        pass


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
            self.pkg_map.set_check(pkg, vcode, is_checked)
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

    # NOT USED
    # TO INVESTIGATE
    def set_checked(self, pkg: str, vcode: str, checked: bool):
        info = self.get(pkg, vcode)
        if info and info.checked != checked:
            info.checked = checked
            self._dirty.add((pkg, int(vcode)))

    # NOT USED
    def find_row(self, pkg: str, vcode: str) -> int:
        """Retourne la ligne correspondant à pkg + version, -1 si non trouvé."""
        for row in range(self.table.rowCount()):
            pkg_item = self.table.item(row, 1)
            vcode_item = self.table.item(row, 2)
            if pkg_item and vcode_item:
                if pkg_item.text().strip() == pkg and vcode_item.text().strip() == vcode:
                    return row
        return -1
