"""UI Layer: модели экранов (ТЗ п.20). Чистая логика — без pygame, тестируется headless."""
from ..core.math_utils import Vector2


class HudModel:
    """п.20.1: HP/мана/стамина, угли/осколки, иконки состояний, миникарта."""

    def __init__(self, world):
        self.world = world

    def snapshot(self):
        p = self.world.player
        w = self.world.wallet
        return {
            "hp": (p.hp, p.max_hp),
            "mana": (p.mana, p.max_mana),
            "stamina": (p.stamina, p.max_stamina),
            "coal": w.coal,
            "shards": w.shards,
            "level": self.world.level,
            "ng_cycle": self.world.ng_cycle,
            "status_icons": [b["kind"] for b in p.buffs] + list(p.status.active_names()
                            if hasattr(p.status, "active_names") else []),
            "inverted": p.control_inverted_timer > 0,
            "minimap": MapModel(self.world).points(),
        }


class MapModel:
    """п.20.1 (миникарта) и клавиша M: призраки, костры, босс-рум."""

    def __init__(self, world):
        self.world = world

    def points(self):
        w = self.world
        pts = [("player", w.player.pos.as_tuple())]
        if w.ghost:
            pts.append(("ghost", w.ghost.pos.as_tuple()))
        for cf in w.campfires:
            pts.append(("campfire_fired" if cf.activated else "campfire", cf.pos.as_tuple()))
        if w.boss and w.boss.alive:
            pts.append(("boss", w.data.boss_room_center))
        pts.append(("exit", w.exit_pos.as_tuple()))
        return pts

    def explored_cells(self):
        """Клетки в радиусе видимости игрока — для тумана войны."""
        p = self.world.player
        cx, cy = int(p.pos.x), int(p.pos.y)
        r = 8
        out = set()
        for y in range(max(0, cy - r), min(len(self.world.grid), cy + r + 1)):
            for x in range(max(0, cx - r), min(len(self.world.grid[0]), cx + r + 1)):
                out.add((x, y))
        return out


class CampfireScreenModel:
    """п.20.2: прокачка (3 ползунка), крафт (4 слота), руны (3 слота), отдых, автосейв."""

    def __init__(self, world, campfire):
        self.world = world
        self.campfire = campfire

    def upgrade_options(self):
        """п.20.2 / п.5: прокачка урона/скорости/выносливости за Угли у костра."""
        e, w = self.world.economy, self.world.wallet
        st = self.world.player.stats_obj
        out = []
        for key, name, lvl, maxlvl, cost_fn in (
                ("damage", "Урон", st.damage_level, C_MAX_DAMAGE, e.damage_cost),
                ("speed", "Скорость атаки", st.speed_level, C_MAX_SPEED, e.speed_cost),
                ("stamina", "Выносливость", st.stamina_level, C_MAX_STAMINA, e.stamina_cost)):
            cost = None if lvl >= maxlvl else cost_fn(lvl + 1)
            out.append({"stat": key, "name": name, "level": lvl,
                        "max": maxlvl, "cost": cost,
                        "affordable": cost is not None and w.coal >= cost})
        return out

    def do_upgrade(self, stat):
        e, w, st = self.world.economy, self.world.wallet, self.world.player.stats_obj
        table = {"damage": ("damage_level", e.damage_cost, C_MAX_DAMAGE),
                 "speed": ("speed_level", e.speed_cost, C_MAX_SPEED),
                 "stamina": ("stamina_level", e.stamina_cost, C_MAX_STAMINA)}
        attr, fn, mx = table[stat]
        lvl = getattr(st, attr)
        if lvl >= mx:
            return False, "Максимум"
        cost = fn(lvl + 1)
        if not w.spend_coal(cost):
            return False, "Недостаточно углей"
        if stat == "damage":
            st.damage_level += 1
        elif stat == "speed":
            st.speed_level += 1
        else:
            st.stamina_level += 1
        return True, f"{stat} → ур.{lvl + 1}"

    def craft_slots(self):
        """Слоты крафта (п.20.2): зелья + эликсиры из рецептов."""
        from ..data import loader
        crafter, inv = self.world.crafter, self.world.inventory
        slots = []
        for rid, r in loader.recipes().items():
            slots.append({"recipe": rid, "name": r.get("name", rid),
                          "can_craft": bool(crafter.can_craft(rid, inv))})
        return slots

    def do_craft(self, recipe_id):
        crafter, inv = self.world.crafter, self.world.inventory
        return crafter.craft(recipe_id, inv, self.world.perksystem)

    def rune_slots(self):
        rs = self.world.rune_system
        return [{"slot": i, "rune": a} for i, a in enumerate(rs.active())]

    def rest(self):
        """Отдых у костра (п.5): восстановление, слёт временных рун, +1 угроза."""
        ok = self.campfire.rest(self.world.player, self.world.rune_system)
        if ok:
            self.campfire._closed = False  # экран остаётся открытым после отдыха
        return ok, self.campfire.rests_left

    def close(self):
        """Закрыть экран костра (клавиша выхода)."""
        self.campfire._closed = True


