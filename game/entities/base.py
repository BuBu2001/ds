"""Базовые сущности: Entity, моб-обёртка над AI, снаряды, лужи, облака пара, ловушки."""
import math
import random
from ..core.math_utils import Vector2
from ..core import constants as C
from ..magic.status import StatusContainer


class Entity:
    """Всё, что имеет позицию и HP: игрок, мобы, маги, боссы, тотемы, фонари."""

    def __init__(self, pos, hp=1, radius=0.5):
        self.pos = pos if isinstance(pos, Vector2) else Vector2(*pos)
        self.hp = hp
        try:                        # у подклассов max_hp может быть свойством (Player)
            self.max_hp = hp
        except AttributeError:
            pass
        self.radius = radius
        self.alive = True
        self.status = StatusContainer()
        self.is_boss = False
        self.is_player = False
        self.speed = 3.0
        self.damage = 5
        self.kind = "entity"
        self.summoned_by = None

    def take_damage(self, amount, damage_type="physical"):
        """damage_type принимает и игнорирует (боссы переопределяют со своим расчётом)."""
        if not self.alive:
            return 0
        # разлом брони = враг получает больше урона
        dmg = amount * (1 + self.status.armor_break_pct)
        self.hp -= dmg
        if self.hp <= 0:
            self.hp = 0
            self.alive = False
        return dmg

    def heal(self, amount):
        self.hp = min(self.max_hp, self.hp + amount)

    def distance_to(self, other):
        return self.pos.distance_to(other.pos)

    def update_status(self, dt, world=None):
        dot = self.status.update(dt, self, world)
        if dot > 0:
            self.hp -= dot
            if self.hp <= 0:
                self.hp = 0
                self.alive = False
        return dot


class Projectile:
    """Снаряд: файербол (дуга), ледяной шип (прямо+снос), луч (игнор гравитации)."""

    def __init__(self, pos, velocity, damage, kind="fire", source="player",
                 aoe_radius=0.0, ignore_gravity=False, always_straight=False,
                 lifetime=4.0, effect=None):
        self.pos = pos.copy()
        self.velocity = velocity.copy()
        self.damage = damage
        self.kind = kind               # fire | ice | spike | beam | arrow
        self.source = source           # 'player' | 'enemy'
        self.aoe_radius = aoe_radius
        self.ignore_gravity = ignore_gravity
        self.always_straight = always_straight
        self.lifetime = lifetime
        self.effect = effect or {}     # {"burn":..}|{"freeze":..}|{"slow":..}
        self.dead = False

    def update(self, dt, anomaly, world):
        from ..magic.anomalies import AnomalyManager
        AnomalyManager.update_projectile(self, dt, anomaly)
        self.lifetime -= dt
        if self.lifetime <= 0:
            self.dead = True
            return
        gx, gy = int(self.pos.x), int(self.pos.y)
        if world.is_wall(gx, gy):
            self.dead = True
            world.on_projectile_impact(self)


class IcePuddle:
    """Ледяная лужа мага (п.12.2): радиус 2м, 10 сек, инверсия управления."""

    def __init__(self, pos, duration=C.PUDDLE_DURATION, radius=C.PUDDLE_RADIUS):
        self.pos = pos.copy() if isinstance(pos, Vector2) else Vector2(*pos)
        self.duration = duration
        self.radius = radius

    def update(self, dt):
        self.duration -= dt
        return self.duration > 0

    def contains(self, pos):
        return math.hypot(pos.x - self.pos.x, pos.y - self.pos.y) <= self.radius


def on_player_enter_puddle(player, puddle):
    """Ровно по псевдокоду ТЗ п.12.2 — стакинг-инверсия не суммируется."""
    if player.control_inverted_timer > 0:
        player.control_inverted_timer = 0.5
    else:
        player.control_inverted_timer = 0.5
    player.brittle_duration = min(6.0, player.brittle_duration + 3.0)
    player.status.apply("brittle", 3.0)


class SteamCloud:
    """Облако пара (п.8.2): АОЕ-урон один раз, -50% точности врагов на 4 сек."""

    def __init__(self, pos, radius, damage, duration=C.STEAM_DURATION):
        self.pos = pos.copy() if isinstance(pos, Vector2) else Vector2(*pos)
        self.radius = radius
        self.damage = damage
        self.duration = duration
        self.applied = set()   # id врагов, получивших урон (не стакается)

    def update(self, dt):
        self.duration -= dt
        return self.duration > 0


class SpikeTrap:
    """Ловушка-шипы (6+ ур.): урон при входе, откат."""

    def __init__(self, pos, damage=15, cooldown=2.0):
        self.pos = pos.copy() if isinstance(pos, Vector2) else Vector2(*pos)
        self.damage = damage
        self.cooldown = cooldown
        self.timer = 0.0

    def try_trigger(self, entity_pos):
        if self.timer > 0:
            return False
        if math.hypot(entity_pos.x - self.pos.x, entity_pos.y - self.pos.y) < 0.7:
            self.timer = self.cooldown
            return True
        return False

    def update(self, dt):
        self.timer = max(0.0, self.timer - dt)
