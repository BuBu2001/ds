"""Босс 5 ур. — Гоблин-шаман (ТЗ п.13.2).

Механика: 3 тотема по углам арены; пока хоть один активен — босс неуязвим и
кастует молнии. После уничтожения всех — 10 сек уязвимости, затем возрождение.
На 50% HP: призыв 2 миньонов; не убить за 8 сек → шаман лечится на 20%.

Стейт-машина: IDLE, CAST_SHIELD, AGRO, SUMMON, VULNERABLE, DEAD.
"""
from enum import Enum
from .base_boss import BaseBoss, BossPhase, Totem, BossStateMachine
from ..core.math_utils import Vector2


class ShamanState(Enum):
    IDLE = 1
    CAST_SHIELD = 2
    AGRO = 3
    SUMMON = 4
    VULNERABLE = 5
    DEAD = 6


VULNERABLE_WINDOW = 10.0     # сек уязвимости после смерти всех тотемов
MINION_HEAL_TIMEOUT = 8.0    # сек, чтобы убить миньонов


class GoblinShaman(BaseBoss):
    BOSS_ID = "goblin_shaman"
    LEVEL = 5
    NAME = "Гоблин-шаман"
    HP = 400
    DAMAGE = 15
    SPEED = 3.0
    TROPHY = "shaman_eye"          # «Око Шамана» — материал Руны Маны
    SOULS = 1

    def __init__(self, pos, mech_points, **kw):
        super().__init__(pos, **kw)
        self.mech_points = mech_points[:3]      # 3 точки под тотемы
        self.totems = []
        self.lightning_cd = 0.0
        self.minion_timer = 0.0
        self.summoned_minions_once = False
        self.sm = ShamanStateMachine(self, ShamanState.IDLE)

    def spawn_totems(self, world):
        for p in self.mech_points:
            t = Totem(Vector2(*p), hp=100 * (self.max_hp / self.HP))
            self.totems.append(t)
            world.spawn_object(t)

    @property
    def active_totems(self):
        return [t for t in self.totems if t.alive]

    @property
    def is_invulnerable(self):
        return bool(self.active_totems) and self.sm.state != ShamanState.VULNERABLE

    def damage_multiplier(self, damage_type):
        return 0.0 if self.is_invulnerable else 1.0

    def take_damage(self, amount, damage_type="physical"):
        dealt = super().take_damage(amount, damage_type)
        # прерывание каста щита накопленным уроном > 10% max HP
        if dealt > 0 and self.sm.state == ShamanState.CAST_SHIELD:
            self.sm.shield_damage += dealt
            if self.sm.shield_damage > self.max_hp * 0.10:
                self.sm.change(ShamanState.AGRO)
        return dealt

    def lightning_strike(self, world):
        """Пока тотемы живы — кастует молнии по игроку."""
        player = world.player
        if player and self.distance_to(player) < 15:
            world.deal_damage_to_player(self.damage * 0.8, source=self, kind="lightning")
            world.spawn_float_text(player.pos, "Молния!")

    def on_totem_death(self, world):
        if not self.active_totems and self.sm.state in (
                ShamanState.AGRO, ShamanState.CAST_SHIELD, ShamanState.IDLE):
            self.sm.change(ShamanState.VULNERABLE)
            self.sm.set_timer("vuln", VULNERABLE_WINDOW)
            self.vulnerable = True

    def revive_totems(self, world):
        for t in self.totems:
            if not t.alive:
                t.hp = t.max_hp
                t.alive = True
        self.vulnerable = False


class ShamanStateMachine(BossStateMachine):
    DEAD = ShamanState.DEAD

    def __init__(self, boss, initial):
        super().__init__(boss, initial)
        self.boss = boss
        self.shield_damage = 0.0

    def on_enter(self, state):
        self.shield_damage = 0.0
        if state == ShamanState.VULNERABLE:
            self.boss.vulnerable = True
        elif state in (ShamanState.AGRO, ShamanState.CAST_SHIELD):
            self.boss.vulnerable = False

    def check_transitions(self, ctx):
        b, world, dt = self.boss, ctx["world"], ctx["dt"]
        st = self.state
        player = world.player
        dist = b.distance_to(player) if player else 999

        if st == ShamanState.IDLE:
            self.change(ShamanState.CAST_SHIELD)
            self.set_timer("shield_cast", 2.0)

        elif st == ShamanState.CAST_SHIELD:
            if self.timer_ready("shield_cast"):
                if not b.active_totems:
                    self.change(ShamanState.VULNERABLE)
                    self.set_timer("vuln", VULNERABLE_WINDOW)
                else:
                    self.change(ShamanState.AGRO)
                    self.set_timer("lightning", 1.5)

        elif st == ShamanState.AGRO:
            # движение к игроку, атака вблизи, молнии пока тотемы живы
            world.move_entity(b, player.pos, dt, speed=b.speed)
            if dist < 2.5 and self.timer_ready("melee"):
                world.deal_damage_to_player(b.damage, source=b, kind="melee")
                self.set_timer("melee", 2.0)
            if b.active_totems and self.timer_ready("lightning"):
                b.lightning_strike(world)
                self.set_timer("lightning", 1.5)
            if not b.active_totems:
                self.change(ShamanState.VULNERABLE)
                self.set_timer("vuln", VULNERABLE_WINDOW)
            # фаза 2: на 50% HP — призыв 2 миньонов (один раз)
            if (b.phase >= BossPhase.P2 and not b.summoned_minions_once
                    and b.active_totems):
                b.summoned_minions_once = True
                self.change(ShamanState.SUMMON)
                self.set_timer("summon_cast", 1.5)
                b.minion_timer = MINION_HEAL_TIMEOUT

        elif st == ShamanState.SUMMON:
            if self.timer_ready("summon_cast") and not b.summons:
                world.summon_minions(b, count=2, mob_id="goblin")
            b.minion_timer -= dt
            alive_minions = [s for s in b.summons if s.alive]
            if b.minion_timer <= 0:
                if alive_minions:
                    b.heal(b.max_hp * 0.20)
                    world.spawn_float_text(b.pos, "Шаман исцелился!")
                else:
                    b.heal(b.max_hp * 0.0)
                self.change(ShamanState.AGRO)

        elif st == ShamanState.VULNERABLE:
            world.move_entity(b, player.pos, dt, speed=b.speed * 0.7)
            if self.timer_ready("vuln"):
                b.revive_totems(world)
                self.change(ShamanState.CAST_SHIELD)
                self.set_timer("shield_cast", 2.0)

        if not b.alive:
            self.change(ShamanState.DEAD)
