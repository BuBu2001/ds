"""Базовый босс (ТЗ п.13): общие правила — фазы, механика уязвимости, дроп.

Дроп: 50–100 углей, 1–2 осколка, трофей (первое убийство), 3–5 материалов тира,
+ Души Боссов при первом убийстве (п.3.1), Золотые слитки при повторных.
Стейт-машины наследуют StateMachine и переопределяют check_transitions.
"""
from enum import Enum
from ..core.state_machine import StateMachine
from ..entities.base import Entity


class BossPhase(Enum):
    P1 = 1
    P2 = 2
    P3 = 3


class BaseBoss(Entity):
    BOSS_ID = "base"
    LEVEL = 5
    NAME = "Босс"
    HP = 500
    DAMAGE = 20
    SPEED = 3.0
    TROPHY = None            # id трофея (первое убийство)
    SOULS = 0                # души за первое убийство

    def __init__(self, pos, ng_hp_mult=1.0, ng_dmg_mult=1.0, threat_stacks=0,
                 first_kill=True, rng=None):
        super().__init__(pos, hp=self.HP * ng_hp_mult, radius=1.0)
        self.is_boss = True
        self.kind = f"boss_{self.BOSS_ID}"
        self.display_name = self.NAME
        self.boss_id = self.BOSS_ID
        self.level_gate = self.LEVEL
        self.damage = self.DAMAGE * ng_dmg_mult * (1 + 0.1 * threat_stacks)
        self.speed = self.SPEED
        self.phase = BossPhase.P1
        self.first_kill = first_kill
        self.summons = []
        self.vulnerable = False
        self.enrage_timer = 0.0

    # ---------- общий каркас ----------
    def update(self, dt, world):
        self.world_ref = world
        if not self.alive:
            if self.sm.state != self.DEAD_STATE:
                self.die(world)
            return
        self.update_status(dt, world)
        if not self.alive:
            self.die(world)
            return
        for s in list(self.summons):
            if not s.alive:
                self.summons.remove(s)
        self.sm.update(dt, {"dt": dt, "world": world})
        self.check_phase_transition()

    def check_phase_transition(self):
        ratio = self.hp / max(1e-6, self.max_hp)
        if ratio <= 0.5 and self.phase == BossPhase.P1:
            self.on_phase(BossPhase.P2)
        elif ratio <= 0.25 and self.phase == BossPhase.P2:
            self.on_phase(BossPhase.P3)

    def on_phase(self, new_phase):
        self.phase = new_phase

    def die(self, world):
        if self.sm.state != self.DEAD_STATE:
            self.sm.change(self.DEAD_STATE)
        world.on_boss_death(self)

    @property
    def DEAD_STATE(self):
        return getattr(self.sm, "DEAD", None)

    # урон по боссам не проходит «мгновенно» (правило капстоуни Стали)
    def can_be_instantly_executed(self):
        return False

    def take_damage(self, amount, damage_type="physical"):
        """Возвращает фактический нанесённый урон с учётом множителей типа."""
        mult = self.damage_multiplier(damage_type)
        if mult <= 0:
            return 0
        return super().take_damage(amount * mult)

    def damage_multiplier(self, damage_type):
        return 1.0


class Totem(Entity):
    """Тотем шамана: 100 HP, пока активен — босс неуязвим."""

    def __init__(self, pos, hp=100):
        super().__init__(pos, hp=hp, radius=0.5)
        self.kind = "totem"
        self.display_name = "Тотем"

    def can_be_instantly_executed(self):
        return False


class Lantern(Entity):
    """Фонарь Костяного лорда на цепи: 200 HP, снимается дальним боем/мечом в прыжке."""

    def __init__(self, pos, hp=200):
        super().__init__(pos, hp=hp, radius=0.5)
        self.kind = "lantern"
        self.display_name = "Фонарь"

    def can_be_instantly_executed(self):
        return False


class BossStateMachine(StateMachine):
    """Общая база стейт-машин боссов: таймеры уязвимости/призыва."""

    def __init__(self, boss, initial):
        super().__init__(initial)
        self.boss = boss
