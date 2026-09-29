"""Economy Layer (ТЗ п.3, 10, 17): валюты, формулы стоимости, дроп, обмен.

Валюты: Угли (прокачка), Осколки (крафт/руны), Души Боссов и Золотые слитки (мета).
"""
import random
from ..core import constants as C


class Wallet:
    """Кошелёк всех четырёх валют + статистика для перков."""

    def __init__(self):
        self.coal = 0            # теряется при смерти
        self.shards = 0          # не теряется
        self.boss_souls = 0      # мета-валюта Древа Талантов
        self.gold_ingots = 0     # мета-валюта Кузницы
        self.total_coal_earned = 0

    # --- базовые операции -------------------------------------------
    def add_coal(self, n):
        self.coal += n
        self.total_coal_earned += n

    def spend_coal(self, n):
        if self.coal >= n:
            self.coal -= n
            return True
        return False

    def add_shards(self, n):
        self.shards += n

    def spend_shards(self, n):
        if self.shards >= n:
            self.shards -= n
            return True
        return False


class Economy:
    """Формулы экономики. Знает про meta-бонусы и модификаторы NG+."""

    def __init__(self, meta=None, modifiers=None):
        self.meta = meta
        self.modifiers = modifiers or set()

    # ---------- стоимости прокачки (п.3.2) ----------
    @staticmethod
    def damage_cost(level):
        return round(C.DMG_UP_BASE * C.DMG_UP_GROWTH ** (level - 1))

    @staticmethod
    def speed_cost(level):
        return round(C.SPD_UP_BASE * C.SPD_UP_GROWTH ** (level - 1))

    @staticmethod
    def stamina_cost(level):
        return round(C.STA_UP_BASE * C.STA_UP_GROWTH ** (level - 1))

    def apply_discount(self, cost, campfire_upgrades):
        """Скидка 10% за улучшение костра «stat_discount» (п.5)."""
        if campfire_upgrades.get("stat_discount", 0) > 0:
            cost = int(cost * 0.9)
        return max(1, cost)

    # ---------- обмен (п.3.1) ----------
    def exchange_rate(self):
        """Обычно 10 углей = 1 осколок; при «Жадности бездны» — обратно."""
        if "abyss_greed" in self.modifiers:
            return ("shard_to_coal", 10)   # 1 осколок = 10 углей
        return ("coal_to_shard", C.COAL_TO_SHARD_RATE)

    def exchange(self, wallet, direction):
        kind, rate = self.exchange_rate()
        if direction == kind:
            if wallet.spend_coal(rate):
                wallet.add_shards(1)
                return True
            return False
        if direction == "shard_to_coal":
            if wallet.spend_shards(1):
                wallet.add_coal(rate)
                return True
        elif direction == "coal_to_shard":
            if wallet.spend_coal(rate):
                wallet.add_shards(1)
                return True
        return False

    # ---------- дроп углей (п.3.1, п.22) ----------
    def coal_drop(self, kind, dungeon_level, threat_stacks=0, rng=random):
        """kind: 'normal' | 'elite' | 'boss'. Формула: base * (1 + 0.1*lvl)."""
        if "abyss_greed" in self.modifiers and kind != "boss":
            return 0
        lo, hi = {"normal": C.COAL_NORMAL, "elite": C.COAL_ELITE,
                  "boss": C.COAL_BOSS}[kind]
        base = rng.randint(lo, hi)
        amount = base * (1 + 0.1 * dungeon_level)
        amount *= 1 + C.REST_THREAT_DROP * threat_stacks
        if "campfire_curse" in self.modifiers:
            amount *= 1.25
        amount *= 1 + self.meta_coal_bonus()
        return int(amount)

    def meta_coal_bonus(self):
        bonus = 0.0
        if self.meta:
            bonus += getattr(self.meta, "coal_drop_pct", 0.0)
            bonus += self.meta.legacy_coal_bonus()
        return min(bonus, 0.25 + 0.25)  # кап мета + наследие

    # ---------- дроп осколков ----------
    def shard_drop_elite(self, dungeon_level, rng=random):
        if "abyss_greed" in self.modifiers:
            chance = 0.10
        else:
            chance = C.SHARD_ELITE_CHANCE + max(0, dungeon_level - 10) * 0.01
        chance += self.meta_shard_bonus()
        return 1 if rng.random() < chance else 0

    def shard_drop_boss(self, rng=random):
        return rng.randint(*C.SHARD_BOSS)

    def meta_shard_bonus(self):
        return self.meta.shard_drop_pct if self.meta else 0.0

    # ---------- смерть (п.10) ----------
    def death_loss(self, wallet, perk_loss_override=None):
        """Возвращает количество углей, которое заберёт призрак."""
        pct = perk_loss_override if perk_loss_override is not None else C.COAL_LOSS_PCT
        lost = int(wallet.coal * pct)  # округление вниз
        wallet.coal -= lost
        return lost

    # ---------- дроп материалов (п.17.1) ----------
    def roll_materials(self, mat_table, is_elite, dungeon_level, ng_plus=False,
                       rng=random):
        """actual_drop = base * (1 + 0.02 * (lvl - min_level))."""
        drops = {}
        mult = 2.0 if "blood_moon" in self.modifiers else 1.0
        for m in mat_table.values():
            lo_lvl, hi_lvl = m["levels"]
            if not (lo_lvl <= dungeon_level <= hi_lvl):
                continue
            base = m["drop_elite"] if is_elite else m["drop_normal"]
            chance = base * (1 + 0.02 * (dungeon_level - lo_lvl))
            if rng.random() < chance:
                c_lo, c_hi = (m["count_elite"] if is_elite else m["count_normal"])
                count = rng.randint(c_lo, c_hi) * int(mult)
                if count == 0:
                    count = 1
                enchanted = ng_plus and rng.random() < C.NG_ENCHANT_CHANCE
                key = m["id"] + ("_ench" if enchanted else "")
                drops[key] = drops.get(key, 0) + count
        return drops

    def boss_materials(self, mat_table, dungeon_level, ng_plus=False, rng=random):
        """3–5 случайных материалов текущего тира (гарантированно)."""
        tier = [m for m in mat_table.values()
                if m["levels"][0] <= dungeon_level <= m["levels"][1]]
        if not tier:
            return {}
        n = rng.randint(3, 5)
        drops = {}
        for _ in range(n):
            m = rng.choice(tier)
            c_lo, c_hi = m["count_normal"]
            enchanted = ng_plus and rng.random() < C.NG_ENCHANT_BOSS_CHANCE
            key = m["id"] + ("_ench" if enchanted else "")
            drops[key] = drops.get(key, 0) + rng.randint(c_lo, c_hi)
        return drops
