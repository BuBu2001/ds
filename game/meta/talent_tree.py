"""Древо Талантов (ТЗ п.6.2): 3 ветки по 10 узлов, цена 1,1,2,2,3,3,5,5,8,13 душ.

Ветки: «Плоть» (выживание), «Дух» (магия), «Сталь» (боевка). Узел 10 — капстоун.
Открыть можно только последовательно (узел N требует N-1). Трата — Души Боссов.
"""
from ..core import constants as C

# Каждый узел: (name, effects dict | special key)
TALENT_TREE = {
    "flesh": {
        "name": "Плоть",
        "nodes": [
            ("+10 HP", {"max_hp_flat": 10}),
            ("+10 HP", {"max_hp_flat": 10}),
            ("+5% сопротивление огню", {"fire_resist": 0.05}),
            ("+5% сопротивление льду", {"ice_resist": 0.05}),
            ("+1 заряд отдыха у костра", {"rest_charge": 1}),
            ("+15 HP", {"max_hp_flat": 15}),
            ("+10% макс. HP", {"max_hp": 0.10}),
            ("Реген 1 HP/сек вне боя", {"special": "regen_ooc"}),
            ("+1 использование отдыха", {"rest_charge": 1}),
            ("Капстоун: при смерти один раз за забег восстанавливаешь 30% HP",
             {"special": "flesh_deathsave"}),
        ],
    },
    "spirit": {
        "name": "Дух",
        "nodes": [
            ("+10 маны", {"max_mana_flat": 10}),
            ("+10 маны", {"max_mana_flat": 10}),
            ("+5% урон огнём", {"fire_damage": 0.05}),
            ("+5% урон льдом", {"ice_damage": 0.05}),
            ("+1 реген маны", {"mana_regen": 1}),
            ("+15 маны", {"max_mana_flat": 15}),
            ("+10% макс. маны", {"max_mana": 0.10}),
            ("Стоимость каста -10%", {"special": "cast_cost_minus"}),
            ("Горение стакается до 4 раз", {"burn_extra_stacks": 1}),
            ("Капстоун: Пар наносит +25% урона и оглушает на 0.5 сек",
             {"special": "steam_capstone", "steam_damage": 0.25}),
        ],
    },
    "steel": {
        "name": "Сталь",
        "nodes": [
            ("+5% урон мечом", {"melee_damage": 0.05}),
            ("+5% урон мечом", {"melee_damage": 0.05}),
            ("+5% скорость атаки", {"attack_speed": 0.05}),
            ("+10 стамины", {"max_stamina_flat": 10}),
            ("+1 реген стамины", {"stamina_regen": 1}),
            ("+10% урон тяжёлой атакой", {"heavy_damage": 0.10}),
            ("+15% крит-урон", {"crit_damage": 0.15}),
            ("Рывок стоит -20% стамины", {"dodge_cost_reduction": 0.20}),
            ("Комбо по замороженному +50% урона", {"combo_bonus": 0.50}),
            ("Капстоун: тяжёлая атака 20% шанс мгновенно убить не-босса с HP<20%",
             {"special": "steel_execution"}),
        ],
    },
}


class TalentTree:
    def __init__(self, souls=0):
        self.souls = souls                     # текущий запас Душ Боссов
        self.progress = {branch: 0 for branch in TALENT_TREE}   # кол-во открытых узлов

    # ---------- цены ----------
    @staticmethod
    def node_price(index):
        return C.TALENT_PRICES[index]

    def next_price(self, branch):
        done = self.progress[branch]
        if done >= len(TALENT_TREE[branch]["nodes"]):
            return None
        return self.node_price(done)

    def can_unlock(self, branch):
        price = self.next_price(branch)
        return price is not None and self.souls >= price

    def unlock_next(self, branch):
        """Открывает следующий узел ветки; возвращает dict эффекта или None."""
        if not self.can_unlock(branch):
            return None
        idx = self.progress[branch]
        price = self.node_price(idx)
        self.souls -= price
        self.progress[branch] = idx + 1
        name, eff = TALENT_TREE[branch]["nodes"][idx]
        return {"branch": branch, "index": idx, "name": name, **eff}

    # ---------- агрегированные эффекты ----------
    def aggregate_effects(self):
        """Суммарные модификаторы по всем открытым узлам."""
        total = {}
        specials = []
        rest_charges = 0
        for branch, count in self.progress.items():
            for i in range(count):
                _name, eff = TALENT_TREE[branch]["nodes"][i]
                for k, v in eff.items():
                    if k == "special":
                        specials.append(v)
                    elif k == "rest_charge":
                        rest_charges += v
                    else:
                        total[k] = total.get(k, 0.0) + v
        total["rest_charge_bonus"] = rest_charges
        return total, specials

    def has_special(self, key):
        _, specials = self.aggregate_effects()
        return key in specials

    # ---------- сериализация ----------
    def to_dict(self):
        return {"souls": self.souls, "progress": dict(self.progress)}

    @classmethod
    def from_dict(cls, d):
        t = cls(souls=d.get("souls", 0))
        t.progress.update(d.get("progress", {}))
        return t
