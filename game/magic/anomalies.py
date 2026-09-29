"""Гравитационные аномалии (ТЗ п.15): глобальные события и локальные зоны.

Влияние на снаряды — update_projectile; влияние на игрока — модификаторы прыжка/рывка/стамины.
"""
import math
import random
from ..core import constants as C
from ..core.math_utils import Vector2


class AnomalyType:
    OVERLOAD = "overload"      # +100%
    WEIGHTLESS = "weightless"  # -80%
    INVERSION = "inversion"    # вверх
    SIDEWAYS = "sideways"      # север/юг/запад/восток
    NONE = "none"


SIDE_VECTORS = {
    "north": Vector2(0, -1), "south": Vector2(0, 1),
    "west": Vector2(-1, 0), "east": Vector2(1, 0),
}


class GravityAnomaly:
    def __init__(self, kind, direction=None, pos=None, radius=0.0, permanent=False):
        self.kind = kind
        self.direction = direction or random.choice(list(SIDE_VECTORS))
        self.pos = pos                  # для локальных зон (клетки)
        self.radius = radius            # 4–6 м для локальных
        self.permanent = permanent
        self.duration = 0.0

    @property
    def multiplier(self):
        return {AnomalyType.OVERLOAD: 2.0, AnomalyType.WEIGHTLESS: 0.2,
                AnomalyType.INVERSION: -1.0}.get(self.kind, 1.0)

    def side_vector(self):
        return SIDE_VECTORS.get(self.direction, Vector2(0, 0))

    def contains(self, pos):
        if self.pos is None:
            return True   # глобальная
        return math.hypot(pos[0] - self.pos[0], pos[1] - self.pos[1]) <= self.radius


class AnomalyManager:
    """Глобальное событие каждые 30 сек (или 15 с «Гравитационным хаосом») + локальные зоны."""

    GLOBAL_KINDS = [AnomalyType.OVERLOAD, AnomalyType.WEIGHTLESS,
                    AnomalyType.INVERSION, AnomalyType.SIDEWAYS]

    def __init__(self, level, modifiers=(), rng=random):
        self.enabled = level >= 11
        self.modifiers = modifiers
        self.rng = rng
        self.period = 15.0 if "grav_chaos" in modifiers else C.ANOMALY_GLOBAL_PERIOD
        self.timer = self.period
        self.global_anomaly = None
        self.local_zones = []

    def add_local_zone(self, pos, radius=None):
        kind = self.rng.choice(self.GLOBAL_KINDS)
        zone = GravityAnomaly(kind, pos=pos,
                              radius=radius or self.rng.randint(*C.ANOMALY_LOCAL_RADIUS),
                              permanent=True)
        self.local_zones.append(zone)
        return zone

    def anomaly_at(self, pos):
        """Действующая аномалия в точке: локальная приоритетнее глобальной."""
        for z in self.local_zones:
            if z.contains(pos):
                return z
        if self.global_anomaly:
            return self.global_anomaly
        return GravityAnomaly(AnomalyType.NONE)

    def update(self, dt):
        if not self.enabled:
            return
        self.timer -= dt
        if self.timer <= 0:
            self.timer = self.period
            kind = self.rng.choice(self.GLOBAL_KINDS)
            self.global_anomaly = GravityAnomaly(kind)
            self.global_anomaly.duration = C.ANOMALY_GLOBAL_DURATION
        elif self.global_anomaly:
            self.global_anomaly.duration -= dt
            if self.global_anomaly.duration <= 0:
                self.global_anomaly = None

    # ---------- влияние на снаряды (п.15.2) ----------
    @staticmethod
    def update_projectile(proj, dt, anomaly):
        g = C.BASE_GRAVITY * anomaly.multiplier
        if proj.ignore_gravity:            # магические лучи
            proj.pos = proj.pos + proj.velocity * dt
            return
        if proj.always_straight:           # ледяной шип: прямо, но сносит боком
            if anomaly.kind == AnomalyType.SIDEWAYS:
                sv = anomaly.side_vector()
                proj.velocity = proj.velocity + sv * g * dt * 0.5
            proj.pos = proj.pos + proj.velocity * dt
            return
        if anomaly.kind == AnomalyType.INVERSION:
            proj.velocity = proj.velocity + Vector2(0, -g * dt * 0.5)
        elif anomaly.kind == AnomalyType.SIDEWAYS:
            sv = anomaly.side_vector()
            proj.velocity = proj.velocity + Vector2(sv.x * g * dt * 0.5,
                                                    sv.y * g * dt * 0.5)
        else:
            proj.velocity = proj.velocity + Vector2(0, g * dt * 0.35)
        proj.pos = proj.pos + proj.velocity * dt

    # ---------- влияние на игрока (п.15.3) ----------
    def player_mods(self, pos):
        a = self.anomaly_at(pos)
        mods = {"jump_mult": 1.0, "dodge_mult": 1.0, "stamina_cost_mult": 1.0,
                "drift": Vector2(0, 0)}
        if a.kind == AnomalyType.OVERLOAD:
            mods["jump_mult"] = 0.5
            mods["dodge_mult"] = 0.7
            mods["stamina_cost_mult"] = 1.2
        elif a.kind == AnomalyType.WEIGHTLESS:
            mods["jump_mult"] = 3.0
            mods["dodge_mult"] = 1.5
            mods["stamina_cost_mult"] = 0.7
        elif a.kind == AnomalyType.INVERSION:
            mods["drift"] = Vector2(0, -2.0)
            mods["stamina_cost_mult"] = 1.5 if mods["drift"].y < 0 else 1.0
        elif a.kind == AnomalyType.SIDEWAYS:
            mods["drift"] = a.side_vector() * 2.0
            mods["stamina_cost_mult"] = 1.1
        return mods
