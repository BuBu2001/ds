"""Наследия и Алтарь Наследия (ТЗ п.6.3).

При окончательной смерти игрок выбирает ОДНО наследие; оно не меняется до
следующей окончательной смерти.
"""
import random
from ..data import loader


LEGACY_DEFS = {
    "legacy_rune": {
        "name": "Руна предков",
        "desc": "1 случайная руна с меча становится стартовой.",
    },
    "legacy_shards": {
        "name": "Осколочный дар",
        "desc": "10% накопленных Осколков переносятся.",
    },
    "legacy_perk": {
        "name": "Урок прошлого",
        "desc": "1 случайный перк становится стартовым.",
    },
    "legacy_coal": {
        "name": "Жар Бездны",
        "desc": "+5% к дропу углей навсегда (стакается до +25%).",
        "stackable": True, "per_stack": 0.05, "cap": 0.25,
    },
}


class LegacyAltar:
    """Алтарь Наследия: выбор после окончательной смерти."""

    def __init__(self, rng=random):
        self.rng = rng
        self.current = None            # выбранный id наследия
        self.coal_stacks = 0           # стаки «Жара Бездны»

    def offer(self, last_run_shards=0, unlocked_runes=None, unlocked_perks=None):
        """Возвращает список доступных наследий для выбора (4 варианта по ТЗ)."""
        offers = []
        if unlocked_runes:
            offers.append({"id": "legacy_rune",
                           "payload": self.rng.choice(list(unlocked_runes))})
        else:
            offers.append({"id": "legacy_rune", "payload": None})
        offers.append({"id": "legacy_shards", "payload": int(last_run_shards * 0.10)})
        if unlocked_perks:
            offers.append({"id": "legacy_perk",
                           "payload": self.rng.choice(list(unlocked_perks))})
        else:
            offers.append({"id": "legacy_perk", "payload": None})
        offers.append({"id": "legacy_coal", "payload": self.coal_stacks})
        return offers

    def choose(self, legacy_id, meta_state):
        """Применяет выбранное наследие к мета-состоянию (SaveData)."""
        if legacy_id not in LEGACY_DEFS:
            return False
        self.current = legacy_id
        if legacy_id == "legacy_coal":
            self.coal_stacks = min(5, self.coal_stacks + 1)   # кап +25%
            meta_state.legacy_coal_stacks = self.coal_stacks
        elif legacy_id == "legacy_rune":
            meta_state.start_rune = self.rng.choice(
                list(loader.runes().keys())) if not getattr(
                    meta_state, "start_rune", None) else meta_state.start_rune
        elif legacy_id == "legacy_perk":
            perks = list(loader.perks().keys())
            meta_state.start_perk = self.rng.choice(perks)
        elif legacy_id == "legacy_shards":
            pass  # payload начисляет world при старте забега
        return True

    def coal_bonus(self):
        return self.coal_stacks * LEGACY_DEFS["legacy_coal"]["per_stack"]

    def to_dict(self):
        return {"current": self.current, "coal_stacks": self.coal_stacks}

    @classmethod
    def from_dict(cls, d, rng=random):
        a = cls(rng=rng)
        a.current = d.get("current")
        a.coal_stacks = d.get("coal_stacks", 0)
        return a
