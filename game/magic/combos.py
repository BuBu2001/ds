"""Комбо-система магии (ТЗ п.8.2): взаимодействия Огонь/Лёд/Меч + Пар."""
from ..core import constants as C


def sword_hit(target, base_damage, is_heavy=False, stats=None):
    """Расчёт удара мечом по состоянию цели.

    Возвращает dict: damage, crit, effects(список строк для UI), freeze_shatter.
    """
    res = {"damage": base_damage, "crit": False, "effects": [], "shatter": False}
    st = target.status
    if st.frozen:
        # Меч по замороженному: гарантированный крит x2 + разлом брони
        res["crit"] = True
        res["damage"] *= 2.0
        st.apply("armor_break", C.SWORD_BREAK_ARMOR_DUR, stacks=C.SWORD_BREAK_ARMOR_PCT)
        res["effects"].append("Разлом брони!")
        res["shatter"] = True
        st.remove("frozen")
        if stats and stats.get("combo_bonus"):
            res["damage"] *= 1 + stats["combo_bonus"]
        if st.has("burn"):
            res["damage"] *= 1.5
            res["effects"].append("Замороженный+горящий: +50%")
        stats_obj = getattr(target, "stats", None)
        if stats_obj:
            stats_obj.frozen_shattered += 1
    elif st.has("brittle"):
        # Меч по хрупкому: +20% урона, +10% крит-шанса
        res["damage"] *= 1.2
        if _roll_crit(stats):
            res["crit"] = True
            res["damage"] *= 2.0
        res["effects"].append("Хрупкость: +20%")
    elif _roll_crit(stats):
        res["crit"] = True
        res["damage"] *= 2.0
    return res


def fire_hit(target, base_fire_damage, stats=None):
    """Огонь по цели. Если заморожена — мгновенное испарение и облако пара."""
    res = {"damage": base_fire_damage, "steam": False, "effects": []}
    st = target.status
    if st.frozen:
        st.remove("frozen")
        res["steam"] = True
        res["steam_damage"] = base_fire_damage * C.STEAM_DMG_PCT
        res["effects"].append("Испарение! Облако пара")
        return res
    max_stacks = C.BURN_STACKS + (stats or {}).get("burn_extra_stacks", 0)
    st.apply("burn", C.BURN_DURATION, stacks=1, max_stacks=max(3, max_stacks))
    res["effects"].append("Горение")
    return res


def ice_hit(target, base_ice_damage, freeze_chance=0.0, stats=None):
    """Лёд по цели. По горящему — тушение, 20% урона, Хрупкость 5 сек."""
    res = {"damage": base_ice_damage, "effects": [], "extinguished": False}
    st = target.status
    if st.has("burn"):
        # Лёд по горящему
        res["damage"] = base_ice_damage * C.ICE_EXTINGUISH_DMG_PCT
        st.remove("burn")
        st.apply("brittle", C.BRITTLE_ON_EXTINGUISH)
        res["extinguished"] = True
        res["effects"].append("Тушение! Хрупкость")
        return res
    chance = freeze_chance + (stats or {}).get("freeze_bonus", 0.0)
    if _roll(chance):
        dur = C.FREEZE_BOSS if getattr(target, "is_boss", False) else C.FREEZE_NORMAL
        st.apply("frozen", dur)
        res["effects"].append("Заморозка")
        if stats:
            stats["freezes"] = stats.get("freezes", 0) + 1
    return res


def steam_cloud(world, pos, radius, damage, duration=C.STEAM_DURATION):
    """Облако пара: АОЕ-урон + -50% точности врагов. Не стакается."""
    world.spawn_steam(pos, radius, damage, duration)


def _roll(p):
    import random
    return random.random() < p


def _roll_crit(stats):
    chance = (stats or {}).get("crit_chance", 0.05)
    return _roll(chance)
