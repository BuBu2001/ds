"""NG+ циклы и модификаторы (ТЗ п.19): вход, перенос/сброс, масштабы, выбор модов."""
import random
from ..core import constants as C
from ..data import loader

# п.19.4: таблица циклов. NG+5+: +0.7 HP-множитель и +0.4 урон-множитель за цикл,
# модификаторов — максимум 4.
HP_MULT_BY_CYCLE = {1: 1.5, 2: 2.0, 3: 2.8, 4: 3.5}
DMG_MULT_BY_CYCLE = {1: 1.3, 2: 1.6, 3: 2.0, 4: 2.5}
MODS_COUNT_BY_CYCLE = {1: 1, 2: 2, 3: 3, 4: 4}
MAX_MODS = 4


def ng_mults(cycle):
    """(hp_mult, dmg_mult, n_modifiers) для цикла NG+ (0 = обычный прогон)."""
    if cycle <= 0:
        return 1.0, 1.0, 0
    hp = HP_MULT_BY_CYCLE.get(cycle, 3.5 + 0.7 * (cycle - 4))
    dmg = DMG_MULT_BY_CYCLE.get(cycle, 2.5 + 0.4 * (cycle - 4))
    n_mods = min(MAX_MODS, MODS_COUNT_BY_CYCLE.get(cycle, MAX_MODS))
    return hp, dmg, n_mods


def can_enter_ng_plus(meta, ng_cycle_completed):
    """п.19.1: убить босса 15 ур. → активировать «Разрыв» у Главного Костра."""
    uid = f"twisted_mage_L{ng_cycle_completed}"
    return any(u.startswith("twisted_mage_L") for u in meta.bosses_first_kill) or \
        ("twisted_mage", ng_cycle_completed) in {(b, c) for b, c in
                                                 [tuple(x.rsplit("_L", 1)) for x in meta.bosses_first_kill
                                                  if "_L" in x]}


def roll_modifiers(cycle, rng=random):
    """Случайный набор модификаторов для цикла (п.19.5)."""
    _, _, n = ng_mults(cycle)
    ids = list(loader.modifiers().keys())
    return set(rng.sample(ids, n)) if n else set()


def apply_reset(wallet, rune_system, inventory, crafter=None):
    """п.19.3: сбрасывается при входе в NG+.

    Сбрасывается: временные руны, зелья, Угли, Осколки (кроме мета-бонусов).
    Переносится (не трогаем здесь): мета-статы, Древо Талантов, наследия,
    постоянные руны, рецепты.
    """
    wallet.coal = 0
    wallet.shards = 0
    if rune_system is not None:
        rune_system.clear_temporary()
    if inventory is not None:
        inventory.clear_consumables()


def secret_level_available(meta, ng_cycle, killed_boss_15_this_run, abyss_keys):
    """п.19.7: 20-й уровень «Трон Бездны» — NG+2+, босс 15 в текущем забеге,
    3 Ключа Бездны (с боссов 5/10/15 в NG+2+), активированный Разрыв."""
    return (ng_cycle >= 2 and killed_boss_15_this_run
            and abyss_keys >= C.ABYSS_KEYS_REQUIRED)


def choose_ending(meta, choice):
    """п.19.8: 'burn' — сжечь Сердце (титры, персонаж исчезает, мета сохраняется);
    'consume' — поглотить (открывает NG++ — бесконечный режим)."""
    if choice == "consume":
        meta.ngpp_unlocked = True
        meta.secret_ending_seen = True
    elif choice == "burn":
        meta.secret_ending_seen = True
    else:
        raise ValueError(f"неизвестная концовка: {choice}")
    return choice


# Параметры NG++ (п.19.8): все модификаторы, случайный босс каждые 5 уровней,
# смерть окончательная, лидерборд по глубине.
NGPP_RULES = {
    "all_modifiers": True,
    "random_boss_every": 5,
    "permadeath": True,
    "leaderboard_metric": "deepest_level",
}
