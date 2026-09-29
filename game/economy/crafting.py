"""Крафт (ТЗ п.5, 17.3): зелья, эликсиры, руны из материалов и осколков."""
import random
from ..core import constants as C
from ..data import loader


class Inventory:
    """Материалы + готовые предметы. Слоты ограничены мета-статом (6–12).

    Материалы хранятся безлимитно (отдельная вкладка UI, п.20.4),
    слоты ограничивают число *разных* зелий/рун в быстром доступе.
    """

    def __init__(self, slots=C.INV_SLOTS_BASE):
        self.materials = {}      # id -> count (в т.ч. 'x_ench' варианты)
        self.potions = []        # id рецептов готовых зелий (быстрые слоты 1-4)
        self.slots = slots

    def add_material(self, mid, n=1):
        self.materials[mid] = self.materials.get(mid, 0) + n

    def has_material(self, mid, n=1):
        # зачарованный материал заменяет обычный при проверке? Нет: не стакаются.
        return self.materials.get(mid, 0) >= n

    def spend_material(self, mid, n=1):
        if self.has_material(mid, n):
            self.materials[mid] -= n
            if self.materials[mid] <= 0:
                del self.materials[mid]
            return True
        return False

    def add_potion(self, recipe_id):
        if len(self.potions) < self.slots:
            self.potions.append(recipe_id)
            return True
        return False


class Crafter:
    """Крафт по рецептам JSON. Модификатор «Скупость» отключает лечение травой."""

    def __init__(self, wallet, rng=random):
        self.wallet = wallet
        self.rng = rng

    def can_craft(self, recipe_id, inventory):
        r = loader.recipes()[recipe_id]
        for ing in r["ingredients"]:
            if "shards" in ing:
                if self.wallet.shards < ing["shards"]:
                    return False
            else:
                if not inventory.has_material(ing["material"], ing["count"]):
                    # допускаем зачарованную версию как замену
                    if not inventory.has_material(ing["material"] + "_ench", ing["count"]):
                        return False
        return True

    def craft(self, recipe_id, inventory, perksystem=None):
        """Возвращает (успех, сообщение). Зачарованные материалы дают +1 силы эффекта."""
        recipes = loader.recipes()
        if recipe_id not in recipes:
            return False, "Нет такого рецепта"
        r = recipes[recipe_id]
        if not self.can_craft(recipe_id, inventory):
            return False, "Недостаточно материалов/осколков"
        enchanted_used = False
        for ing in r["ingredients"]:
            if "shards" in ing:
                self.wallet.spend_shards(ing["shards"])
            else:
                if inventory.spend_material(ing["material"], ing["count"]):
                    pass
                else:
                    inventory.spend_material(ing["material"] + "_ench", ing["count"])
                    enchanted_used = True
        eff = dict(r["effect"])
        if enchanted_used and "value" in eff:
            eff["value"] += 0.05  # «+1 к силе» упрощённо как +5%
        if eff["kind"] == "unlock_random_perk":
            if perksystem and perksystem.unlock_random():
                return True, "Открыт случайный перк!"
            return True, "Все перки уже открыты"
        if eff["kind"] == "apply_rune":
            return True, f"Руна «{r['name']}» готова к наложению"
        inventory.add_potion(recipe_id)
        effects = getattr(inventory, "potion_effects", {})
        effects[recipe_id] = eff
        inventory.potion_effects = effects
        return True, f"Скрафчено: {r['name']}" + (" (зачарованное)" if enchanted_used else "")
