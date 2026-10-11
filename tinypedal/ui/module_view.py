#  TinyPedal is an open-source overlay application for racing simulation.
#  Copyright (C) 2022-2026 TinyPedal developers, see contributors.md file
#
#  This file is part of TinyPedal.
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
Module & widget list view
"""

from PySide2.QtCore import QRect, QSize, Qt, Slot
from PySide2.QtGui import QPainter, QPalette
from PySide2.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QListView,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .. import app_signal, cfg
from ..formatter import format_module_name
from ..module_control import ModuleControl
from ._common import UIScaler
from .config import UserConfig


class ModuleList(QWidget):
    """Module & widget list view"""

    def __init__(self, parent, module_control: ModuleControl):
        """Initialize module list setting

        Args:
            module_control: Module control (or widget) object.
        """
        super().__init__(parent)
        self.module_control = module_control

        # Label
        self.label_loaded = QLabel("")

        # List box
        self.listbox_module = QListWidget(self)
        self.listbox_module.setViewMode(QListView.IconMode)
        self.listbox_module.setMovement(QListView.Static)
        self.listbox_module.setResizeMode(QListView.Adjust)
        self.listbox_module.setWrapping(True)
        self.listbox_module.setGridSize(QSize(UIScaler.size(18), UIScaler.size(6)))
        self.listbox_module.setSpacing(UIScaler.pixel(4))
        self.create_list()

        # Button
        button_enable = QPushButton("Enable All")
        button_enable.clicked.connect(self.module_button_enable_all)

        button_disable = QPushButton("Disable All")
        button_disable.clicked.connect(self.module_button_disable_all)

        layout_button = QHBoxLayout()
        layout_button.addWidget(button_enable)
        layout_button.addStretch(1)
        layout_button.addWidget(button_disable)

        # Layout
        layout_main = QVBoxLayout()
        layout_main.addWidget(self.label_loaded)
        layout_main.addWidget(self.listbox_module)
        layout_main.addLayout(layout_button)
        margin = UIScaler.pixel(6)
        layout_main.setContentsMargins(margin, margin, margin, margin)
        self.setLayout(layout_main)

    def create_list(self):
        """Create module list"""
        for _name in self.module_control.names:
            module_item = ModuleControlItem(self, _name, self.module_control)
            item = QListWidgetItem()
            item.setSizeHint(QSize(UIScaler.size(18), UIScaler.size(6)))
            self.listbox_module.addItem(item)
            self.listbox_module.setItemWidget(item, module_item)
        self.listbox_module.setCurrentRow(0)

    @Slot(bool)  # type: ignore[operator]
    def refresh(self):
        """Refresh module & button toggle state"""
        listbox_module = self.listbox_module
        for row_index in range(listbox_module.count()):
            item = listbox_module.item(row_index)
            listbox_module.itemWidget(item).update_state()

    def refresh_label(self):
        """Refresh label text"""
        self.label_loaded.setText(
            f"Enabled: <b>{self.module_control.number_active}/"
            f"{self.module_control.number_total}</b>"
        )

    def module_button_enable_all(self):
        """Enable all modules"""
        if self.module_control.number_active != self.module_control.number_total:
            if self.confirm_batch_toggle("Enable"):
                self.module_control.enable_all()
                app_signal.refresh.emit(True)

    def module_button_disable_all(self):
        """Disable all modules"""
        if self.module_control.number_active:
            if self.confirm_batch_toggle("Disable"):
                self.module_control.disable_all()
                app_signal.refresh.emit(True)

    def confirm_batch_toggle(self, confirm_type: str) -> bool:
        """Batch toggle confirmation"""
        if not cfg.application["show_confirmation_for_batch_toggle"]:
            return True
        msg_text = f"<b>{confirm_type}</b> all {self.module_control.type_id}s?"
        confirm_msg = QMessageBox.question(
            self, "Confirm", msg_text,
            buttons=QMessageBox.Yes | QMessageBox.No,
            defaultButton=QMessageBox.No,
        )
        return confirm_msg == QMessageBox.Yes


class ModuleControlItem(QWidget):
    """Module control item"""

    def __init__(self, parent, module_name: str, module_control: ModuleControl):
        """Initialize list box setting

        Args:
            module_name: Module (or widget) name string.
            module_control: Module control (or widget) object.
        """
        super().__init__(parent)
        self._parent = parent
        self.module_name = module_name
        self.module_control = module_control

        label_name = QLabel(format_module_name(module_name))
        label_name.setWordWrap(True)

        self.button_toggle = ToggleSwitch()
        self.button_toggle.setObjectName("buttonToggle")
        self.button_toggle.setChecked(self.is_enabled())
        self.button_toggle.clicked.connect(self.toggle_state)

        button_config = QPushButton("⚙")
        button_config.setObjectName("buttonConfig")
        button_config.setToolTip("Configure plugin")
        button_config.setAccessibleName("Configure plugin")
        button_config.pressed.connect(self.open_config_dialog)

        layout_button = QHBoxLayout()
        layout_button.setContentsMargins(0, 0, 0, 0)
        layout_button.setSpacing(UIScaler.pixel(2))
        layout_button.addStretch(1)
        layout_button.addWidget(button_config)
        layout_button.addWidget(self.button_toggle)

        layout_item = QVBoxLayout()
        layout_item.setContentsMargins(UIScaler.pixel(5), UIScaler.pixel(4), UIScaler.pixel(5), UIScaler.pixel(4))
        layout_item.setSpacing(UIScaler.pixel(2))
        layout_item.addWidget(label_name, stretch=1)
        layout_item.addLayout(layout_button)
        self.setLayout(layout_item)

    def is_enabled(self) -> bool:
        """Is module enabled"""
        return cfg.user.setting[self.module_name]["enable"]

    def toggle_state(self):
        """Toggle button state"""
        self.module_control.toggle(self.module_name)
        self._parent.refresh_label()

    def update_state(self):
        """Update button toggle state"""
        self.button_toggle.setChecked(self.is_enabled())
        self._parent.refresh_label()

    def open_config_dialog(self):
        """Config dialog"""
        _dialog = UserConfig(
            parent=self._parent,
            key_name=self.module_name,
            preset_name=cfg.filename.setting,
            config_type=self.module_control.type_id,
            user_setting=cfg.user.setting,
            default_setting=cfg.default.setting,
            reload_func=self.reload_module,
        )
        _dialog.open()

    def reload_module(self):
        """Reload module & button state"""
        self.module_control.reload(self.module_name)
        self.update_state()


class ToggleSwitch(QCheckBox):
    """Compact switch with a visible state label"""

    def sizeHint(self) -> QSize:
        return QSize(UIScaler.size(7.5), UIScaler.size(2.2))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        palette = self.palette()
        track_width = UIScaler.size(2.6)
        track_height = UIScaler.size(1.2)
        knob_size = UIScaler.size(0.9)
        label_width = self.width() - track_width - UIScaler.pixel(4)
        track_x = label_width + UIScaler.pixel(4)
        track_y = (self.height() - track_height) // 2

        painter.setPen(palette.color(QPalette.WindowText))
        painter.drawText(
            QRect(0, 0, label_width, self.height()),
            Qt.AlignLeft | Qt.AlignVCenter,
            "On" if self.isChecked() else "Off",
        )

        track_color = palette.color(QPalette.Highlight if self.isChecked() else QPalette.Mid)
        painter.setPen(Qt.NoPen)
        painter.setBrush(track_color)
        painter.drawRoundedRect(
            QRect(track_x, track_y, track_width, track_height),
            track_height / 2,
            track_height / 2,
        )

        knob_x = track_x + track_width - knob_size - UIScaler.pixel(2) if self.isChecked() else track_x + UIScaler.pixel(2)
        knob_y = track_y + (track_height - knob_size) // 2
        painter.setBrush(palette.color(QPalette.Base))
        painter.drawEllipse(QRect(knob_x, knob_y, knob_size, knob_size))
