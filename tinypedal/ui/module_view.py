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

import math

from PySide2.QtCore import QPoint, QRect, QRectF, QSize, Qt, Slot
from PySide2.QtGui import QColor, QPainter, QPainterPath, QPalette
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
        self.listbox_module.setGridSize(QSize(UIScaler.size(18), UIScaler.size(7)))
        self.listbox_module.setSpacing(UIScaler.pixel(0))
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
            item.setSizeHint(QSize(UIScaler.size(18), UIScaler.size(7)))
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
        self.setAttribute(Qt.WA_StyledBackground, True)

        label_name = QLabel(format_module_name(module_name))
        label_name.setWordWrap(True)
        label_name.setAlignment(Qt.AlignCenter)

        self.button_toggle = ToggleSwitch()
        self.button_toggle.setObjectName("buttonToggle")
        self.button_toggle.setChecked(self.is_enabled())
        self.button_toggle.setCursor(Qt.PointingHandCursor)
        self.button_toggle.clicked.connect(self.toggle_state)

        button_config = GearButton()
        button_config.setObjectName("buttonConfig")
        button_config.setToolTip("Configure plugin")
        button_config.setAccessibleName("Configure plugin")
        button_config.setCursor(Qt.PointingHandCursor)
        button_config.pressed.connect(self.open_config_dialog)

        layout_button = QHBoxLayout()
        layout_button.setContentsMargins(0, 0, 0, 0)
        layout_button.addStretch(1)
        layout_button.addWidget(self.button_toggle)
        layout_button.addWidget(button_config)

        layout_button.addStretch(1)
        layout_button.setSpacing(UIScaler.pixel(4))

        layout_item = QVBoxLayout()
        layout_item.setContentsMargins(UIScaler.pixel(5), UIScaler.pixel(4), UIScaler.pixel(5), UIScaler.pixel(4))
        layout_item.setSpacing(UIScaler.pixel(3))
        layout_item.addWidget(label_name)
        layout_item.addLayout(layout_button)

        # Outer margin creates the gap between cards
        layout_outer = QVBoxLayout()
        gap = UIScaler.pixel(5)
        layout_outer.setContentsMargins(gap, gap, gap, gap)
        self.card = QWidget(self)
        self.card.setObjectName("moduleCard")
        self.card.setAttribute(Qt.WA_StyledBackground, True)
        self.card.setLayout(layout_item)
        layout_outer.addWidget(self.card)
        self.setLayout(layout_outer)

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
    """Pill-shaped switch with an integrated state label"""

    def sizeHint(self) -> QSize:
        return QSize(UIScaler.size(6.2), UIScaler.size(2.1))

    def hitButton(self, pos: QPoint) -> bool:
        return self.rect().contains(pos)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        width = self.width()
        height = self.height()
        inset = UIScaler.pixel(1)
        knob_size = height - UIScaler.pixel(6)
        knob_margin = (height - knob_size) / 2
        pill = QRectF(inset, inset, width - inset * 2, height - inset * 2)
        knob_y = (height - knob_size) / 2

        painter.setPen(Qt.NoPen)
        if self.isChecked():
            painter.setBrush(QColor("#00D6A3"))
            painter.drawRoundedRect(pill, height / 2, height / 2)
            painter.setPen(QColor("#12372F"))
            knob_x = width - knob_margin - knob_size
            text_rect = QRect(0, 0, int(knob_x), height)
            text = "ON"
        else:
            painter.setBrush(Qt.transparent)
            painter.setPen(Qt.white)
            painter.drawRoundedRect(pill, height / 2, height / 2)
            knob_x = knob_margin
            text_rect = QRect(int(knob_x + knob_size), 0, width - int(knob_x + knob_size), height)
            text = "OFF"

        font = painter.font()
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(Qt.white if not self.isChecked() else QColor("#12372F"))
        painter.drawText(text_rect, Qt.AlignCenter, text)
        painter.setPen(Qt.NoPen)
        painter.setBrush(Qt.white)
        painter.drawEllipse(QRectF(knob_x, knob_y, knob_size, knob_size))


class GearButton(QPushButton):
    """Icon button drawing a theme-aware gear"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(QSize(UIScaler.size(2.3), UIScaler.size(2.3)))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(self.palette().color(QPalette.ButtonText))

        radius = min(self.width(), self.height()) * 0.47
        center_x = self.width() / 2
        center_y = self.height() / 2
        path = QPainterPath()
        path.setFillRule(Qt.OddEvenFill)
        points = ((0, 0.78), (6, 0.78), (6, 1), (22, 1), (22, 0.78), (45, 0.78))
        for tooth in range(8):
            base_angle = tooth * 45 - 90
            for angle_offset, scale in points:
                angle = math.radians(base_angle + angle_offset)
                point_x = center_x + radius * scale * math.cos(angle)
                point_y = center_y + radius * scale * math.sin(angle)
                if path.elementCount() == 0:
                    path.moveTo(point_x, point_y)
                else:
                    path.lineTo(point_x, point_y)
        path.closeSubpath()
        hole_radius = radius * 0.4
        path.addEllipse(center_x - hole_radius, center_y - hole_radius, hole_radius * 2, hole_radius * 2)
        painter.drawPath(path)

    def sizeHint(self) -> QSize:
        return QSize(UIScaler.size(2.3), UIScaler.size(2.3))
