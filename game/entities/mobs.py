"""Обычные мобы (ТЗ п.11): таблица по уровням + простые стейт-машины."""
import random
from enum import Enum
from ..core.state_machine import StateMachine
from .base import Entity
from ..core.math_utils import Vector2


class MobState(Enum):
    IDLE = 1
    CHASE = 2
    ATTACK = 3
    WINDUP = 4
    DEAD = 5


# name: hp, damage, speed(м/с), spawn_group, tiers
MOB_TABLE = {
    "goblin": {"name": "Гоблин", "hp": 30, "damage": 5, "speed": 3.0, "tiers": (1, 5)},
    "wolf":   {"name": "Волк", "hp": 25, "damage": 7, "speed": 5.0, "tiers": (1, 5)},
    "rat":    {"name": "Крыса", "hp": 15, "damage": 3, "speed": 4.0, "tiers": (1, 5), "group": (3, 5)},
    "skeleton": {"name": "Скелет", "hp": 50, "damage": 10, "speed": 3.0, "tiers": (6, 10)},
    "zombie": {"name": "Зомби", "hp": 80, "damage": 8, "speed": 1.5, "tiers": (6, 10)},
    "spider": {"name": "Паук", "hp": 40, "damage": 12, "speed": 6.0, "tiers": (6, 10), "jumper": True},
    "mutant": {"name": "Мутант", "hp": 100, "damage": 15, "speed": 4.0, "tiers": (11, 20), "explode": 20},
    "reflection": {"name": "Отражение", "hp": 80, "damage": 10, "speed": 4.0, "tiers": (11, 20), "copies_build": True},
    "eye":    {"name": "Глаз", "hp": 60, "damage": 10, "speed": 2.0, "tiers": (11, 20), "ranged": True},
}


def mobs_for_level(level, rng=random):
    """Какие мобы спавнятся на уровне."""
    pool = [k for k, v in MOB_TABLE.items() if v["tiers"][0] <= level <= v["tiers"][1]]
    return pool or ["rat"]


class Mob(Entity):
    def __init__(self, mob_id, pos, ng_hp_mult=1.0, ng_dmg_mult=1.0,
                 threat_stacks=0, is_elite=False, modifiers=()):
        data = MOB_TABLE[mob_id]
        hp = data["hp"] * ng_hp_mult * (2.0 if is_elite else 1.0)
        super().__init__(pos, hp=hp, radius=0.45)
        self.mob_id = mob_id
        self.kind = mob_id
        self.display_name = ("Элитный " if is_elite else "") + data["name"]
        base_dmg = data["damage"] * ng_dmg_mult * (1.5 if is_elite else 1.0)
        # угроза от отдыхов: мобы +10% силы за стак (п.5)
        self.damage = base_dmg * (1 + 0.10 * threat_stacks)
        self.speed = data["speed"] * (1.25 if is_elite else 1.0)
        self.is_elite = is_elite
        self.explode_damage = data.get("explode", 0)
        self.jumper = data.get("jumper", False)
        self.ranged = data.get("ranged", False)
        self.copies_build = data.get("copies_build", False)
        self.attack_range = 1.2 if not self.ranged else 8.0
        self.attack_cooldown = 1.0 / max(0.3, (1 + 0.3 * ("silence_mod" in modifiers)))
        self.cd_timer = 0.0
        self.windup = 0.0
        self.sm = MobStateMachine(self)

    @property
    def hp_ratio(self):
        return self.hp / max(1e-6, self.max_hp)

    def update(self, dt, world):
        if not self.alive:
            self.sm.change(MobState.DEAD)
            return
        self.update_status(dt, world)
        if not self.alive:
            world.on_enemy_death(self, by_burn=True)
            return
        if self.status.frozen:
            return  # полная остановка
        self.cd_timer = max(0.0, self.cd_timer - dt)
        ctx = {"dt": dt, "world": world}
        self.sm.update(dt, ctx)
        self._act(dt, world)

    def _act(self, dt, world):
        st = self.sm.state
        player = world.player
        to_p = player.pos - self.pos
        dist = to_p.length()
        speed = self.speed * (1 - self.status.slow_pct)
        if st == MobState.CHASE:
            if dist > 0.8:
                move = to_p.normalized() * speed * dt
                new = self.pos + move
                if not world.is_wall(int(new.x), int(new.y)):
                    self.pos = new
        elif st == MobState.WINDUP:
            self.windup -= dt
            if self.windup <= 0:
                if self.ranged:
                    world.spawn_enemy_projectile(self, "beam")
                else:
                    if dist <= self.attack_range + 0.3:
                        world.damage_player(self.damage)
                self.cd_timer = self.attack_cooldown
                self.sm.change(MobState.CHASE)
        elif st == MobState.ATTACK:
            if self.ranged and dist <= self.attack_range:
                self.sm.change(MobState.WINDUP)
                self.windup = 0.5
            elif dist <= self.attack_range:
                self.sm.change(MobState.WINDUP)
                self.windup = 0.4
            else:
                self.sm.change(MobState.CHASE)


class MobStateMachine(StateMachine):
    AGGRO_RADIUS = 10.0

    def __init__(self, mob):
        super().__init__(MobState.IDLE)
        self.mob = mob

    def check_transitions(self, ctx):
        world = ctx["world"]
        p = world.player
        if not p.alive:
            return
        dist = self.mob.distance_to(p)
        los = world.has_los(self.mob.pos.as_tuple(), p.pos.as_tuple())
        st = self.state
        if st == MobState.IDLE:
            if dist < self.AGGRO_RADIUS and los:
                self.change(MobState.CHASE)
        elif st == MobState.CHASE:
            if dist <= self.mob.attack_range and self.mob.cd_timer <= 0:
                self.change(MobState.ATTACK)
            elif dist > self.AGGRO_RADIUS * 1.5 or not los:
                self.change(MobState.IDLE)
        elif st == MobState.ATTACK:
            pass  #handled in _act