C_MAX_DAMAGE, C_MAX_SPEED, C_MAX_STAMINA = 20, 15, 20


class InventoryModel:
    """п.20.4: 6–12 слотов, зелья 1–4, материалы/руны/перки — вкладки."""

    def __init__(self, world):
        self.world = world

    def tabs(self):
        w = self.world
        return {
            "potions": list(w.inventory.potions),
            "materials": dict(w.inventory.materials),
            "runes": [dict(r) for r in w.rune_system.active()],
            "perks": [{"id": pid, **self._perk_progress(pid)}
                      for pid in sorted(w.perksystem.unlocked)],
            "slots_free": max(0, w.inventory.slots - len(w.inventory.potions)),
        }

    def _perk_progress(self, pid):
        from ..data import loader
        pdef = loader.perks().get(pid, {})
        need = pdef.get("condition", {})
        return {"name": pdef.get("name", pid), "need": need}

    def use_potion(self, slot_index):
        """Быстрый слот 1–4 (клавиши 1..4)."""
        inv = self.world.inventory
        p = self.world.player
        if not (0 <= slot_index < len(inv.potions)):
            return False, "Пустой слот"
        rid = inv.potions.pop(slot_index)
        from ..data import loader
        eff = loader.recipes()[rid]["effect"]
        kind, value = eff["kind"], eff.get("value", 0)
        dur = eff.get("duration", 10.0)
        if kind == "heal":
            p.hp = min(p.max_hp, p.hp + value * p.max_hp)
        elif kind == "mana":
            p.mana = min(p.max_mana, p.mana + value * p.max_mana)
        elif kind in ("hot", "fury", "resist"):
            p.buffs.append({"kind": kind, "value": value, "duration": dur,
                            "orig_duration": dur})
        p.stats_obj.counters["potions_used"] += 1
        return True, rid


class DeathScreenModel:
    """п.20.5: счётчик потерянных углей, подсказка про призрак, «Продолжить»."""

    def __init__(self, world):
        self.world = world

    def info(self):
        g = self.world.ghost
        return {
            "lost_coal": g.coal if g else 0,
            "hint": "Призрак ждёт на месте смерти." if g
                    else "Угли сгорели — вы погибли в недостижимой зоне.",
            "continue_label": "Продолжить",
        }


class BonfireHubModel:
    """п.20.3 Главный Костёр: древо, алтарь, сундук, кузница, выбор NG+."""

    def __init__(self, meta):
        self.meta = meta

    def panels(self):
        return {
            "talent_tree": self.meta.talents.tree_summary()
            if hasattr(self.meta.talents, "tree_summary") else "3 ветки",
            "altar": self.meta.altar.to_dict(),
            "trophy_chest": sorted(self.meta.trophies),
            "forge_gold": self.meta.gold_ingots,
            "ng_cycle": self.meta.ng_cycle,
            "ngpp": self.meta.ngpp_unlocked,
        }
