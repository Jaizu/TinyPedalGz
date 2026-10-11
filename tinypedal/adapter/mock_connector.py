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
Mock API connector (test mode, no game required)
"""

from ..constant import API
from . import mock_reader
from ._connector import APIDataReader, Connector
from .mock_data import MockSession


class MockLMU(Connector):
    """Simulated LMU data for testing overlays"""

    NAME = API.NAME_LMU  # behave as LMU for config, user files & modules
    LEGACY = False
    __slots__ = ("_sim",)

    def __init__(self):
        self._sim = MockSession()

    def start(self):
        self._sim.start()

    def stop(self):
        """Nothing to stop"""

    def reader(self) -> APIDataReader:
        sim = self._sim
        return APIDataReader(
            mock_reader.State(sim),
            mock_reader.Brake(sim),
            mock_reader.ElectricMotor(sim),
            mock_reader.Engine(sim),
            mock_reader.Inputs(sim),
            mock_reader.Lap(sim),
            mock_reader.Session(sim),
            mock_reader.Switch(sim),
            mock_reader.Timing(sim),
            mock_reader.Tyre(sim),
            mock_reader.Vehicle(sim),
            mock_reader.Wheel(sim),
        )

    def setup(self, config: dict):
        """Ignore game connection settings"""
