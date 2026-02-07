from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QCheckBox, QWidget, QHBoxLayout
from PyQt5.QtGui import QColor

def add_checkbox(table, row: int, col: int,
                 checked: bool, pkg_key: tuple, pkg_map: dict):
    """
    Insère un vrai QCheckBox centré dans la cellule (row, col) de `table`
    et lie son état à pkg_map[pkg_key]["checked"].
    """
    cb = QCheckBox()
    cb.setChecked(checked)
    # Centrage
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.addWidget(cb)
    layout.setAlignment(Qt.AlignCenter)
    layout.setContentsMargins(0,0,0,0)
    table.setCellWidget(row, col, container)

    def on_state_changed(state: int):
        pkg_map[pkg_key]["checked"] = (state == Qt.Checked)

    cb.stateChanged.connect(on_state_changed)

def is_row_colored(table, row):
    item = table.item(row, 0)  # colonne 0
    if not item:
        return False
    color = item.background().color()
    # QColor par défaut est Qt.transparent ou blanc (dépend du style)
    return color != QColor(Qt.transparent) and color.alpha() > 0

# Not used yet : color a row
def _color_row(tablewidget, row: int, color: QColor):
    for col in range(tablewidget.columnCount()):
        item = tablewidget.item(row, col)
        if color is None:
            item.setBackground(QtGui.QBrush())  # set default color
        else:
            item.setBackground(QtGui.QBrush(color))