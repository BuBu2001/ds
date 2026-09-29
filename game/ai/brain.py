"""AI Layer: тонкие обёртки над стейт-машинами сущностей (ТЗ п.11, 12).

Сами стейт-машины живут в entities/*; здесь — точка входа слоя и
хелперы выбора поведения, чтобы World не знал деталей AI.
"""
from ..entities.mobs import Mob
from ..entities.mages import Mage


class MobBrain:
    """Управляет обычным мобом/элиткой через его StateMachine (30→60 FPS LOD)."""

    def __init__(self, mob: Mob):
        self.mob = mob
        self.is_elite = getattr(mob, "is_elite", False)

    def update(self, dt, world):
        m = self.mob
        if not m.alive:
            return
        # «Тишина» (модификатор п.19.5 #8): мобы атакуют быстрее, маги молчат
        if "silence" in getattr(world, "modifiers", set()) and not self.is_elite:
            dt *= 1.3
        m.update(dt, world)

    @property
    def state(self):
        return self.mob.sm.state.name if hasattr(self.mob, "sm") else "?"


class MageBrain:
    """Маг-враг (п.12): касты, прерывания, баффы союзников. LOD 30 FPS."""

    def __init__(self, mage: Mage):
        self.mage = mage

    def update(self, dt, world):
        mg = self.mage
        if not mg.alive:
            return
        if "silence" in getattr(world, "modifiers", set()):
            # Тишина: маги не кастуют (но мобы ускоряются — учтено в MobBrain)
            if hasattr(mg, "hold_cast"):
                mg.hold_cast()
            return
        mg.update(dt, world)

    @property
    def state(self):
        return self.mage.sm.state.name if hasattr(self.mage, "sm") else "?"
