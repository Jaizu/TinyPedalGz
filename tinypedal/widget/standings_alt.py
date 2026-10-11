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
Standings Widget - alternative layout

Selected with "enable_alternative_layout" option in standings widget.
"""

from PySide2.QtCore import QRectF, Qt
from PySide2.QtGui import QColor, QPainter
from PySide2.QtWidgets import QWidget

from .. import api, minfo
from .. import calculation as calc
from ..constant import DATA
from ..formatter import random_color_class
from ..userfile.custom_image import load_brand_logo_image
from ._base import Overlay

SESSION_NAMES = ("TEST DAY", "PRACTICE", "QUALIFY", "WARM UP", "RACE", "HOTLAP")

# Temporary fixed colors, layout/data first
COLOR_TEXT = "#FFFFFF"
COLOR_TEXT_DIM = "#9FB4CC"
COLOR_HEADER_BG = "#0C1624"
COLOR_ROW_BG = "#121E2E"
COLOR_ROW_PLAYER_BG = "#12305A"
COLOR_LOGO_BG = "#1A1A1A"

# Grid columns
COL_CLASS, COL_POS, COL_NUM, COL_DRV, COL_BRD, COL_GAP, COL_LAP = range(7)
TOTAL_COLUMNS = 7


class ClassLegend(QWidget):
    """Class color legend"""

    def __init__(self, parent, height: int, offset_y: int):
        super().__init__(parent)
        self.setFixedHeight(height)
        self.last = None
        self.classes = ()
        self.fg = QColor(COLOR_TEXT_DIM)
        self.bg = QColor(COLOR_HEADER_BG)
        self._offset_y = offset_y

    def paintEvent(self, event):
        """Draw"""
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.bg)
        size = max(self.height() // 3, 3)
        x_pos = self.width()
        metrics = painter.fontMetrics()
        # Draw from right to left
        for name, color in reversed(self.classes):
            text_width = metrics.horizontalAdvance(name)
            x_pos -= text_width + size
            painter.setPen(self.fg)
            painter.drawText(
                QRectF(x_pos, self._offset_y, text_width, self.height()),
                Qt.AlignLeft | Qt.AlignVCenter, name,
            )
            x_pos -= size * 2
            painter.fillRect(
                QRectF(x_pos, (self.height() - size) / 2, size, size), QColor(color))
            x_pos -= size


class Realtime(Overlay):
    """Draw widget"""

    def __init__(self, config, widget_name):
        # Assign base setting
        super().__init__(config, widget_name)
        layout = self.set_grid_layout(gap_vert=self.wcfg["bar_gap"], gap_hori=0)
        self.set_primary_layout(layout=layout)

        # Config font
        font = self.config_font(
            self.wcfg["font_name"],
            self.wcfg["font_size"],
            self.wcfg["font_weight"],
        )
        self.setFont(font)
        font_m = self.get_font_metrics(font)

        # Config variable
        bar_padx = self.set_padding(self.wcfg["font_size"], self.wcfg["bar_padding"])
        self.drv_width = max(int(self.wcfg["driver_name_width"]), 1)
        self.brd_width = max(int(self.wcfg["brand_logo_width"]), 1)
        self.brd_height = max(self.wcfg["font_size"], 1)
        self.gap_decimals = 3
        self.show_class_timegap = (self.wcfg["enable_multi_class_split_mode"]
            and self.wcfg["show_time_gap_from_same_class"])
        self.show_class_separator = self.wcfg["split_gap"] > 0
        self.height_def = font_m.height
        self.height_gap = self.wcfg["split_gap"]
        self.pixmap_brandlogo = {}

        if self.wcfg["enable_single_class_exclusive_mode"]:
            max_display_vehicles = self.wcfg["maximum_vehicles_exclusive_mode"]
        elif self.wcfg["enable_multi_class_split_mode"]:
            max_display_vehicles = self.wcfg["maximum_vehicles_split_mode"]
        else:
            max_display_vehicles = self.wcfg["maximum_vehicles_combined_mode"]
        self.veh_range = min(max(int(max_display_vehicles), 5), 126)
        self.row_visible = [False] * self.veh_range

        def text_bars(chars: int, align=Qt.AlignCenter, fg=COLOR_TEXT, bg=COLOR_ROW_BG, count=1):
            return self.set_rawtext(
                width=chars * font_m.width + bar_padx,
                fixed_height=font_m.height,
                offset_y=font_m.voffset,
                fg_color=fg,
                bg_color=bg,
                alignment=align,
                count=count,
            )

        # Header: session name, lap counter, remaining time
        self.bar_session = text_bars(8, Qt.AlignLeft | Qt.AlignVCenter, COLOR_TEXT_DIM, COLOR_HEADER_BG)
        self.bar_laps = text_bars(10, Qt.AlignCenter, COLOR_TEXT, COLOR_HEADER_BG)
        self.bar_time = text_bars(8, Qt.AlignRight | Qt.AlignVCenter, COLOR_TEXT, COLOR_HEADER_BG)
        layout.addWidget(self.bar_session, 0, COL_CLASS, 1, 4)
        layout.addWidget(self.bar_laps, 0, COL_BRD, 1, 2)
        layout.addWidget(self.bar_time, 0, COL_LAP)

        # Rows
        side = max(font_m.width // 2, 2)
        self.bars_cls = self.set_rawtext(
            fixed_width=side, fixed_height=font_m.height, count=self.veh_range)
        self.bars_pos = text_bars(2, count=self.veh_range)
        self.bars_num = text_bars(4, Qt.AlignLeft | Qt.AlignVCenter, COLOR_TEXT_DIM, count=self.veh_range)
        self.bars_drv = text_bars(self.drv_width, Qt.AlignLeft | Qt.AlignVCenter, count=self.veh_range)
        self.bars_brd = self.set_rawimage(
            width=self.brd_width, fixed_height=font_m.height, bg_color=COLOR_LOGO_BG, count=self.veh_range)
        self.bars_gap = text_bars(8, Qt.AlignRight | Qt.AlignVCenter, COLOR_TEXT_DIM, count=self.veh_range)
        self.bars_lap = text_bars(9, Qt.AlignRight | Qt.AlignVCenter, count=self.veh_range)
        self.rows = tuple(zip(
            self.bars_cls, self.bars_pos, self.bars_num, self.bars_drv,
            self.bars_brd, self.bars_gap, self.bars_lap,
        ))
        for idx, row in enumerate(self.rows):
            for column, bar in enumerate(row):
                layout.addWidget(bar, idx + 1, column)
                if idx >= 1:
                    bar.hide()

        # Footer: class legend
        self.legend = ClassLegend(self, font_m.height, font_m.voffset)
        layout.addWidget(self.legend, self.veh_range + 1, 0, 1, TOTAL_COLUMNS)

    def timerEvent(self, event):
        """Update when vehicle on track"""
        in_race = api.read.session.in_race()
        self.update_header()

        standings_list = minfo.relative.standings
        total_std_idx = len(standings_list) - 1  # skip final -1 index
        legend = {}

        for idx in range(self.veh_range):
            if idx < total_std_idx:
                std_idx = standings_list[idx]
            else:
                std_idx = -2

            # Row state: 0 - show, 1 - draw gap, 2 - hide
            if std_idx >= -1:
                self.row_visible[idx] = True
                state = int(std_idx == -1)
            elif not self.row_visible[idx]:
                continue
            else:
                self.row_visible[idx] = False
                state = 2

            veh_info = minfo.vehicles.dataSet[std_idx]
            if state != 0:
                self.toggle_row(idx, state)
                continue
            self.toggle_row(idx, 0)
            hi_player = veh_info.isPlayer
            if veh_info.vehicleClass not in legend:
                legend[veh_info.vehicleClass] = self.class_color(veh_info.vehicleClass)

            row = self.rows[idx]
            bar_cls, bar_pos, bar_num, bar_drv, bar_brd, bar_gap, bar_lap = row
            bg = COLOR_ROW_PLAYER_BG if hi_player else COLOR_ROW_BG

            # Rank/flag columns are not available from game data
            self.update_text(bar_cls, (veh_info.vehicleClass, state), "", COLOR_TEXT,
                self.class_color(veh_info.vehicleClass))
            self.update_text(bar_pos, (veh_info.positionOverall, hi_player, state),
                f"{veh_info.positionOverall}", COLOR_TEXT, bg)
            self.update_text(bar_num, (veh_info.carNumber, hi_player, state),
                veh_info.carNumber, COLOR_TEXT_DIM, bg)
            self.update_text(bar_drv, (veh_info.driverName, hi_player, state),
                f"{veh_info.driverName:<{self.drv_width}.{self.drv_width}}", COLOR_TEXT, bg)
            self.update_logo(bar_brd, (veh_info.brandName, state), veh_info.brandName)

            if in_race:
                if self.show_class_timegap:
                    gap = self.gap_to_leader_race(veh_info.gapBehindLeaderInClass, veh_info.positionInClass)
                else:
                    gap = self.gap_to_leader_race(veh_info.gapBehindLeader, veh_info.positionOverall)
            elif self.show_class_timegap:
                gap = self.gap_to_leader_best(veh_info.bestLapTime, veh_info.classBestLapTime)
            else:
                gap = self.gap_to_leader_best(veh_info.bestLapTime, minfo.vehicles.leaderBestLapTime)
            self.update_text(bar_gap, (gap, hi_player, state), gap, COLOR_TEXT_DIM, bg)

            if veh_info.pitTimer.pitting and (in_race or self.wcfg["show_best_laptime"]):
                laptime = self.set_pittime(veh_info.inPit, veh_info.pitTimer.elapsed)
            elif in_race:
                laptime = self.set_laptime(veh_info.lastLapTime, veh_info.isValidLap)
            else:
                laptime = self.set_laptime(veh_info.bestLapTime)
            self.update_text(bar_lap, (laptime, hi_player, state), laptime, COLOR_TEXT, bg)

        self.update_legend(tuple(legend.items()))

    # GUI update methods
    def update_header(self):
        """Session name, lap counter, remaining time"""
        session_name = SESSION_NAMES[api.read.session.session_type()]
        lap_number = api.read.lap.completed() + 1
        if api.read.session.finish_type(minfo.vehicles.finishAsLap):
            text_laps = f"LAP {lap_number} / {api.read.lap.maximum()}"
        else:
            text_laps = f"LAP {lap_number}"
        remaining = api.read.session.remaining() - minfo.vehicles.finishTimeOffset
        text_time = calc.sec2sessiontime(max(remaining, 0))
        self.update_text(self.bar_session, session_name, session_name, COLOR_TEXT_DIM, COLOR_HEADER_BG)
        self.update_text(self.bar_laps, text_laps, text_laps, COLOR_TEXT, COLOR_HEADER_BG)
        self.update_text(self.bar_time, text_time, text_time, COLOR_TEXT, COLOR_HEADER_BG)

    @staticmethod
    def update_text(target, key, text, fg, bg):
        """Update text bar if data changed"""
        if target.last != key:
            target.last = key
            target.text = text
            target.fg, target.bg = fg, bg
            target.update()

    def update_logo(self, target, key, brand_name):
        """Update brand logo"""
        if target.last != key:
            target.last = key
            target.image = self.set_brand_logo(brand_name)
            target.update()

    def update_legend(self, classes):
        """Update class legend"""
        if self.legend.last != classes:
            self.legend.last = classes
            self.legend.classes = classes
            self.legend.update()

    def toggle_row(self, idx, state):
        """Show, hide, or turn row into class separator gap"""
        row = self.rows[idx]
        if row[0].state == state:
            return
        for bar in row:
            bar.state = state
            if state == 1 and self.show_class_separator:
                bar.clear()
                bar.last = None
                bar.setFixedHeight(self.height_gap)
                bar.show()
            else:
                bar.last = None  # force redraw when shown again
                bar.setHidden(state != 0)
                bar.setFixedHeight(self.height_def)

    # Additional methods
    def class_color(self, class_name: str) -> str:
        """Vehicle class color"""
        style = self.cfg.user.classes.get(class_name)
        if style is not None:
            return style["color"]
        if class_name:
            return random_color_class(class_name)
        return COLOR_ROW_BG

    def set_brand_logo(self, brand_name: str):
        """Set brand logo"""
        if brand_name not in self.pixmap_brandlogo:
            self.pixmap_brandlogo[brand_name] = load_brand_logo_image(
                filepath=self.cfg.path.brand_logo,
                filename=brand_name,
                max_width=self.brd_width,
                max_height=self.brd_height,
            )
        return self.pixmap_brandlogo[brand_name]

    @staticmethod
    def set_laptime(laptime, valid: bool = True):
        """Set lap time"""
        if 0 < laptime < DATA.MAX_SECONDS:
            if valid:
                return calc.sec2laptime_full(laptime)
            return f"*{calc.sec2laptime_full(laptime)}"
        return DATA.TEXT_NOLAPTIME

    @staticmethod
    def set_pittime(inpit, pit_time):
        """Set pit time"""
        if 0 < pit_time < DATA.MAX_SECONDS:
            return f"{'PIT' if inpit else 'OUT'}{pit_time:>5.1f}"
        return DATA.TEXT_NOLAPTIME

    def gap_to_leader_best(self, player_best, leader_best):
        """Gap to leader's best laptime"""
        time = player_best - leader_best
        if time == 0 and player_best > 0:
            return "-"
        if time < 0 or player_best < 1:
            return "-"
        return f"+{time:.{self.gap_decimals}f}"

    def gap_to_leader_race(self, gap_behind, position):
        """Gap to race leader"""
        if position == 1:
            return "-"
        if isinstance(gap_behind, int):
            return f"+{gap_behind:.0f}L"
        return f"+{gap_behind:.{self.gap_decimals}f}"
