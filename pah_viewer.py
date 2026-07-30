import logging

from collections import defaultdict
from PyQt5.QtCore import Qt, QObject, QModelIndex, QItemSelectionModel
from PyQt5.QtGui import QColor, QStandardItemModel, QStandardItem
from PyQt5.QtWidgets import QAbstractItemView, QTableView

import pah_data as pahd


class PackageTableAdapter(QObject):
    """
    Adaptateur QTableView + QStandardItemModel.
    - colonne 5 = case cochable native Qt
    - l’état coché est conservé côté UI via checked_state
    - is_checked() lit l’état réel du modèle affiché
    """

    HEADERS = ["Label", "Package", "Version", "Android", "Local", "Select"]

    def __init__(self, table: QTableView, pkg_map: pahd.PackageMap):
        super().__init__()
        self.table = table
        self.view = table  # ← IMPORTANT : définir AVANT utilisation
        self.pkg_map = pkg_map

        self.model = QStandardItemModel(0, len(self.HEADERS), self.view)
        self.view.setModel(self.model)
        self.view.setSortingEnabled(True)
        self.view.sortByColumn(0, Qt.AscendingOrder)

        self._row_index: dict[tuple[str, str], int] = {}
        self.checked_state: dict[tuple[str, str], bool] = {}
        self.filter_text = ""

        self.last_clicked_row: int | None = None
        self._dragging = False
        self._drag_state: bool | None = None

        self.view.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.view.setMouseTracking(True)

        self.view.selectionModel().selectionChanged.connect(self._on_selection_changed)

    def _on_selection_changed(self, selected, deselected) -> None:
        self._switch_state_selection(selected, True)
        self._switch_state_selection(deselected, False)

    def _switch_state_selection(self, selection, state:bool) -> None:
        for selection_range in selection:
            top = selection_range.top()
            bottom = selection_range.bottom()

            for row in range(top, bottom + 1):
                pkg_item = self.model.item(row, 1)
                vcode_item = self.model.item(row, 2)

                if not pkg_item or not vcode_item:
                    continue
                key = (pkg_item.text(), vcode_item.text())
                self.checked_state[key] = state
                item = self.model.item(row, 5)
                # UI sync immédiate (LOCAL ONLY)
                if (item.text()=="●" and state) or ( item.text()=="" and not state):
                    logging.debug(f"{pkg_item.text()}: check state ≠ selected state")
                if item:
                    item.setText("●" if state else "")
                    logging.debug(f"{pkg_item.text()}: checked" if state else f"{pkg_item.text()}: unchecked")

    def refresh(self) -> None:
        """Reconstruit le modèle depuis PackageMap."""
        data = sorted(
            self.pkg_map.get_all_packages().items(),
            key=lambda x: (x[0][0], x[0][1])
        )
        if self.filter_text:
            filtered = []
            for (pkg, vcode), info in data:
                if (
                    self.filter_text in pkg.lower()
                    or self.filter_text in (info.label or "").lower()
                ):
                    filtered.append(((pkg, vcode), info))
            data = filtered

        self.model.setRowCount(len(data))
        self.model.blockSignals(True)
        try:
            self.model.clear()
            self.model.setColumnCount(len(self.HEADERS))
            self.model.setHorizontalHeaderLabels(self.HEADERS)
            self.model.setRowCount(len(data))
            self._row_index.clear()
            pkg_name_to_rows = defaultdict(list)

            for row, ((pkg, vcode_int), info) in enumerate(data):
                vcode_str = str(vcode_int)
                self.model.setItem(row, 0, self._ro_item(info.label))
                self.model.setItem(row, 1, self._ro_item(pkg))
                self.model.setItem(row, 2, self._ro_item(vcode_str))
                self.model.setItem(row, 3, self._ro_item("✓" if info.android else ""))
                self.model.setItem(row, 4, self._ro_item("✓" if info.local else ""))
                chk = QStandardItem()
                chk.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                self.model.setItem(row, 5, chk)
                pkg_name_to_rows[pkg].append(row)
            self.render_checked_state()
            self._apply_version_colors(pkg_name_to_rows)
        finally:
            self.model.blockSignals(False)

        self.view.setSortingEnabled(True)
        self.view.sortByColumn(
            self.view.horizontalHeader().sortIndicatorSection(),
            self.view.horizontalHeader().sortIndicatorOrder()
        )

    def _ro_item(self, text) -> QStandardItem:
        item = QStandardItem(str(text))
        item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
        return item

    def is_checked(self, pkg: str, vcode: str) -> bool:
        index = self.find_index(pkg, vcode)
        if not index.isValid():
            return False
        item = self.model.item(index.row(), 5)
        return item and item.text() == "●"

    def set_checked(self, pkg: str, vcode: str, checked: bool) -> None:
        index = self.find_index(pkg, vcode)
        if not index.isValid():
            return
        item = self.model.item(index.row(), 5)
        if item:
            item.setText("●" if checked else "")

    def set_filter(self, text: str) -> None:
        self.filter_text = text.lower().strip()
        self.refresh()

    def toggle_all_checked(self) -> None:
        if not self.model.rowCount():
            return
        # état global courant
        all_checked = all(
            self.is_checked(
                self.model.item(row, 1).text(),
                self.model.item(row, 2).text()
            )
            for row in range(self.model.rowCount())
            if self.model.item(row, 1) and self.model.item(row, 2)
        )
        new_state = not all_checked
        sel_model = self.view.selectionModel()
        if sel_model:
            sel_model.blockSignals(True)
        self.model.blockSignals(True)
        try:
            # reset sélection dans tous les cas
            if sel_model:
                sel_model.clearSelection()
                sel_model.setCurrentIndex(QModelIndex(), QItemSelectionModel.NoUpdate)

            for row in range(self.model.rowCount()):
                pkg_item = self.model.item(row, 1)
                vcode_item = self.model.item(row, 2)
                item = self.model.item(row, 5)
                if not pkg_item or not vcode_item or not item:
                    continue
                key = (pkg_item.text(), vcode_item.text())

                # --- LOGIQUE ---
                self.checked_state[key] = new_state
                item.setText("●" if new_state else "")

                # --- UI SELECTION ---
                if sel_model and new_state:
                    index = self.model.index(row, 0)
                    sel_model.select(
                        index,
                        QItemSelectionModel.Select | QItemSelectionModel.Rows
                    )
        finally:
            self.model.blockSignals(False)
            if sel_model:
                sel_model.blockSignals(False)
        self.render_checked_state()
        self.view.viewport().update()
        logging.debug("Select+Check all toggled -> %s", new_state)

    def select_and_check_all(self) -> None:
        if not self.model.rowCount():
            return
        sel_model = self.view.selectionModel()
        if sel_model:
            sel_model.blockSignals(True)

        self.model.blockSignals(True)
        try:
            # reset sélection
            if sel_model:
                sel_model.clearSelection()
                sel_model.setCurrentIndex(QModelIndex(), QItemSelectionModel.NoUpdate)

            for row in range(self.model.rowCount()):
                pkg_item = self.model.item(row, 1)
                vcode_item = self.model.item(row, 2)

                if not pkg_item or not vcode_item:
                    continue
                key = (pkg_item.text(), vcode_item.text())
                # --- CHECK ---
                self.checked_state[key] = True
                # --- SELECT ---
                if sel_model:
                    index = self.model.index(row, 0)
                    sel_model.select(
                        index,
                        QItemSelectionModel.Select | QItemSelectionModel.Rows
                    )
        finally:
            self.model.blockSignals(False)
            if sel_model:
                sel_model.blockSignals(False)
        # rendu des checks
        self.render_checked_state()
        self.view.viewport().update()
        logging.debug("Select + Check ALL applied")

    def invert_all(self) -> None:
        if not self.model.rowCount():
            return
        sel_model = self.view.selectionModel()

        if sel_model:
            sel_model.blockSignals(True)
        self.model.blockSignals(True)

        try:
            if sel_model:
                sel_model.clearSelection()
                sel_model.setCurrentIndex(QModelIndex(), QItemSelectionModel.NoUpdate)

            for row in range(self.model.rowCount()):
                pkg_item = self.model.item(row, 1)
                vcode_item = self.model.item(row, 2)
                item = self.model.item(row, 5)
                if not pkg_item or not vcode_item or not item:
                    continue
                key = (pkg_item.text(), vcode_item.text())
                # état actuel (UI = source de vérité ici)
                current_state = (item.text() == "●")
                new_state = not current_state
                # --- DATA ---
                self.checked_state[key] = new_state
                # --- UI CHECK ---
                item.setText("●" if new_state else "")
                # --- UI SELECTION ---
                if sel_model and new_state:
                    index = self.model.index(row, 0)
                    sel_model.select(
                        index,
                        QItemSelectionModel.Select | QItemSelectionModel.Rows
                    )
        finally:
            self.model.blockSignals(False)
            if sel_model:
                sel_model.blockSignals(False)
        self.view.viewport().update()
        logging.debug("Invert selection + checked")

    # Clear_1=> selection
    def clear_selection(self) -> None:
        sel_model = self.view.selectionModel()
        if sel_model:
            sel_model.clearSelection() # Selection
            sel_model.setCurrentIndex(QModelIndex(), QItemSelectionModel.NoUpdate)
        self.clear_all_checked() # checked_state + item ""

    # Clear 2 => checked
    def clear_all_checked(self):
        self.checked_state.clear()
        for row in range(self.model.rowCount()):
            item = self.model.item(row, 5)
            if item:
                item.setText("")

    def find_index(self, pkg: str, vcode: str):
        for row in range(self.model.rowCount()):
            p = self.model.item(row, 1)
            v = self.model.item(row, 2)
            if p and v and (p.text(), v.text()) == (pkg, str(vcode)):
                return self.model.index(row, 0)
        return QModelIndex()

    def _apply_version_colors(self, pkg_rows):
        for pkg, rows in pkg_rows.items():
            if len(rows) <= 1:
                continue
            versions = []

            for r in rows:
                v = int(self.model.item(r, 2).text())
                versions.append((r, v))
            versions.sort(key=lambda x: x[1])

            for i, (row, _) in enumerate(versions):
                color = (
                    QColor(255, 230, 180) if i == 0 else
                    QColor(200, 255, 200) if i == len(versions) - 1 else
                    QColor(255, 255, 180)
                )
                for c in range(self.model.columnCount()):
                    item = self.model.item(row, c)
                    if item:
                        item.setBackground(color)

    # pas encore utilisée
    def render_checked_state(self) -> None:
        for row in range(self.model.rowCount()):
            pkg_item = self.model.item(row, 1)
            vcode_item = self.model.item(row, 2)
            item = self.model.item(row, 5)
            if not pkg_item or not vcode_item or not item:
                continue
            key = (pkg_item.text(), vcode_item.text())
            state = self.checked_state.get(key, False)
            item.setText("●" if state else "")

