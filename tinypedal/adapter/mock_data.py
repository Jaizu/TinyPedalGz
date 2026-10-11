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
Mock race simulation for test mode (no game required)

Simulates a multi-class endurance race (Hypercar + LMGT3) mid-way through:
traffic, pit stops, fuel / virtual energy burn, tyre wear & temperature,
weather changes, slow cars (yellow flags) and blue flags.
"""

from __future__ import annotations

import math
import random
import threading
import time

TRACK_NAME = "TinyPedal Test Circuit"  # unique name so real user data is never touched
PLAYER_INDEX = 4
START_ET = 1200.0  # session already 20 min in
END_ET = 3600.0  # 60 min race
UPDATE_INTERVAL = 0.04
MAX_STEP = 0.05

TRACK_SCALE = 1.5
TRACK_POINTS = 2000
LAT_ACCEL_LIMIT = 11.0
SPEED_MIN = 22.0
SPEED_MAX = 92.0
ACCEL_PROFILE = 6.0
BRAKE_PROFILE = 22.0

SECTOR1_END = 0.32
SECTOR2_END = 0.67

PIT_ENTRY = 350.0  # meters before finish line
PIT_BOX = 140.0  # meters after finish line
PIT_EXIT = 420.0
PIT_SPEED = 22.0
PIT_LANE_OFFSET = 14.0

# (driver, team, model, class, number)
GRID = (
    ("Kenji Arakawa", "Toyota Gazoo Racing", "Toyota GR010 - Hybrid", "Hypercar", 7),
    ("Marco Bianchi", "Ferrari AF Corse", "Ferrari 499P", "Hypercar", 51),
    ("Lukas Brandt", "Porsche Penske Motorsport", "Porsche 963", "Hypercar", 6),
    ("Tom Whitaker", "Cadillac Whelen", "Cadillac V-Series.R", "Hypercar", 311),
    ("You (Player)", "Toyota Gazoo Racing", "Toyota GR010 - Hybrid", "Hypercar", 8),
    ("Remi Fabre", "Peugeot TotalEnergies", "Peugeot 9X8", "Hypercar", 93),
    ("Jonas Keller", "BMW M Team WRT", "BMW M Hybrid V8", "Hypercar", 20),
    ("Pablo Ortega", "Alpine Endurance Team", "Alpine A424", "Hypercar", 35),
    ("Alex Novak", "Cadillac Hertz Team Jota", "Cadillac V-Series.R", "Hypercar", 12),
    ("Ryo Tanaka", "Porsche Proton Competition", "Porsche 963", "Hypercar", 99),
    ("Ian Mackay", "Ferrari AF Corse", "Ferrari 499P", "Hypercar", 83),
    ("Dario Rossi", "Alpine Endurance Team", "Alpine A424", "Hypercar", 36),
    ("Nick Hartley", "Akkodis ASP Team", "Lexus RC F LMGT3", "LMGT3", 78),
    ("Sven Lindqvist", "Manthey PureRxcing", "Porsche 911 GT3 R LMGT3", "LMGT3", 92),
    ("Chris Doyle", "Corvette Racing", "Chevrolet Corvette Z06 LMGT3.R", "LMGT3", 33),
    ("Mateo Silva", "Vista AF Corse", "Ferrari 296 LMGT3", "LMGT3", 21),
    ("Dan Fletcher", "Heart of Racing", "Aston Martin Vantage AMR LMGT3", "LMGT3", 27),
    ("Yuki Mori", "United Autosports", "McLaren 720S LMGT3 Evo", "LMGT3", 95),
    ("Felix Maurer", "WRT", "BMW M4 LMGT3", "LMGT3", 31),
    ("Leo Fischer", "Iron Lynx", "Lamborghini Huracan LMGT3 Evo", "LMGT3", 63),
)


def _clamp(value: float, low: float, high: float) -> float:
    return low if value < low else high if value > high else value


class Track:
    """Closed-loop track with uniform arc-length sampling"""

    def __init__(self):
        raw_count = 8000
        raw = []
        for i in range(raw_count):
            t = 2 * math.pi * i / raw_count
            raw.append((t, *self._point(t)))
        cum = [0.0]
        for i in range(1, raw_count + 1):
            _, x0, z0 = raw[i - 1]
            _, x1, z1 = raw[i % raw_count]
            cum.append(cum[-1] + math.hypot(x1 - x0, z1 - z0))
        self.length = cum[-1]
        n = TRACK_POINTS
        self.count = n
        self.step = self.length / n

        self.xs: list[float] = []
        self.zs: list[float] = []
        self.ys: list[float] = []
        self.hx: list[float] = []
        self.hz: list[float] = []
        self.curv: list[float] = []
        j = 0
        for k in range(n):
            target = k * self.step
            while cum[j + 1] < target:
                j += 1
            span = cum[j + 1] - cum[j]
            frac = (target - cum[j]) / span if span else 0.0
            t = 2 * math.pi * (j + frac) / raw_count
            x, z = self._point(t)
            dx, dz, ddx, ddz = self._derivative(t)
            speed2 = dx * dx + dz * dz
            norm = math.sqrt(speed2)
            self.xs.append(x)
            self.zs.append(z)
            self.ys.append(6.0 * math.sin(2 * t) + 3.0 * math.sin(3 * t))
            self.hx.append(dx / norm)
            self.hz.append(dz / norm)
            self.curv.append((dx * ddz - dz * ddx) / (speed2 * norm))

        self.speed = self._speed_profile()
        self.base_laptime = sum(self.step / v for v in self.speed)

    @staticmethod
    def _point(t: float) -> tuple[float, float]:
        s = TRACK_SCALE
        return (
            s * (800 * math.cos(t) + 250 * math.cos(3 * t)),
            s * (400 * math.sin(t) + 200 * math.sin(2 * t) + 60 * math.sin(3 * t)),
        )

    @staticmethod
    def _derivative(t: float) -> tuple[float, float, float, float]:
        s = TRACK_SCALE
        return (
            s * (-800 * math.sin(t) - 750 * math.sin(3 * t)),
            s * (400 * math.cos(t) + 400 * math.cos(2 * t) + 180 * math.cos(3 * t)),
            s * (-800 * math.cos(t) - 2250 * math.cos(3 * t)),
            s * (-400 * math.sin(t) - 800 * math.sin(2 * t) - 540 * math.sin(3 * t)),
        )

    def _speed_profile(self) -> list[float]:
        n = self.count
        speed = [
            _clamp(math.sqrt(LAT_ACCEL_LIMIT / max(abs(k), 1e-5)), SPEED_MIN, SPEED_MAX)
            for k in self.curv
        ]
        for _ in range(3):
            for i in range(2 * n):
                a, b = i % n, (i + 1) % n
                speed[b] = min(speed[b], math.sqrt(speed[a] ** 2 + 2 * ACCEL_PROFILE * self.step))
            for i in range(2 * n, 0, -1):
                a, b = i % n, (i - 1) % n
                speed[b] = min(speed[b], math.sqrt(speed[a] ** 2 + 2 * BRAKE_PROFILE * self.step))
        return speed

    def at(self, s: float) -> tuple[float, float, float, float, float, float, float]:
        """Position & track info at distance: x, y, z, heading x, heading z, curvature, target speed"""
        pos = s / self.step
        i = int(pos) % self.count
        j = (i + 1) % self.count
        f = pos - int(pos)
        return (
            self.xs[i] + (self.xs[j] - self.xs[i]) * f,
            self.ys[i] + (self.ys[j] - self.ys[i]) * f,
            self.zs[i] + (self.zs[j] - self.zs[i]) * f,
            self.hx[i],
            self.hz[i],
            self.curv[i],
            self.speed[i],
        )


class Car:
    """Simulated vehicle"""

    def __init__(self, index: int, grid_entry: tuple, pace: float):
        driver, team, model, klass, number = grid_entry
        self.index = index
        self.driver = driver
        self.team = f"{team} #{number}"
        self.model = model
        self.klass = klass
        self.hyper = klass == "Hypercar"
        self.number = number
        self.base_pace = pace
        self.qualification = index + 1
        self.gears = 7 if self.hyper else 6
        self.gear_step = 13.2 if self.hyper else 12.8
        self.rpm_max = 8200.0 if self.hyper else 7600.0
        self.tank = 90.0 if self.hyper else 100.0
        self.fuel_rate = 0.042 if self.hyper else 0.036
        self.ve_rate = 0.00055
        self.accel = 7.0 if self.hyper else 5.5
        self.decel = 24.0 if self.hyper else 19.0
        self.hybrid = self.hyper and index % 2 == 0
        self.reset(0.0)

    def reset(self, start_distance: float):
        """Place car in mid-race state"""
        self.pace = self.base_pace
        self.lap_factor = 1.0
        self.laps = 0
        self.s = 0.0
        self.v = 0.0
        self.a = 0.0
        self.lat_accel = 0.0
        self.throttle = 0.0
        self.brake = 0.0
        self.steer = 0.0
        self.gear = 0
        self.rpm = 1500.0
        self.torque = 0.0
        self.lap_start = 0.0
        self.cur_s1 = 0.0
        self.cur_s2 = 0.0
        self.last_s2 = 0.0
        self.sector = 0
        self.last_lap = 0.0
        self.best_lap = 0.0
        self.finish = 0
        self.slow_left = 0.0
        self.pit = 0
        self.pit_timer = 0.0
        self.pit_stops = 0
        self.pit_start_ve = 0.0
        self.pit_start_fuel = 0.0
        self.pit_lap = -99
        self.lateral = random.uniform(-1.5, 1.5)
        self.line_offset = self.lateral
        self.fuel = random.uniform(0.35, 0.95) * self.tank
        self.ve = random.uniform(0.2, 0.9) if self.hyper else 0.0
        self.compound = 1
        self.wear = [random.uniform(0.6, 0.95)] * 4
        self.tyre_temp = [78.0, 78.0, 80.0, 80.0]
        self.carcass = [74.0, 74.0, 76.0, 76.0]
        self.load = [4000.0, 4000.0, 4500.0, 4500.0]
        self.pit_total = 1.0
        self.brake_temp = [320.0, 320.0, 280.0, 280.0]
        self.brake_wear = [0.0275 - random.uniform(0, 0.004)] * 4
        self.water = 88.0
        self.oil = 104.0
        self.battery = random.uniform(0.3, 0.8)
        self.motor_state = 1 if self.hybrid else 0
        self.regen = 0.0
        self.x = self.y = self.z = 0.0
        self.hx = 0.0
        self.hz = 1.0
        self.curv = 0.0
        self.place = 0
        self.incidents = 0
        self.penalties = 0
        self.integrity = 1.0
        self.start_distance = start_distance

    def place_on_track(self, sim: MockSession):
        """Set initial distance & lap timing"""
        track = sim.track
        self.laps = int(self.start_distance // track.length)
        self.s = self.start_distance % track.length
        ref = track.base_laptime / self.base_pace
        self.v = track.at(self.s)[6] * self.base_pace
        self.last_lap = ref * random.uniform(1.0, 1.006)
        self.best_lap = self.last_lap * random.uniform(0.992, 0.999)
        self.last_s2 = self.last_lap * SECTOR2_END
        self.lap_start = sim.et - self.s / track.length * ref
        self.sector = self._sector_index(track)
        if self.sector > 0:
            self.cur_s1 = ref * SECTOR1_END
        if self.sector > 1:
            self.cur_s2 = ref * SECTOR2_END

    def _sector_index(self, track: Track) -> int:
        frac = self.s / track.length
        return 0 if frac < SECTOR1_END else 1 if frac < SECTOR2_END else 2

    def wants_pit(self, sim: MockSession) -> bool:
        if sim.et > sim.end_et - 240 or self.finish or self.laps - self.pit_lap < 2:
            return False
        low_energy = self.ve < 0.09 if self.hyper else self.fuel < 7.0
        return low_energy or min(self.wear) < 0.4

    def step(self, sim: MockSession, dt: float):
        """Advance simulation"""
        track = sim.track
        length = track.length
        x, y, z, hx, hz, k, v_prof = track.at(self.s)
        target = v_prof * self.pace * self.lap_factor
        if self.slow_left > 0:
            self.slow_left -= dt
            target = min(target, 16.0)

        # Pit stop state machine
        if self.pit == 0 and self.wants_pit(sim):
            self.pit = 1
        if self.pit == 1 and self.s > length - PIT_ENTRY:
            self.pit = 2
        if self.pit == 2:
            remain = PIT_BOX - self.s if self.s < length / 2 else length - self.s + PIT_BOX
            target = min(target, PIT_SPEED, math.sqrt(max(0.0, 2 * 6.0 * (remain - 1.0))) + 1.0)
            if remain <= 1.5 and self.v < 3.0:
                self._start_stop(sim)
        elif self.pit == 4:
            target = min(target, PIT_SPEED)
            if length / 2 > self.s > PIT_EXIT:
                self.pit = 0

        if self.pit == 3:
            self._pit_service(sim, dt)
            target = 0.0
            self.v = 0.0

        # Longitudinal dynamics
        acc = max(self.accel - 0.045 * self.v, 1.0)
        dv = _clamp(target - self.v, -self.decel * dt, acc * dt)
        self.a = dv / dt
        self.v = max(self.v + dv, 0.0)
        self.s += self.v * dt

        if self.s >= length:
            self.s -= length
            self._cross_line(sim)
        self._update_sector(sim, track)

        # Inputs
        if self.pit == 3:
            self.throttle = self.brake = 0.0
        elif self.a > 0.3:
            self.throttle = min(1.0, 0.45 + self.a / acc * 0.55)
            self.brake = 0.0
        elif self.a < -1.5:
            self.throttle = 0.0
            self.brake = min(1.0, -self.a / self.decel * 1.1)
        else:
            self.throttle = _clamp(0.2 + 0.5 * self.v / SPEED_MAX, 0.0, 0.8) if self.v > 1 else 0.0
            self.brake = 0.0

        # Geometry
        self.curv = k
        self.lat_accel = self.v * self.v * k
        self.steer = _clamp(k * 38.0 + random.uniform(-0.004, 0.004), -1.0, 1.0) if self.v > 1 else 0.0
        lateral_target = PIT_LANE_OFFSET if self.pit in (2, 3, 4) else self.line_offset
        self.lateral += _clamp(lateral_target - self.lateral, -4.0 * dt, 4.0 * dt)
        self.x = x - hz * self.lateral
        self.z = z + hx * self.lateral
        self.y = y
        self.hx, self.hz = hx, hz

        self._powertrain(dt)
        self._thermal(sim, dt)
        self._consume(dt)

    def _start_stop(self, sim: MockSession):
        self.pit = 3
        self.v = 0.0
        self.pit_start_ve = self.ve
        self.pit_start_fuel = self.fuel
        refill = (1.0 - self.ve) / 0.035 if self.hyper else (self.tank - self.fuel) / 3.3
        self.pit_timer = min(max(refill, 12.0), 45.0) + 2.0
        self.pit_total = self.pit_timer

    def _pit_service(self, sim: MockSession, dt: float):
        self.pit_timer -= dt
        done = 1.0 - max(self.pit_timer, 0.0) / self.pit_total
        self.ve = self.pit_start_ve + (1.0 - self.pit_start_ve) * done if self.hyper else 0.0
        self.fuel = self.pit_start_fuel + (self.tank - self.pit_start_fuel) * done
        if self.pit_timer <= 0:
            self.wear = [1.0] * 4
            self.compound = 3 if sim.rain > 0.12 else 1
            self.tyre_temp = [62.0] * 4
            self.carcass = [55.0] * 4
            self.pit_stops += 1
            self.pit_lap = self.laps
            self.pit = 4

    def _cross_line(self, sim: MockSession):
        self.laps += 1
        laptime = sim.et - self.lap_start
        self.last_lap = laptime
        if self.best_lap <= 0 or laptime < self.best_lap:
            self.best_lap = laptime
        self.last_s2 = self.cur_s2
        self.lap_start = sim.et
        self.cur_s1 = self.cur_s2 = 0.0
        self.sector = 0
        self.lap_factor = _clamp(random.gauss(1.0, 0.004), 0.985, 1.01)
        if sim.et > sim.end_et and not self.finish:
            self.finish = 1

    def _update_sector(self, sim: MockSession, track: Track):
        sector = self._sector_index(track)
        if sector == self.sector:
            return
        elapsed = sim.et - self.lap_start
        if sector == 1:
            self.cur_s1 = elapsed
        elif sector == 2:
            self.cur_s2 = elapsed
        self.sector = sector

    def _powertrain(self, dt: float):
        v = self.v
        if v < 0.5 and self.pit != 3:
            self.gear = 1
        elif self.pit == 3 or v < 0.5:
            self.gear = 0
        else:
            self.gear = int(_clamp(int(v / self.gear_step) + 1, 1, self.gears))
        if self.gear == 0:
            self.rpm = 1500.0
        else:
            frac = _clamp((v - (self.gear - 1) * self.gear_step) / self.gear_step, 0.0, 1.0)
            self.rpm = 4700.0 + (self.rpm_max - 4700.0) * frac - 300.0 * (1.0 - self.throttle)
        self.torque = self.throttle * (620.0 if self.hyper else 560.0) * (0.85 + 0.15 * (self.rpm / self.rpm_max))
        if self.hybrid:
            if self.brake > 0.2 and v > 20:
                self.motor_state = 3
                self.regen = 110.0 * self.brake
                self.battery = min(self.battery + 0.004 * dt * self.brake * 10, 0.95)
            elif self.throttle > 0.9 and v > 50 and self.battery > 0.08:
                self.motor_state = 2
                self.regen = 0.0
                self.battery = max(self.battery - 0.003 * dt * 10, 0.05)
            else:
                self.motor_state = 1
                self.regen = 0.0

    def _thermal(self, sim: MockSession, dt: float):
        v = self.v
        ay = self.lat_accel
        lat = min(1.0, abs(ay) / 18.0)
        df = 1.0 * v * v if self.hyper else 0.55 * v * v
        relax = min(dt / 12.0, 1.0)
        carc_relax = min(dt / 40.0, 1.0)
        wear_base = 0.8e-4 * dt
        wet_factor = 1.0 - 0.25 * sim.rain
        for w in range(4):
            side = -1.0 if w % 2 == 0 else 1.0
            front = w < 2
            outer = side * ay > 0
            load = max((3700.0 if front else 4300.0) + 0.22 * df * 0.5 + side * ay * 110.0, 200.0)
            target = (
                52.0 + 0.005 * load + 14.0 * lat * (1.0 if outer else 0.4)
                + (6.0 * self.brake if front else 4.0 * self.throttle)
            ) * wet_factor + sim.track_temp * 0.15
            self.tyre_temp[w] += (target - self.tyre_temp[w]) * relax
            self.carcass[w] += (self.tyre_temp[w] - 4.0 - self.carcass[w]) * carc_relax
            self.wear[w] = max(
                self.wear[w] - wear_base * (
                    1.0 + 1.6 * lat * (1.0 if outer else 0.5)
                    + (0.5 * self.throttle if not front else 0.5 * self.brake)
                ),
                0.0,
            )
            self.load[w] = load
            # Brakes
            force = self.brake * (1.0 if front else 0.7)
            if self.brake > 0.05:
                self.brake_temp[w] += (300.0 + 650.0 * force - self.brake_temp[w]) * min(dt / 2.0, 1.0)
            else:
                self.brake_temp[w] += (220.0 - self.brake_temp[w]) * min(dt / 7.0, 1.0)
            self.brake_wear[w] = max(self.brake_wear[w] - dt * force * 5e-6, 0.012)
        self.water += ((82.0 + 8.0 * self.throttle + (10.0 if v < 10 else 0.0)) - self.water) * min(dt / 15.0, 1.0)
        self.oil += ((self.water + 18.0) - self.oil) * min(dt / 25.0, 1.0)

    def _consume(self, dt: float):
        if self.pit == 3:
            return
        self.fuel = max(self.fuel - self.fuel_rate * self.throttle * dt, 0.0)
        if self.hyper:
            self.ve = max(self.ve - self.ve_rate * self.throttle * dt, 0.0)


class MockSession:
    """Mock race session, advanced on demand by wall clock"""

    def __init__(self):
        self.track = Track()
        self.lock = threading.Lock()
        self.cars: list[Car] = []
        self.player = PLAYER_INDEX
        self.end_et = END_ET
        self.resets = 0
        self._last = time.monotonic()
        self._next_event = 0.0
        self.build()

    def build(self):
        """Create cars"""
        self.cars = []
        hyper_rank = gt_rank = 0
        for index, entry in enumerate(GRID):
            if entry[3] == "Hypercar":
                pace = 1.0 - 0.0045 * hyper_rank
                hyper_rank += 1
            else:
                pace = 0.89 - 0.004 * gt_rank
                gt_rank += 1
            self.cars.append(Car(index, entry, pace))
        self.restart()

    def restart(self):
        """Restart session from initial mid-race state"""
        self.et = START_ET
        self.rain = 0.0
        self.wetness = 0.0
        self.track_temp = 34.0
        self.ambient_temp = 24.0
        self.cloud = 1
        self.t0 = START_ET
        self._next_event = self.et + 150.0
        track = self.track
        avg_speed = track.length / track.base_laptime
        for car in self.cars:
            car.reset(0.0)
            car.start_distance = max(
                START_ET * avg_speed * car.base_pace - car.index * random.uniform(35.0, 80.0), 0.0
            )
            car.place_on_track(self)
        player = self.cars[self.player]
        player.ve = 0.17  # player pits within a few laps
        self._rank()

    def start(self):
        """Reset time reference (API start)"""
        with self.lock:
            self._last = time.monotonic()

    def update(self):
        """Advance simulation to current time"""
        now = time.monotonic()
        if now - self._last < UPDATE_INTERVAL:
            return
        if not self.lock.acquire(blocking=False):
            return
        try:
            dt = min(now - self._last, 5.0)
            self._last = now
            while dt > 1e-6:
                step = min(dt, MAX_STEP)
                self._step(step)
                dt -= step
        finally:
            self.lock.release()

    def _step(self, dt: float):
        self.et += dt
        self._weather(dt)
        if self.et >= self._next_event:
            self._next_event = self.et + random.uniform(240.0, 420.0)
            candidates = [c for c in self.cars if c.index != self.player and c.pit == 0 and c.slow_left <= 0]
            if candidates:
                random.choice(candidates).slow_left = random.uniform(20.0, 35.0)
        for car in self.cars:
            car.step(self, dt)
        self._rank()
        if self.et > self.end_et + 150.0:
            self.resets += 1
            self.restart()

    def _rank(self):
        length = self.track.length
        ordered = sorted(self.cars, key=lambda c: c.laps * length + c.s, reverse=True)
        for place, car in enumerate(ordered, start=1):
            car.place = place

    def weather_at(self, seconds: float) -> tuple[float, int]:
        """Rain (fraction), base cloud coverage at session time"""
        phase = ((seconds - self.t0) / 60.0) % 30.0
        if phase < 4:
            return 0.0, 1
        if phase < 7:
            return 0.18 * (phase - 4) / 3, 3
        if phase < 14:
            return 0.18, 4
        if phase < 18:
            return 0.18 * (18 - phase) / 4, 3
        return 0.0, 2

    def _weather(self, dt: float):
        self.rain, self.cloud = self.weather_at(self.et)
        if self.rain > 0:
            self.wetness = min(self.wetness + dt / 150.0 * min(self.rain * 6, 1.0), 1.0)
        else:
            self.wetness = max(self.wetness - dt / 240.0, 0.0)
        self.track_temp = 34.0 - 8.0 * self.wetness - (2.0 if self.cloud >= 3 else 0.0)
        self.ambient_temp = 24.0 - 3.0 * min(self.rain * 5, 1.0)

    def blue_flag(self, car: Car) -> bool:
        """Slower class car with faster class car approaching from behind"""
        if car.hyper or car.pit:
            return False
        length = self.track.length
        for other in self.cars:
            if other.hyper and not other.pit:
                gap = (car.s - other.s) % length
                if 0 < gap < 120:
                    return True
        return False

    def yellow_flag(self) -> bool:
        return any(c.slow_left > 0 and c.pit == 0 for c in self.cars)
