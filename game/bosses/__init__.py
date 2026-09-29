"""Boss Layer (ТЗ п.13): фабрика боссов по уровню и механикам."""
from .base_boss import BaseBoss, Totem, Lantern, BossPhase, BossStateMachine
from .shaman import GoblinShaman, ShamanState
from .bone_lord import BoneLord, BoneLordState, LANTERN_DAMAGE_TABLE
from .twisted_mage import TwistedMage, TwistedClone, TwistedMageState
from .heart_of_abyss import HeartOfAbyss, TrueReflection, HeartState

BOSS_BY_LEVEL = {5: GoblinShaman, 10: BoneLord, 15: TwistedMage, 20: HeartOfAbyss}


def boss_for_level(level, pos, mech_points=None, **kw):
    """Вернёт экземпляр босса для уровня; для 20 — Сердце Бездны."""
    cls = BOSS_BY_LEVEL.get(level)
    if cls is None:
        return None
    if cls is HeartOfAbyss:
        return cls(pos, **kw)
    return cls(pos, mech_points or [(pos.x - 4, pos.y - 4), (pos.x + 4, pos.y - 4),
                                    (pos.x - 4, pos.y + 4)], **kw)


__all__ = [
    "BaseBoss", "BossPhase", "BossStateMachine", "Totem", "Lantern",
    "GoblinShaman", "ShamanState",
    "BoneLord", "BoneLordState", "LANTERN_DAMAGE_TABLE",
    "TwistedMage", "TwistedClone", "TwistedMageState",
    "HeartOfAbyss", "TrueReflection", "HeartState",
    "BOSS_BY_LEVEL", "boss_for_level",
]
