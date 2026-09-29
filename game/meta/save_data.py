"""Meta Layer (ТЗ п.6, 10, 19): Мета-статы, сохранения, Главный Костёр, концевые экраны.

Сохраняется навсегда: мета-статы (п.6.1), Древо Талантов, наследие, трофеи,
золотые слитки, души боссов, открытые перки/руны, рекорды NG++.
Формат — JSON (п.21.1).
"""
import json
import os
from ..core import constants as C
from .talent_tree import TalentTree
from .legacies import LegacyAltar

SAVE_PATH = os.path.join(os.path.expanduser("~"), ".abyss_economy_save.json")

# Мета-статы п.6.1: цена в душах/слитках за шаг
META_STAT_DEFS = {
    "hp":        {"base": 100, "max": 200, "step": 20, "currency": "souls",  "cost": 1},
    "mana":      {"base": 100, "max": 200, "step": 20, "currency": "souls",  "cost": 1},
    "stamina":   {"base": 100, "max": 200, "step": 20, "currency": "souls",  "cost": 1},
    "inventory": {"base": 6,   "max": 12,  "step": 1,  "currency": "ingots", "cost": 1},
    "start_perks": {"base": 0, "max": 3,   "step": 1,  "currency": "souls",  "cost": 2},
    "start_runes": {"base": 0, "max": 3,   "step": 1,  "currency": "trophy", "cost": 1},
    "coal_drop": {"base": 0.0, "max": 0.25, "step": 0.05, "currency": "ingots", "cost": 1},
    "shard_drop": {"base": 0.0, "max": 0.15, "step": 0.05, "currency": "ingots", "cost": 1},
}


