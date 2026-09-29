"""Руны (ТЗ п.9): временные/постоянные, стаки «Заточки», снятие за осколки, трофеи."""
import random
from ..data import loader
from ..core import constants as C


class RuneSystem:
    """Хранилище рун меча игрока + правила наложения/снятия."""

    def __init__(self, wallet, rng=random):
        self.wallet = wallet
        self.rng = rng
        self.defs = loader.runes()
        self.slots = []            # [{"id", "stacks", "enchanted"}] — активные руны
        self.max_slots = C.RUNE_SLOTS_BASE
        self.trophies = set()      # id предметов-триггеров для постоянных рун

    def unlock_slot(self):
        if self.max_slots < 3:
            self.max_slots += 1
            return True
        return False

    def can_apply(self, rune_id):
        rd = self.defs.get(rune_id)
        if not rd:
            return False, "Нет такой руны"
        existing = self._find(rune_id)
        if existing and rd.get("max_stacks"):
            if existing["stacks"] >= rd["max_stacks"]:
                return False, f"{rd['name']}: максимум {rd['max_stacks']} стака"
            return True, ""
        if existing:
            return False, "Руна уже на мече"
        if len(self.slots) >= self.max_slots:
            return False, "Нет свободных слотов"
        if rd["permanent"]:
            if self.wallet.shards < rd["cost_shards"]:
                return False, "Мало осколков"
            if rd.get("trophy") and rd["trophy"] not in self.trophies:
                return False, f"Нужен предмет: {rd['trophy']}"
        return True, ""

    def apply(self, rune_id, enchanted=False):
        ok, msg = self.can_apply(rune_id)
        if not ok:
            return False, msg
        rd = self.defs[rune_id]
        existing = self._find(rune_id)
        if existing and rd.get("max_stacks"):
            existing["stacks"] += 1
            return True, f"{rd['name']}: стак {existing['stacks']}"
        if rd["permanent"]:
            self.wallet.spend_shards(rd["cost_shards"])
        self.slots.append({"id": rune_id, "stacks": 1, "enchanted": enchanted})
        return True, f"{rd['name']} наложена"

    def remove(self, rune_id):
        """Снятие любой руны: 5 Осколков (п.9). Постоянную можно заменить за 10."""
        r = self._find(rune_id)
        if not r:
            return False, "Руна не наложена"
        if self.wallet.spend_shards(C and loader.load("runes")["removal_cost_shards"]):
            self.slots.remove(r)
            return True, f"Руна снята"
        return False, "Мало осколков (нужно 5)"

    def replace_permanent(self, old_id, new_id):
        """Замена постоянной руны: 10 осколков."""
        ok, msg = self.can_apply(new_id)
        if not ok:
            return False, msg
        if self.wallet.spend_shards(loader.load("runes")["permanent_replace_cost_shards"]):
            self.remove_free(old_id)
            return self.apply(new_id)
        return False, "Мало осколков (нужно 10)"

    def remove_free(self, rune_id):
        r = self._find(rune_id)
        if r:
            self.slots.remove(r)

    def _find(self, rune_id):
        for r in self.slots:
            if r["id"] == rune_id:
                return r
        return None

    def active(self):
        out = []
        for r in self.slots:
            d = dict(self.defs[r["id"]])
            d["stacks"] = r["stacks"]
            d["enchanted"] = r["enchanted"]
            out.append(d)
        return out

    def add_trophy(self, item_id):
        self.trophies.add(item_id)

    # --- временные руны слетают при смерти и отдыхе (п.9.1) ---
    def clear_temporary(self):
        removed = [r["id"] for r in self.slots
                   if not self.defs[r["id"]]["permanent"]]
        self.slots = [r for r in self.slots if self.defs[r["id"]]["permanent"]]
        return removed

    def has_enchanted(self, rune_id):
        """Зачарованная версия заменяет обычную — не стакается (п.9)."""
        for r in self.slots:
            if r["id"] == rune_id and r.get("enchanted"):
                return True
        return False

    # --- эффекты на урон при ударе ---
    def on_attack(self, player, target, world):
        for r in self.active():
            eff = r.get("effects", {})
            if eff.get("lifesteal"):
                heal = player.damage() * eff["lifesteal"]
                player.hp = min(player.max_hp, player.hp + heal)
            if eff.get("instant_kill_chance") and not getattr(target, "is_boss", False):
                if self.rng.random() < eff["instant_kill_chance"]:
                    target.take_damage(target.hp)
                    world.spawn_float_text(target.pos, "ПУСТОТА!")
