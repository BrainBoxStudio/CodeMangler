"""Small widgets shared across panels."""
from __future__ import annotations

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QMenu,
    QPushButton,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QWidget,
    QWidgetAction,
)

from app.config import MangleOptions

# (top-level group label, MangleOptions attr, [(sub-item label, MangleOptions attr), ...])
MANGLE_OPTION_GROUPS: tuple[tuple[str, str, tuple[tuple[str, str], ...]], ...] = (
    (
        "Sensitive Info",
        "sensitive_info",
        (
            ("Secrets", "sensitive_secrets"),
            ("PII", "sensitive_pii"),
            ("Network (IP / Hostname / URL)", "sensitive_network"),
            ("File Paths", "sensitive_paths"),
            ("Org / Project Names", "sensitive_org_project"),
        ),
    ),
    (
        "Code Identifiers",
        "code_identifiers",
        (
            ("Variables", "code_variables"),
            ("Functions / Methods", "code_functions"),
            ("Classes / Structs", "code_classes"),
            ("Interfaces", "code_interfaces"),
            ("Enums", "code_enums"),
            ("Namespaces / Modules", "code_namespaces"),
            ("Constants", "code_constants"),
        ),
    ),
)


class AnimatedArrowButton(QPushButton):
    """Circular button that pulses through colours while busy.

    `frames` is a sequence of glyphs cycled while animating; the middle frame
    (or the first, for short sequences) is used as the idle/resting label.
    """

    _COLORS = ["#2E86C1", "#3498DB", "#5DADE2", "#3498DB", "#2E86C1"]

    def __init__(
        self,
        frames: tuple[str, ...],
        tooltip: str = "",
        parent: QWidget | None = None,
    ) -> None:
        idle_text = frames[len(frames) // 2]
        super().__init__(idle_text, parent)
        self._frames = frames
        self._idle_text = idle_text
        self.setObjectName("arrowBtn")
        if tooltip:
            self.setToolTip(tooltip)
        self._timer = QTimer(self)
        self._timer.setInterval(160)
        self._timer.timeout.connect(self._tick)
        self._frame = 0
        self._apply_color("#2E86C1")

    def start_animation(self) -> None:
        self._frame = 0
        self.setEnabled(False)
        self._timer.start()

    def stop_animation(self) -> None:
        self._timer.stop()
        self.setText(self._idle_text)
        self._apply_color("#2E86C1")
        self.setEnabled(True)

    def _tick(self) -> None:
        idx = self._frame % len(self._frames)
        self.setText(self._frames[idx])
        self._apply_color(self._COLORS[idx % len(self._COLORS)])
        self._frame += 1

    def _apply_color(self, color: str) -> None:
        self.setStyleSheet(
            f"""
            QPushButton#arrowBtn {{
                background-color: {color};
                color: white;
                border-radius: 32px;
                font-size: 20px;
                font-weight: bold;
                min-width:  64px;
                max-width:  64px;
                min-height: 64px;
                max-height: 64px;
            }}
            """
        )


class CheckableTreeDropdown(QToolButton):
    """A button that opens a checkable tree popup — PySide6 has no built-in
    checkable nested-combo widget, so this hosts a QTreeWidget inside a QMenu
    via QWidgetAction. Two top-level tristate groups (Mangle Options:
    Sensitive Info / Code Identifiers), each with checkable sub-items
    matching MangleOptions' fields 1:1 (see MANGLE_OPTION_GROUPS above).
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("mangleDropdown")
        self.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.setToolTip("Choose what to mangle: sensitive values, code identifiers, or both.")

        self._top_items: dict[str, QTreeWidgetItem] = {}
        self._sub_items: dict[str, QTreeWidgetItem] = {}
        self._updating = False

        tree = QTreeWidget()
        tree.setObjectName("mangleTree")
        tree.setHeaderHidden(True)
        tree.setRootIsDecorated(True)

        for group_label, group_attr, children in MANGLE_OPTION_GROUPS:
            top = QTreeWidgetItem([group_label])
            top.setFlags(top.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            top.setCheckState(0, Qt.CheckState.Checked)
            tree.addTopLevelItem(top)
            self._top_items[group_attr] = top
            for child_label, child_attr in children:
                child = QTreeWidgetItem([child_label])
                child.setFlags(child.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                child.setCheckState(0, Qt.CheckState.Checked)
                top.addChild(child)
                self._sub_items[child_attr] = child
        tree.expandAll()
        tree.itemChanged.connect(self._on_item_changed)
        self._tree = tree

        menu = QMenu(self)
        action = QWidgetAction(menu)
        action.setDefaultWidget(tree)
        menu.addAction(action)
        self.setMenu(menu)

        self._update_button_text()

    def _on_item_changed(self, item: QTreeWidgetItem, _column: int) -> None:
        if self._updating:
            return
        self._updating = True
        try:
            if item.parent() is None:
                state = item.checkState(0)
                if state != Qt.CheckState.PartiallyChecked:
                    for i in range(item.childCount()):
                        item.child(i).setCheckState(0, state)
            else:
                parent = item.parent()
                states = {parent.child(i).checkState(0) for i in range(parent.childCount())}
                if states == {Qt.CheckState.Checked}:
                    parent.setCheckState(0, Qt.CheckState.Checked)
                elif states == {Qt.CheckState.Unchecked}:
                    parent.setCheckState(0, Qt.CheckState.Unchecked)
                else:
                    parent.setCheckState(0, Qt.CheckState.PartiallyChecked)
        finally:
            self._updating = False
        self._update_button_text()

    def _update_button_text(self) -> None:
        total = len(self._sub_items)
        checked = sum(
            1 for item in self._sub_items.values() if item.checkState(0) == Qt.CheckState.Checked
        )
        if checked == total:
            self.setText("Mangle: All")
        elif checked == 0:
            self.setText("Mangle: None")
        else:
            self.setText(f"Mangle: {checked} of {total}")

    def get_mangle_options(self) -> MangleOptions:
        kwargs = {attr: item.checkState(0) == Qt.CheckState.Checked for attr, item in self._sub_items.items()}
        for attr, item in self._top_items.items():
            kwargs[attr] = item.checkState(0) != Qt.CheckState.Unchecked
        return MangleOptions(**kwargs)
