"""Босс 15 ур. — Искажённый маг (ТЗ п.13.4).

- Меняет гравитацию каждые 20 сек (все подпрыгивают, снаряды по дуге).
- Уязвим только когда кастует (прекаст 2 сек — светящийся шар).
- Прервать каст (урон > 10% HP) → босс падает, 5 сек уязвимости.
- Призывает 3 копии; одна настоящая. Убийство копии лечит настоящего на 10%.

Стейт-машина: IDLE, AGRO, CAST, VULNERABLE, SUMMON_CLONES, DEAD.
"""
from enum import Enum
from .base_boss import BaseBoss, BossPhase, BossStateMachine
from ..core.math_utils import Vector2


class TwistedMageState(Enum):
    IDLE = 1
    AGRO = 2
    CAST = 3
    VULNERABLE = 4
    SUMMON_CLONES = 5
    DEAD = 6


GRAVITY_PERIOD = 20.0
CAST_DURATION = 2.0
VULNERABLE_AFTER_INTERRUPT = 5.0
CLONE_HEAL_PCT = 0.10


class TwistedClone(BaseBoss):
    """Копия Искажённого мага. Одна из них — настоящая (is_true_clone)."""

    BOSS_ID = "twisted_clone"
    LEVEL = 15
    NAME = "Искажённая копия"
    HP = 150
    DAMAGE = 12
    SPEED = 4.0

    def __init__(self, pos, is_true=False, master=None, **kw):
        super().__init__(pos, **kw)
        self.is_boss = False          # копия считается обычным врагом для капстоунов
        self.is_true_clone = is_true
        self.master = master
        self.sm = None                # простая AI-логика в update

    def update(self, dt, world):
        if not self.alive:
            return
        self.update_status(dt, world)
        if not self.alive:
            self.on_death(world)
            return
        player = world.player
        if player:
            world.move_entity(self, player.pos, dt, speed=self.speed)
            if self.distance_to(player) < 2.0 and getattr(self, "_cd", 0) <= 0:
                world.deal_damage_to_player(self.damage, source=self, kind="melee")
                self._cd = 2.0
            self._cd = getattr(self, "_cd", 0) - dt

    def on_death(self, world):
        if self.master and self.master.alive and not self.is_true_clone:
            # убийство НЕ настоящей копии лечит оригинала на 10%
            self.master.heal(self.master.max_hp * CLONE_HEAL_PCT)
            world.spawn_float_text(self.master.pos, "Оригинал исцелён!")
        elif self.master:
            self.master.clones.remove(self)


class TwistedMage(BaseBoss):
    BOSS_ID = "twisted_mage"
    LEVEL = 15
    NAME = "Искажённый маг"
    HP = 1500
    DAMAGE = 25
    SPEED = 3.5
    TROPHY = "abyss_key_3"           # третий Ключ Бездны + трофей NG+2
    SOULS = 3

    def __init__(self, pos, mech_points=None, **kw):
        super().__init__(pos, **kw)
        self.gravity_timer = GRAVITY_PERIOD
        self.cast_damage_accum = 0.0
        self.clones = []
        self.true_index = 0
        self.sm = TwistedMageStateMachine(self, TwistedMageState.IDLE)

    @property
    def is_casting(self):
        return self.sm.state == TwistedMageState.CAST

    def damage_multiplier(self, damage_type):
        # уязвим только во время каста или после прерывания
        if self.sm.state in (TwistedMageState.CAST, TwistedMageState.VULNERABLE):
            return 1.0
        return 0.15   # почти неуязвим вне каста

    def take_damage(self, amount, damage_type="physical"):
        dealt = super().take_damage(amount, damage_type)
        if self.is_casting and dealt > 0:
            self.cast_damage_accum += dealt / max(1e-6, self.max_hp)
            if self.cast_damage_accum > 0.10:
                # прерывание: босс падает, 5 сек уязвимости
                self.cast_damage_accum = 0.0
                self.sm.change(TwistedMageState.VULNERABLE)
                self.sm.set_timer("vuln", VULNERABLE_AFTER_INTERRUPT)
                self.sm.cancel_cast()
        return dealt

    def flip_gravity(self, world):
        """Глобальная смена гравитации: все подпрыгивают, снаряды по дуге."""
        world.force_gravity_flip()
        world.spawn_float_text(self.pos, "Гравитация искажена!")

    def summon_clones(self, world):
        true_i = world.rng.randint(0, 2)
        for i in range(3):
            offset = Vector2((i - 1) * 3.0, 2.0)
            c = TwistedClone(self.pos + offset, is_true=(i == true_i),
                             master=self, ng_hp_mult=self.max_hp / self.HP,
                             ng_dmg_mult=self.damage / self.DAMAGE)
            self.clones.append(c)
            world.spawn_object(c)
        self.true_index = true_i


class TwistedMageStateMachine(BossStateMachine):
    DEAD = TwistedMageState.DEAD

    def cancel_cast(self):
        self.boss.cast_damage_accum = 0.0

    def check_transitions(self, ctx):
        b, world, dt = self.boss, ctx["world"], ctx["dt"]
        st = self.state
        player = world.player
        dist = b.distance_to(player) if player else 999

        # таймер гравитации — сквозной (каждые 20 сек)
        b.gravity_timer -= dt
        if b.gravity_timer <= 0:
            b.gravity_timer = GRAVITY_PERIOD
            b.flip_gravity(world)

        if st == TwistedMageState.IDLE:
            if dist < 15:
                self.change(TwistedMageState.AGRO)

        elif st == TwistedMageState.AGRO:
            world.move_entity(b, player.pos, dt, speed=b.speed)
            if self.timer_ready("cast_cd"):
                self.change(TwistedMageState.CAST)
                self.set_timer("cast", CAST_DURATION)
                b.cast_damage_accum = 0.0
            # при 50%/25% HP — призвание копий
            if b.phase >= BossPhase.P2 and not getattr(b, "_cloned_p2", False):
                b._cloned_p2 = True
                self.change(TwistedMageState.SUMMON_CLONES)
                self.set_timer("summon", 1.5)

        elif st == TwistedMageState.CAST:
            # прекаст: светящийся шар; завершение → выстрел искривлённым снарядом
            if self.timer_ready("cast"):
                world.spawn_twisted_bolt(b, player)
                self.set_timer("cast_cd", 4.0)
                self.change(TwistedMageState.AGRO)

        elif st == TwistedMageState.VULNERABLE:
            if self.timer_ready("vuln"):
                self.set_timer("cast_cd", 1.0)
                self.change(TwistedMageState.AGRO)

        elif st == TwistedMageState.SUMMON_CLONES:
            if self.timer_ready("summon"):
                b.summon_clones(world)
                self.change(TwistedMageState.AGRO)

        if not b.alive:
            for c in b.clones:
                if c.alive:
                    c.alive = False   # копии гибнут вместе с оригиналом
            self.change(TwistedMageState.DEAD)
