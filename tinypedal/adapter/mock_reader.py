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
Mock API data reader for test mode
"""

from __future__ import annotations

import math

from ..calculation import min_nonzero
from ..constant import DATA
from ..formatter import strip_invalid_char
from . import _reader
from .mock_data import END_ET, TRACK_NAME, Car, MockSession

COMPOUND_NAME = ("Soft", "Medium", "Hard", "Wet")
CAMBER = (-0.056, -0.056, -0.031, -0.031)
TOE = (-0.0003, 0.0003, 0.0005, -0.0005)
RACE_START_TIME_OF_DAY = 14 * 3600.0


class DataAdapter:
    """Access simulated data"""

    __slots__ = ("sim",)

    def __init__(self, sim: MockSession) -> None:
        self.sim = sim

    def car(self, index: int | None = None) -> Car:
        """Get car by index, local player if not specified"""
        sim = self.sim
        sim.update()
        cars = sim.cars
        if index is None or not 0 <= index < len(cars):
            return cars[sim.player]
        return cars[index]


class State(_reader.State, DataAdapter):
    """State"""

    __slots__ = ()

    def active(self) -> bool:
        self.sim.update()
        return True

    def paused(self) -> bool:
        return False

    def resets(self) -> int:
        return self.sim.resets

    def version(self) -> str:
        return "test"


class Brake(_reader.Brake, DataAdapter):
    """Brake"""

    __slots__ = ()

    def compound_name(self, index: int | None = None) -> tuple[str, str]:
        return "", ""

    def bias_front(self, index: int | None = None) -> float:
        return 0.56 if self.car(index).hyper else 0.60

    def migration(self, index: int | None = None) -> float:
        return 0.0

    def pressure(self, index: int | None = None, scale: float = 1) -> tuple[float, ...]:
        brake = self.car(index).brake
        front = brake * scale
        rear = brake * 0.75 * scale
        return front, front, rear, rear

    def temperature(self, index: int | None = None) -> tuple[float, ...]:
        return tuple(self.car(index).brake_temp)

    def wear(self, index: int | None = None) -> tuple[float, ...]:
        return tuple(self.car(index).brake_wear)


class ElectricMotor(_reader.ElectricMotor, DataAdapter):
    """Electric motor"""

    __slots__ = ()

    def state(self, index: int | None = None) -> int:
        return self.car(index).motor_state

    def battery_charge(self, index: int | None = None) -> float:
        car = self.car(index)
        return car.battery if car.hybrid else 0.0

    def rpm(self, index: int | None = None) -> float:
        car = self.car(index)
        return car.rpm * 2.2 if car.motor_state == 2 else 0.0

    def torque(self, index: int | None = None) -> float:
        car = self.car(index)
        if car.motor_state == 2:
            return 180.0
        if car.motor_state == 3:
            return -90.0 * car.brake
        return 0.0

    def motor_temperature(self, index: int | None = None) -> float:
        car = self.car(index)
        return 62.0 + 12.0 * (car.motor_state > 1) if car.hybrid else 0.0

    def water_temperature(self, index: int | None = None) -> float:
        return 55.0 if self.car(index).hybrid else 0.0

    def regeneration_level(self, index: int | None = None) -> float:
        return self.car(index).regen


class Engine(_reader.Engine, DataAdapter):
    """Engine"""

    __slots__ = ()

    def gear(self, index: int | None = None) -> int:
        return self.car(index).gear

    def gear_max(self, index: int | None = None) -> int:
        return self.car(index).gears

    def rpm(self, index: int | None = None) -> float:
        return self.car(index).rpm

    def rpm_max(self, index: int | None = None) -> float:
        return self.car(index).rpm_max

    def torque(self, index: int | None = None) -> float:
        return self.car(index).torque

    def turbo(self, index: int | None = None) -> float:
        return 0.0

    def oil_temperature(self, index: int | None = None) -> float:
        return self.car(index).oil

    def water_temperature(self, index: int | None = None) -> float:
        return self.car(index).water

    def exhaust_temperature(self, index: int | None = None) -> float:
        return 0.0

    def lift_and_coast_progress(self, index: int | None = None) -> float:
        return 0.0

    def fuel(self, index: int | None = None) -> float:
        return self.car(index).fuel

    def fuel_fraction(self, index: int | None = None) -> float:
        car = self.car(index)
        return car.fuel / car.tank

    def tank_capacity(self, index: int | None = None) -> float:
        return self.car(index).tank

    def virtual_energy(self, index: int | None = None) -> float:
        return self.car(index).ve

    def max_virtual_energy(self) -> float:
        return 0.0

    def absolute_refill(self) -> float:
        car = self.car()
        return (1.0 - car.ve) * 100 if car.hyper else car.tank - car.fuel


class Inputs(_reader.Inputs, DataAdapter):
    """Inputs"""

    __slots__ = ()

    def throttle(self, index: int | None = None) -> float:
        return self.car(index).throttle

    def throttle_raw(self, index: int | None = None) -> float:
        return self.car(index).throttle

    def brake(self, index: int | None = None) -> float:
        return self.car(index).brake

    def brake_raw(self, index: int | None = None) -> float:
        return self.car(index).brake

    def clutch(self, index: int | None = None) -> float:
        return 1.0 if self.car(index).gear == 0 else 0.0

    def clutch_raw(self, index: int | None = None) -> float:
        return self.clutch(index)

    def steering(self, index: int | None = None) -> float:
        return self.car(index).steer

    def steering_range(self, index: int | None = None) -> float:
        return 540.0

    def force_feedback(self) -> float:
        return max(-1.0, min(1.0, self.car().lat_accel / 30.0))


class Lap(_reader.Lap, DataAdapter):
    """Lap"""

    __slots__ = ()

    def completed(self, index: int | None = None) -> int:
        return self.car(index).laps

    def track_length(self) -> float:
        return self.sim.track.length

    def distance(self, index: int | None = None) -> float:
        return self.car(index).s

    def progress(self, index: int | None = None) -> float:
        return self.car(index).s / self.sim.track.length

    def maximum(self) -> int:
        return 2147483647  # time-limited race

    def remaining(self, index: int | None = None) -> float:
        car = self.car(index)
        return max(self.maximum() - car.laps - car.s / self.sim.track.length, 0.0)

    def sector_index(self, index: int | None = None) -> int:
        return self.car(index).sector

    def safety_car_distance(self) -> float:
        return 0.0

    def safety_car_active(self) -> bool:
        return False


class Session(_reader.Session, DataAdapter):
    """Session"""

    __slots__ = ()

    def combo_name(self) -> str:
        return strip_invalid_char(f"{TRACK_NAME} - {self.car().klass}")

    def track_name(self) -> str:
        return strip_invalid_char(TRACK_NAME)

    def identifier(self) -> tuple[int, int, int]:
        car = self.car()
        return int(END_ET * 100 + 10), int(self.sim.et), car.laps

    def elapsed(self) -> float:
        self.sim.update()
        return self.sim.et

    def remaining(self) -> float:
        self.sim.update()
        return max(END_ET - self.sim.et, 0.0)

    def session_type(self) -> int:
        return 4

    def finish_type(self, as_lap: bool | None = None) -> int:
        return 0

    def in_race(self) -> bool:
        return True

    def private_qualifying(self) -> bool:
        return False

    def pit_open(self) -> bool:
        return True

    def pre_race(self) -> bool:
        return False

    def green_flag(self) -> bool:
        return True

    def blue_flag(self, index: int | None = None) -> bool:
        return self.sim.blue_flag(self.car(index))

    def yellow_flag(self) -> bool:
        self.sim.update()
        return self.sim.yellow_flag()

    def start_lights(self) -> int:
        return -1

    def track_temperature(self) -> float:
        self.sim.update()
        return self.sim.track_temp

    def ambient_temperature(self) -> float:
        self.sim.update()
        return self.sim.ambient_temp

    def raininess(self) -> float:
        self.sim.update()
        return self.sim.rain

    def wetness(self) -> float:
        self.sim.update()
        return self.sim.wetness

    @staticmethod
    def _sky_type(rain: float, cloud: int) -> int:
        if rain <= 0:
            return cloud
        for limit, sky in ((0.10, 5), (0.15, 6), (0.20, 7), (0.40, 8), (0.60, 9)):
            if rain <= limit:
                return sky
        return 10

    def weather_forecast(self) -> tuple[tuple[float, int, float, float], ...]:
        self.sim.update()
        remaining = END_ET - self.sim.et
        nodes = []
        for minutes in (10, 20, 30, 40):
            if minutes * 60 > remaining:
                break
            rain, cloud = self.sim.weather_at(self.sim.et + minutes * 60)
            nodes.append((
                float(minutes),
                self._sky_type(rain, cloud),
                24.0 - 3.0 * min(rain * 5, 1.0),
                min(0.05 + rain / 0.18 * 0.85, 1.0),
            ))
        return tuple(nodes)

    def cloud_coverage(self) -> int:
        self.sim.update()
        return self._sky_type(self.sim.rain, self.sim.cloud)

    def grip_level(self) -> float:
        return 1.0

    def track_time(self, scale: int = 1) -> float:
        self.sim.update()
        return RACE_START_TIME_OF_DAY + self.sim.et

    def time_scale(self) -> int:
        return 1

    def limits_points(self) -> float:
        return 0.0

    def cut_points(self, index: int | None = None) -> float:
        return 0.0

    def wind_direction(self) -> float:
        return DATA.FLOAT_INF

    def wind_speed(self) -> float:
        return 0.0


class Switch(_reader.Switch, DataAdapter):
    """Switch"""

    __slots__ = ()

    def tc_level(self, index: int | None = None) -> int:
        return 4

    def tc_cut_level(self, index: int | None = None) -> int:
        return 5 if self.car(index).hyper else -1

    def tc_slip_level(self, index: int | None = None) -> int:
        return 3 if self.car(index).hyper else -1

    def abs_level(self, index: int | None = None) -> int:
        return -1 if self.car(index).hyper else 4

    def motor_map_level(self, index: int | None = None) -> int:
        return 1

    def brake_migration_level(self, index: int | None = None) -> int:
        return 2 if self.car(index).hyper else -1

    def front_arb_level(self, index: int | None = None) -> int:
        return 3

    def rear_arb_level(self, index: int | None = None) -> int:
        return 4

    def wipers(self, index: int | None = None) -> int:
        self.sim.update()
        return 2 if self.sim.rain > 0.05 else 0

    def headlights(self, index: int | None = None) -> int:
        self.sim.update()
        return int(self.sim.rain > 0.05)

    def ignition(self, index: int | None = None, stall_rpm: float = 100) -> int:
        return 2

    def speed_limiter(self, index: int | None = None) -> int:
        return int(self.car(index).pit in (2, 3, 4))

    def tc_active(self, index: int | None = None) -> bool:
        car = self.car(index)
        return car.throttle > 0.9 and car.v < 45 and abs(car.lat_accel) > 6

    def abs_active(self, index: int | None = None) -> bool:
        car = self.car(index)
        return not car.hyper and car.brake > 0.9

    def drs_status(self, index: int | None = None) -> int:
        return 0

    def auto_clutch(self) -> bool:
        return True


class Timing(_reader.Timing, DataAdapter):
    """Timing"""

    __slots__ = ()

    def elapsed(self, index: int | None = None) -> float:
        self.car(index)
        return self.sim.et

    def is_last_valid(self, index: int | None = None) -> bool:
        return self.car(index).last_lap > 0

    def current_laptime(self, index: int | None = None) -> float:
        car = self.car(index)
        return max(self.sim.et - car.lap_start, 0.0)

    def last_laptime(self, index: int | None = None) -> float:
        return self.car(index).last_lap

    def best_laptime(self, index: int | None = None) -> float:
        return self.car(index).best_lap

    def reference_laptime(self, index: int | None = None, laptime: float = 0) -> float:
        if 0 < laptime < DATA.MAX_SECONDS:
            return laptime
        init_time = min_nonzero((
            self.best_laptime(index),
            abs(self.last_laptime(index)),
            DATA.MAX_SECONDS,
        ))
        if 0 < init_time < DATA.MAX_SECONDS:
            return init_time
        return min_nonzero((self.estimated_laptime(index), DATA.MAX_SECONDS))

    def estimated_laptime(self, index: int | None = None) -> float:
        car = self.car(index)
        return car.best_lap * 0.998 if car.best_lap > 0 else car.last_lap

    def estimated_time_into(self, index: int | None = None) -> float:
        return self.current_laptime(index)

    def last_sector(self, index: int | None = None) -> float:
        car = self.car(index)
        if car.sector == 0 and car.last_lap > 0 < car.last_s2:
            return car.last_lap - car.last_s2
        if car.sector == 1:
            return car.cur_s1
        if car.sector == 2 and car.cur_s2 > 0 < car.cur_s1:
            return car.cur_s2 - car.cur_s1
        return 0.0


class Tyre(_reader.Tyre, DataAdapter):
    """Tyre (front left, front right, rear left, rear right)"""

    __slots__ = ()

    def compound_name(self, index: int | None = None) -> tuple[str, ...]:
        name = COMPOUND_NAME[self.car(index).compound]
        return name, name, name, name

    def compound_class(self, index: int | None = None) -> tuple[str, ...]:
        car = self.car(index)
        name = f"{car.klass} - {COMPOUND_NAME[car.compound]}"
        return name, name, name, name

    def surface_temperature_avg(self, index: int | None = None) -> tuple[float, ...]:
        return tuple(self.car(index).tyre_temp)

    def surface_temperature_ico(self, index: int | None = None) -> tuple[float, ...]:
        out = []
        for temp in self.car(index).tyre_temp:
            out.extend((temp + 5.0, temp + 1.0, temp - 6.0))
        return tuple(out)

    def inner_temperature_avg(self, index: int | None = None) -> tuple[float, ...]:
        return tuple(temp - 6.0 for temp in self.car(index).tyre_temp)

    def inner_temperature_ico(self, index: int | None = None) -> tuple[float, ...]:
        out = []
        for temp in self.car(index).tyre_temp:
            out.extend((temp - 1.0, temp - 5.0, temp - 12.0))
        return tuple(out)

    def pressure(self, index: int | None = None) -> tuple[float, ...]:
        return tuple(136.0 + 0.22 * (temp - 35.0) for temp in self.car(index).carcass)

    def load(self, index: int | None = None) -> tuple[float, ...]:
        return tuple(self.car(index).load)

    def wear(self, index: int | None = None) -> tuple[float, ...]:
        return tuple(self.car(index).wear)

    def puncture(self, index: int | None = None, threshold: float = 0.01) -> tuple[bool, ...]:
        return False, False, False, False

    def carcass_temperature(self, index: int | None = None) -> tuple[float, ...]:
        return tuple(self.car(index).carcass)

    def vertical_deflection(self, index: int | None = None) -> tuple[float, ...]:
        return tuple(load / 320.0 for load in self.car(index).load)

    def slip_angle(self, index: int | None = None) -> tuple[float, ...]:
        car = self.car(index)
        angle = 0.05 * max(-1.0, min(1.0, car.lat_accel / 18.0))
        return angle, angle, angle * 0.9, angle * 0.9


class Vehicle(_reader.Vehicle, DataAdapter):
    """Vehicle"""

    __slots__ = ()

    def incidents(self, index: int | None = None) -> int:
        return self.car(index).incidents

    def is_player(self, index: int = 0) -> bool:
        return self.sim.player == index

    def is_driving(self) -> bool:
        return True

    def player_index(self) -> int:
        return self.sim.player

    def slot_id(self, index: int | None = None) -> int:
        return self.car(index).index

    def driver_name(self, index: int | None = None) -> str:
        return self.car(index).driver

    def team_name(self, index: int | None = None) -> str:
        return self.car(index).team

    def vehicle_model(self, index: int | None = None) -> str:
        return self.car(index).model

    def class_name(self, index: int | None = None) -> str:
        return self.car(index).klass

    def same_class(self, index: int | None = None) -> bool:
        return self.car(index).klass == self.car().klass

    def total_vehicles(self) -> int:
        return len(self.sim.cars)

    def place(self, index: int | None = None) -> int:
        return self.car(index).place

    def qualification(self, index: int | None = None) -> int:
        return self.car(index).qualification

    def in_pits(self, index: int | None = None) -> bool:
        return self.car(index).pit in (2, 3, 4)

    def in_garage(self, index: int | None = None) -> bool:
        return False

    def in_paddock(self, index: int | None = None) -> int:
        return int(self.car(index).pit in (2, 3, 4))

    def number_pitstops(self, index: int | None = None, penalty: int = 0) -> int:
        return -penalty if penalty else self.car(index).pit_stops

    def number_penalties(self, index: int | None = None) -> int:
        return self.car(index).penalties

    def pit_request(self, index: int | None = None) -> bool:
        return self.car(index).pit == 1

    def pit_stop_time(self) -> float:
        return 30.0

    def repair_time(self) -> float:
        return 0.0

    def finish_state(self, index: int | None = None) -> int:
        return self.car(index).finish

    def orientation_yaw(self, index: int | None = None) -> float:
        car = self.car(index)
        return math.atan2(-car.hx, -car.hz)

    def position_xyz(self, index: int | None = None) -> tuple[float, float, float]:
        car = self.car(index)
        return car.x, car.y, car.z

    def position_longitudinal(self, index: int | None = None) -> float:
        return self.car(index).x

    def position_lateral(self, index: int | None = None) -> float:
        return -self.car(index).z

    def position_vertical(self, index: int | None = None) -> float:
        return self.car(index).y

    def acceleration_lateral(self, index: int | None = None) -> float:
        return self.car(index).lat_accel

    def acceleration_longitudinal(self, index: int | None = None) -> float:
        return -self.car(index).a  # positive while braking, same as game

    def acceleration_vertical(self, index: int | None = None) -> float:
        return 0.0

    def velocity_lateral(self, index: int | None = None) -> float:
        return 0.0

    def velocity_longitudinal(self, index: int | None = None) -> float:
        return self.car(index).v

    def velocity_vertical(self, index: int | None = None) -> float:
        return 0.0

    def speed(self, index: int | None = None) -> float:
        return self.car(index).v

    def downforce_front(self, index: int | None = None) -> float:
        car = self.car(index)
        return (0.42 if car.hyper else 0.45) * (1.0 if car.hyper else 0.55) * car.v * car.v

    def downforce_rear(self, index: int | None = None) -> float:
        car = self.car(index)
        return (0.58 if car.hyper else 0.55) * (1.0 if car.hyper else 0.55) * car.v * car.v

    def damage_severity(self, index: int | None = None) -> tuple[float, ...]:
        return (0.0,) * 8

    def aero_damage(self, index: int | None = None) -> float:
        return 0.0

    def integrity(self, index: int | None = None) -> float:
        return self.car(index).integrity

    def is_detached(self, index: int | None = None) -> bool:
        return False

    def impact_time(self, index: int | None = None) -> float:
        return 0.0

    def impact_position(self, index: int | None = None) -> tuple[float, float]:
        return 0.0, 0.0

    def setup(self) -> tuple[str, ...]:
        return (f'VehicleClassSetting="{self.car().klass}"', "UpgradeSetting=(0,0,0,0)")


class Wheel(_reader.Wheel, DataAdapter):
    """Wheel & suspension (front left, front right, rear left, rear right)"""

    __slots__ = ()

    def track_front(self, index: int | None = None) -> float:
        return 1680.0

    def track_rear(self, index: int | None = None) -> float:
        return 1650.0

    def wheelbase(self, index: int | None = None) -> float:
        return 3000.0

    def camber(self, index: int | None = None) -> tuple[float, ...]:
        return CAMBER

    def toe(self, index: int | None = None) -> tuple[float, ...]:
        return TOE

    def rotation(self, index: int | None = None) -> tuple[float, ...]:
        rot = self.car(index).v / 0.34
        return rot, rot, rot, rot

    def ride_height(self, index: int | None = None) -> tuple[float, ...]:
        v2 = self.car(index).v ** 2
        front = 52.0 - 0.0018 * v2
        rear = 70.0 - 0.0020 * v2
        return front, front, rear, rear

    def third_spring_deflection(self, index: int | None = None) -> tuple[float, ...]:
        return 0.0, 0.0, 0.0, 0.0

    def suspension_deflection(self, index: int | None = None) -> tuple[float, ...]:
        v2 = self.car(index).v ** 2
        front = 18.0 + 0.0015 * v2
        rear = 25.0 + 0.0020 * v2
        return front, front, rear, rear

    def suspension_force(self, index: int | None = None) -> tuple[float, ...]:
        return tuple(load * 0.9 for load in self.car(index).load)

    def suspension_damage(self, index: int | None = None) -> tuple[float, ...]:
        return 0.0, 0.0, 0.0, 0.0

    def position_vertical(self, index: int | None = None) -> tuple[float, ...]:
        return 0.0, 0.0, 0.0, 0.0

    def is_detached(self, index: int | None = None) -> tuple[bool, ...]:
        return False, False, False, False

    def offroad(self, index: int | None = None) -> int:
        return 0