class MetaState:
    """Всё, что переживает окончательную смерть."""

    def __init__(self):
        # прокачанные значения мета-статов (абсолют)
        self.meta_stats = {k: v["base"] for k, v in META_STAT_DEFS.items()}
        self.souls_spend_pool = 0          # резерв; актуально в TalentTree.souls
        self.gold_ingots = 0
        self.trophies = set()              # id предметов боссов (первое убийство)
        self.bosses_first_kill = set()     # ('goblin_shaman', ng_cycle)
        self.bosses_souls_given = {}       # boss_id -> последний цикл, за который дана душа
        self.unlocked_perks = set()
        self.discovered_runes = set()      # руны, найденные на стенах (лор, 20 шт.)
        self.wall_rune_total = 0           # прогресс «Собирателя лора»
        self.talents = TalentTree()
        self.altar = LegacyAltar()
        self.legacy_coal_stacks = 0
        self.start_rune = None
        self.start_perk = None
        self.ng_cycle = 0                  # текущий цикл NG+
        self.ngpp_unlocked = False         # NG++ после «Поглотить Сердце»
        self.secret_ending_seen = False
        self.deepest_level = 0
        self.total_deaths = 0
        self.settings = DEFAULT_SETTINGS.copy()

    # ---------- доступ к мета-статам ----------
    def as_dict_for_player(self):
        """То, что читает PlayerStats.meta."""
        return {
            "hp": int(self.meta_stats["hp"]) - C.HP_BASE,
            "mana": int(self.meta_stats["mana"]) - C.MANA_BASE,
            "stamina": int(self.meta_stats["stamina"]) - C.STAMINA_BASE,
            "inventory": int(self.meta_stats["inventory"]),
        }

    @property
    def coal_drop_pct(self):
        return self.meta_stats["coal_drop"]

    @property
    def shard_drop_pct(self):
        return self.meta_stats["shard_drop"]

    def legacy_coal_bonus(self):
        return self.altar.coal_bonus()

    @property
    def inventory_slots(self):
        return int(self.meta_stats["inventory"])

    # ---------- покупка мета-статов (кузница / древо) ----------
    def upgrade_meta_stat(self, key):
        d = META_STAT_DEFS[key]
        cur = self.meta_stats[key]
        if cur >= d["max"]:
            return False, "Максимум"
        pool = self.talents.souls if d["currency"] == "souls" else self.gold_ingots
        if d["currency"] == "trophy":
            if not self.trophies:
                return False, "Нужен трофей"
            self.trophies.pop(next(iter(self.trophies)))
        elif pool < d["cost"]:
            return False, f"Мало {d['currency']}"
        else:
            if d["currency"] == "souls":
                self.talents.souls -= d["cost"]
            else:
                self.gold_ingots -= d["cost"]
        self.meta_stats[key] = min(d["max"], cur + d["step"])
        return True, str(self.meta_stats[key])

    # ---------- Кузница: обмен золотых слитков (п.6) ----------
    FORGE_MENU = [
        ("inventory_slot", "Слот инвентаря +1", 1),
        ("coal_drop", "Дроп углей +5%", 1),
        ("shard_drop", "Дроп осколков +5%", 2),
    ]

    def forge_buy(self, option):
        for key, _label, cost in self.FORGE_MENU:
            if option == key and self.gold_ingots >= cost:
                self.gold_ingots -= cost
                ok, res = self.upgrade_meta_stat(key)
                return ok, res
        return False, "Нет такой опции или мало слитков"

    # ---------- Души Боссов (п.3.1) ----------
    def grant_boss_souls(self, boss_id, level, ng_cycle):
        """Выдаёт души только при первом убийстве конкретного босса (+1 за NG+ цикл)."""
        from ..core.constants import SOULS_BY_BOSS
        base = SOULS_BY_BOSS.get(level, 0)
        gained = 0
        key = boss_id
        last = self.bosses_souls_given.get(key, -1)
        if ng_cycle > last:
            gained = base + (1 if ng_cycle >= 1 else 0)
            self.bosses_souls_given[key] = ng_cycle
        self.talents.souls += gained
        return gained

    # ---------- сериализация ----------
    def to_dict(self):
        return {
            "meta_stats": self.meta_stats,
            "gold_ingots": self.gold_ingots,
            "trophies": sorted(self.trophies),
            "bosses_souls_given": self.bosses_souls_given,
            "unlocked_perks": sorted(self.unlocked_perks),
            "discovered_runes": sorted(self.discovered_runes),
            "wall_rune_total": self.wall_rune_total,
            "talents": self.talents.to_dict(),
            "altar": self.altar.to_dict(),
            "legacy_coal_stacks": self.legacy_coal_stacks,
            "start_rune": self.start_rune,
            "start_perk": self.start_perk,
            "ng_cycle": self.ng_cycle,
            "ngpp_unlocked": self.ngpp_unlocked,
            "secret_ending_seen": self.secret_ending_seen,
            "deepest_level": self.deepest_level,
            "total_deaths": self.total_deaths,
            "settings": self.settings,
        }

    @classmethod
    def from_dict(cls, d):
        m = cls()
        m.meta_stats.update(d.get("meta_stats", {}))
        m.gold_ingots = d.get("gold_ingots", 0)
        m.trophies = set(d.get("trophies", []))
        m.bosses_souls_given = d.get("bosses_souls_given", {})
        m.unlocked_perks = set(d.get("unlocked_perks", []))
        m.discovered_runes = set(d.get("discovered_runes", []))
        m.wall_rune_total = d.get("wall_rune_total", 0)
        m.talents = TalentTree.from_dict(d.get("talents", {}))
        m.altar = LegacyAltar.from_dict(d.get("altar", {}))
        m.legacy_coal_stacks = d.get("legacy_coal_stacks", 0)
        m.start_rune = d.get("start_rune")
        m.start_perk = d.get("start_perk")
        m.ng_cycle = d.get("ng_cycle", 0)
        m.ngpp_unlocked = d.get("ngpp_unlocked", False)
        m.secret_ending_seen = d.get("secret_ending_seen", False)
        m.deepest_level = d.get("deepest_level", 0)
        m.total_deaths = d.get("total_deaths", 0)
        m.settings.update(d.get("settings", {}))
        return m


# ---------- настройки управления (п.2: всё ремапится) ----------
DEFAULT_SETTINGS = {
    "keys": {
        "forward": "w", "back": "s", "left": "a", "right": "d",
        "attack_light": "mouse0", "attack_heavy": "mouse2",
        "dodge": "shift", "cast_fire": "q", "cast_ice": "e",
        "interact": "f", "inventory": "i", "map": "m",
        "potion1": "1", "potion2": "2", "potion3": "3", "potion4": "4",
    },
    "invert_move_on_puddle": True,   # инверсия НЕ трогает мышь/камеру
}


def save_game(meta: MetaState, run_state=None, path=SAVE_PATH):
    data = {"version": 1, "meta": meta.to_dict()}
    if run_state is not None:
        data["run"] = run_state
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)
    return path


def load_game(path=SAVE_PATH):
    """Возвращает пару (MetaState, run_state). Нет файла — (None, None)."""
    if not os.path.exists(path):
        return None, None
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return MetaState.from_dict(data.get("meta", {})), data.get("run")


def load_meta(path=SAVE_PATH):
    """Только мета-состояние из сохранения (или None, если файла нет)."""
    meta, _run = load_game(path)
    return meta
