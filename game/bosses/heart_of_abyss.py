"""Истинный босс NG+2+ 20 ур. — Сердце Бездны (ТЗ п.13.5, 19.7–19.8).

Фаза 1: копирует атаки игрока (меч/огонь/лёд/пар) в случайном порядке.
Фаза 2: призывает 3 Отражения; одно истинное (1 HP, 200% урона), найти за 10 сек,
        иначе все три взрываются.
Фаза 3: гравитация каждые 5 сек; арена сужается (лава поднимается от краёв).

Лут: Сердце Бездны (мета-трофей) → секретная концовка / выбор финала (п.19.8).
"""
from enum import Enum
import random
from .base_boss import BaseBoss, BossPhase, BossStateMachine
from ..entities.base import Entity
from ..core.math_utils import Vector2


class HeartState(Enum):
    IDLE = 1
    MIMIC = 2          # фаза 1: копирование атак
    HUNT = 3           # фаза 2: поиск истинного отражения
    COLLAPSE = 4       # фаза 3: сужение арены
    DEAD = 5


MIMIC_ATTACKS = ["sword", "fire", "ice", "steam"]
REFLECTION_TIMEOUT = 10.0
PHASE3_GRAVITY_PERIOD = 5.0


class TrueReflection(Entity):
    """Отражение из фазы 2: 1 HP, 200% урона. Игрок должен найти настоящее."""

    def __init__(self, pos, is_true=False, damage_reflect=0.0):
        super().__init__(pos, hp=1 if is_true else 60, radius=0.6)
        self.kind = "true_reflection" if is_true else "fake_reflection"
        self.display_name = "Отражение"
        self.is_true = is_true
        self.damage = 20 * 2.0 if is_true else 20
        self.speed = 4.0
        self._cd = 0.0

    def update(self, dt, world):
        if not self.alive:
            return
        player = world.player
        if player:
            world.move_entity(self, player.pos, dt, speed=self.speed)
            self._cd -= dt
            if self.distance_to(player) < 1.5 and self._cd <= 0:
                world.deal_damage_to_player(self.damage, source=self, kind="reflection")
                self._cd = 1.5


class HeartOfAbyss(BaseBoss):
    BOSS_ID = "heart_of_abyss"
    LEVEL = 20
    NAME = "Сердце Бездны"
    HP = 4000
    DAMAGE = 30
    SPEED = 3.0
    TROPHY = "heart_of_abyss_item"   # мета-трофей, открывает секретную концовку
    SOULS = 0                        # не даёт душ — это финал

    def __init__(self, pos, arena_box=None, **kw):
        super().__init__(pos, **kw)
        self.arena_box = arena_box or (0, 0, 100, 100)   # (x0,y0,x1,y1)
        self.lava_margin = 0          # насколько лава поднялась от краёв (клетки)
        self.gravity_timer = PHASE3_GRAVITY_PERIOD
        self.last_player_attacks = []  # стек последних атак игрока для мимики
        self.reflections = []
        self.hunt_timer = 0.0
        self.sm = HeartStateMachine(self, HeartState.IDLE)

    # ---------- мимика (фаза 1) ----------
    def note_player_attack(self, attack_kind):
        self.last_player_attacks.append(attack_kind)
        if len(self.last_player_attacks) > 8:
            self.last_player_attacks.pop(0)

    def pick_mimic_attack(self, rng=random):
        if self.last_player_attacks:
            return rng.choice(self.last_player_attacks[-4:])
        return rng.choice(MIMIC_ATTACKS)

    def perform_mimic(self, world):
        player = world.player
        if not player:
            return
        kind = self.pick_mimic_attack(world.rng)
        if kind == "sword":
            if self.distance_to(player) < 2.5:
                world.deal_damage_to_player(self.damage, source=self, kind="sword")
        elif kind == "fire":
            world.enemy_cast_fire(self, player, self.damage)
        elif kind == "ice":
            world.enemy_cast_ice(self, player, self.damage)
        elif kind == "steam":
            world.enemy_cast_steam(self, player, self.damage * 0.6)
        world.spawn_float_text(self.pos, f"Мимикрия: {kind}")

    # ---------- фаза 2: Отражения ----------
    def summon_reflections(self, world):
        true_i = world.rng.randint(0, 2)
        self.reflections = []
        for i in range(3):
            ang = world.rng.uniform(0, 6.28)
            off = Vector2.from_angle(ang, 4.0)
            r = TrueReflection(self.pos + off, is_true=(i == true_i))
            self.reflections.append(r)
            world.spawn_object(r)
        self.hunt_timer = REFLECTION_TIMEOUT

    def reflections_explode(self, world):
        """Время вышло — все три взрываются по игроку."""
        player = world.player
        for r in self.reflections:
            if r.alive:
                r.alive = False
                if player:
                    d = r.distance_to(player)
                    if d < 5:
                        world.deal_damage_to_player(25 * (1 - d / 5), source=r,
                                                    kind="explosion")
        world.spawn_float_text(self.pos, "Отражения взорвались!")

    # ---------- фаза 3: сужение арены ----------
    def raise_lava(self, world):
        self.lava_margin += 1
        world.set_lava_margin(self.lava_margin)

    def on_phase(self, new_phase):
        super().on_phase(new_phase)
        if new_phase == BossPhase.P2:
            self.sm.change(HeartState.HUNT)
        elif new_phase == BossPhase.P3:
            self.sm.change(HeartState.COLLAPSE)

    def ending_choices(self):
        """После победы — выбор концовки (п.19.8)."""
        return ["burn_heart", "absorb_heart"]


class HeartStateMachine(BossStateMachine):
    DEAD = HeartState.DEAD

    def check_transitions(self, ctx):
        b, world, dt = self.boss, ctx["world"], ctx["dt"]
        st = self.state
        player = world.player

        if st == HeartState.IDLE:
            self.change(HeartState.MIMIC)
            self.set_timer("mimic_cd", 2.0)

        elif st == HeartState.MIMIC:
            if player:
                world.move_entity(b, player.pos, dt, speed=b.speed)
            if self.timer_ready("mimic_cd"):
                b.perform_mimic(world)
                self.set_timer("mimic_cd", 2.0)

        elif st == HeartState.HUNT:
            if not b.reflections:
                b.summon_reflections(world)
            b.hunt_timer -= dt
            alive_true = [r for r in b.reflections if r.alive and r.is_true]
            if not alive_true:
                # игрок нашёл истинное отражение — продолжаем мимику
                b.reflections = []
                self.change(HeartState.MIMIC)
            elif b.hunt_timer <= 0:
                b.reflections_explode(world)
                b.reflections = []
                self.change(HeartState.MIMIC)

        elif st == HeartState.COLLAPSE:
            # гравитация каждые 5 сек + лава съедает арену
            b.gravity_timer -= dt
            if b.gravity_timer <= 0:
                b.gravity_timer = PHASE3_GRAVITY_PERIOD
                world.force_gravity_flip()
            if self.timer_ready("lava_step"):
                b.raise_lava(world)
                self.set_timer("lava_step", 3.0)
            if player:
                world.move_entity(b, player.pos, dt, speed=b.speed)
                if self.timer_ready("mimic_cd"):
                    b.perform_mimic(world)
                    self.set_timer("mimic_cd", 1.5)

        if not b.alive:
            self.change(HeartState.DEAD)
