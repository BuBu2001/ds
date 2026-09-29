"""Босс 10 ур. — Костяной лорд (ТЗ п.13.3).

Иммунен к огню, уязвим к льду; фонари на цепях (200 HP) дают таблицу
множителей урона. Каждый снятый фонарь: -25% защиты. После снятия обоих —
15 сек уязвимости, затем фонари загораются вновь + призыв скелетов.

Стейт-машина ровно по ТЗ: IDLE→CAST_SHIELD (player_dist<12, таймер 2.0),
CAST_SHIELD→VULNERABLE (0 фонарей, 15.0) / AGRO (summon_timer 10.0),
AGRO: атака dist<2.5 (20 урона, кд 2.0); SUMMON: 1.5с → 2 скелета → AGRO (кд 15.0);
VULNERABLE: 15с, скорость -50%, полный урон; dist>15 → сброс в CAST_SHIELD.
"""
from enum import Enum
from .base_boss import BaseBoss, Lantern, BossStateMachine
from ..core.math_utils import Vector2


class BoneLordState(Enum):
    IDLE = 1
    CAST_SHIELD = 2
    AGRO = 3
    SUMMON = 4
    VULNERABLE = 5
    DEAD = 6


# Таблица уязвимости по живым фонарям (п.13.3): {fire, ice, physical}
LANTERN_DAMAGE_TABLE = {
    2: {"fire": 0.0, "ice": 0.5, "physical": 0.25},
    1: {"fire": 0.25, "ice": 0.75, "physical": 0.50},
    0: {"fire": 1.0, "ice": 1.0, "physical": 1.0},
}

VULNERABLE_DURATION = 15.0
ATTACK_RANGE = 2.5
ATTACK_COOLDOWN = 2.0
ATTACK_DAMAGE = 20
RESET_DISTANCE = 15.0


class BoneLord(BaseBoss):
    BOSS_ID = "bone_lord"
    LEVEL = 10
    NAME = "Костяной лорд"
    HP = 900
    DAMAGE = ATTACK_DAMAGE
    SPEED = 3.5
    TROPHY = "bone_skull"          # «Череп Костяного лорда» — материал Руны Жизни
    SOULS = 2

    def __init__(self, pos, mech_points, **kw):
        super().__init__(pos, **kw)
        self.mech_points = mech_points[:2]     # 2 точки под фонари
        self.lanterns = []
        self.summon_timer = 10.0
        self.sm = BoneLordStateMachine(self, BoneLordState.IDLE)

    def spawn_lanterns(self, world):
        for p in self.mech_points:
            l = Lantern(Vector2(*p), hp=200 * (self.max_hp / self.HP))
            self.lanterns.append(l)
            world.spawn_object(l)

    @property
    def live_lanterns(self):
        return sum(1 for l in self.lanterns if l.alive)

    def damage_multiplier(self, damage_type):
        table = LANTERN_DAMAGE_TABLE.get(self.live_lanterns, LANTERN_DAMAGE_TABLE[0])
        base = table.get(damage_type, 1.0)
        # защита босса: каждый живой фонарь +25% (т.е. -25% за снятый уже в таблице)
        if self.sm.state == BoneLordState.VULNERABLE:
            return 1.0
        return base

    def relight_lanterns(self):
        for l in self.lanterns:
            if not l.alive:
                l.hp = l.max_hp
                l.alive = True

    def on_lantern_death(self, world):
        if self.live_lanterns == 0 and self.sm.state in (
                BoneLordState.AGRO, BoneLordState.CAST_SHIELD):
            self.sm.change(BoneLordState.VULNERABLE)
            self.sm.set_timer("vuln", VULNERABLE_DURATION)


class BoneLordStateMachine(BossStateMachine):
    DEAD = BoneLordState.DEAD

    def check_transitions(self, ctx):
        b, world, dt = self.boss, ctx["world"], ctx["dt"]
        st = self.state
        player = world.player
        dist = b.distance_to(player) if player else 999

        if st == BoneLordState.IDLE:
            if dist < 12:
                self.change(BoneLordState.CAST_SHIELD)
                self.set_timer("shield", 2.0)

        elif st == BoneLordState.CAST_SHIELD:
            if self.timer_ready("shield"):
                if b.live_lanterns == 0:
                    self.change(BoneLordState.VULNERABLE)
                    self.set_timer("vuln", VULNERABLE_DURATION)
                else:
                    b.summon_timer = 10.0
                    self.change(BoneLordState.AGRO)

        elif st == BoneLordState.AGRO:
            world.move_entity(b, player.pos, dt, speed=b.speed)
            if dist < ATTACK_RANGE and self.timer_ready("melee"):
                world.deal_damage_to_player(ATTACK_DAMAGE, source=b, kind="melee")
                self.set_timer("melee", ATTACK_COOLDOWN)
            b.summon_timer -= dt
            if b.summon_timer <= 0 and b.live_lanterns == 2:
                self.change(BoneLordState.SUMMON)
                self.set_timer("summon_cast", 1.5)
            if b.live_lanterns == 0:
                self.change(BoneLordState.VULNERABLE)
                self.set_timer("vuln", VULNERABLE_DURATION)

        elif st == BoneLordState.SUMMON:
            if self.timer_ready("summon_cast"):
                world.summon_minions(b, count=2, mob_id="skeleton")
                b.summon_timer = 15.0
                self.change(BoneLordState.AGRO)

        elif st == BoneLordState.VULNERABLE:
            # скорость -50%, полный урон (damage_multiplier вернёт 1.0)
            world.move_entity(b, player.pos, dt, speed=b.speed * 0.5)
            if dist > RESET_DISTANCE:
                # сброшен — фонари загораются, цикл щита заново
                b.relight_lanterns()
                self.change(BoneLordState.CAST_SHIELD)
                self.set_timer("shield", 2.0)
                return
            if self.timer_ready("vuln"):
                if b.alive:
                    b.relight_lanterns()
                    self.change(BoneLordState.CAST_SHIELD)
                    self.set_timer("shield", 2.0)

        if not b.alive:
            self.change(BoneLordState.DEAD)
