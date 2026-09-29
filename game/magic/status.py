"""Состояния врагов и их обработка (ТЗ п.8.1): Горение, Хрупкость, Заморозка."""


class StatusEffect:
    def __init__(self, kind, duration, stacks=1):
        self.kind = kind          # 'burn' | 'brittle' | 'frozen' | 'armor_break' | 'accuracy_down' | 'slow'
        self.duration = duration
        self.stacks = stacks

    def update(self, dt):
        self.duration -= dt
        return self.duration > 0


class StatusContainer:
    """Набор статусов на одном существе + тики урона от горения."""

    def __init__(self):
        self.effects = {}         # kind -> StatusEffect

    def has(self, kind):
        e = self.effects.get(kind)
        return e is not None and e.duration > 0

    def get(self, kind):
        return self.effects.get(kind)

    def apply(self, kind, duration, stacks=1, max_stacks=1):
        if kind in self.effects:
            e = self.effects[kind]
            if kind == "burn":
                e.stacks = min(max_stacks, e.stacks + stacks)
                e.duration = max(e.duration, duration)
            elif kind == "brittle":
                e.duration = min(6.0, e.duration + duration)   # по ТЗ — стаки длительности
            else:
                e.duration = max(e.duration, duration)
                e.stacks = max(e.stacks, stacks)
        else:
            self.effects[kind] = StatusEffect(kind, duration, stacks)

    def remove(self, kind):
        self.effects.pop(kind, None)

    def update(self, dt, entity, world=None):
        """Тики: DPS от горения. Возвращает суммарный DoT-урон за кадр."""
        dot_damage = 0.0
        for kind in list(self.effects):
            e = self.effects[kind]
            if not e.update(dt):
                self.effects.pop(kind)
                if kind == "frozen" and world:
                    world.on_thaw(entity)
        if self.has("burn"):
            from ..core.constants import BURN_DPS_PCT
            e = self.effects["burn"]
            dot_damage = entity.max_hp * BURN_DPS_PCT * e.stacks * dt
        return dot_damage

    # --- производные модификаторы ---
    @property
    def slow_pct(self):
        s = 0.0
        if self.has("brittle"):
            from ..core.constants import BRITTLE_SLOW
            s += BRITTLE_SLOW
        if self.has("slow"):
            s += self.effects["slow"].stacks * 0.30
        return min(s, 0.9)

    @property
    def frozen(self):
        return self.has("frozen")

    @property
    def crit_vulnerability(self):
        from ..core.constants import BRITTLE_CRIT_VULN
        return BRITTLE_CRIT_VULN if self.has("brittle") else 0.0

    @property
    def accuracy_debuff(self):
        return 0.5 if self.has("accuracy_down") else 0.0

    @property
    def armor_break_pct(self):
        e = self.effects.get("armor_break")
        return e.stacks if e else 0.0
