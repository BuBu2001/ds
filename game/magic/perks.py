"""Система перков (ТЗ п.18): 25 перков, условия-счётчики, стартовые перки, «Без костра»."""
import random
from ..data import loader


class PerkSystem:
    def __init__(self, rng=random):
        self.rng = rng
        self.defs = loader.perks()
        self.unlocked = set()          # id открытых перков
        self.starting = []             # до 3 активных стартовых перков (п.6.1)

    # --- автооткрытие по счётчикам статистики игрока ---
    def check_unlocks(self, counters):
        newly = []
        for pid, p in self.defs.items():
            if pid in self.unlocked:
                continue
            stat, need = p["condition"]["stat"], p["condition"]["count"]
            if counters.get(stat, 0) >= need:
                self.unlocked.add(pid)
                newly.append(p)
        return newly

    def unlock_random(self):
        """Рецепт «Случайный перк» за 3 осколка."""
        locked = [pid for pid in self.defs if pid not in self.unlocked]
        if not locked:
            return None
        pid = self.rng.choice(locked)
        self.unlocked.add(pid)
        return self.defs[pid]

    def active_perks(self):
        """Перки, реально влияющие на игру: все открытые + выбранные стартовые."""
        return [self.defs[pid] for pid in self.unlocked | set(self.starting)
                if pid in self.defs]

    def effects_merged(self):
        merged = {}
        for p in self.active_perks():
            for k, v in p["effects"].items():
                merged[k] = merged.get(k, 0) + v
        return merged

    def has(self, pid):
        return pid in self.unlocked or pid in self.starting

    def burn_on_rest(self, counters=None):
        """п.7: перки с флагом burns_on_rest (например «Без костра»)
        сгорают при первом отдыхе за забег."""
        burned = []
        for pid in list(self.unlocked) + list(self.starting):
            p = self.defs.get(pid, {})
            if p.get("burns_on_rest"):
                if pid in self.unlocked:
                    self.unlocked.discard(pid)
                if pid in self.starting:
                    self.starting.remove(pid)
                burned.append(pid)
        return burned

    # --- спецусловия из ТЗ ---
    def sword_only_d5_check(self, run_stats):
        """Минималист: если на ур.1–5 использовалось только оружие melee_sword."""
        return run_stats.get("methods_used", set()) <= {"sword"} and run_stats.get("level") == 5

    def pacifist_check(self, run_stats):
        return run_stats.get("kills", 0) == 0

    def apply_run_end(self, run_stats, counters):
        """Достижения уровня: без отдыха / без урона / пацифист и т.д."""
        lvl = run_stats.get("level", 1)
        if run_stats.get("rests", 0) == 0:
            counters["levels_no_rest"] += 1
            if lvl >= 5:
                counters["dungeons_no_rest"] += 1
        if run_stats.get("damage_taken", 0) == 0:
            counters["levels_no_damage"] += 1
        if self.pacifist_check(run_stats):
            counters["pacifist_runs"] += 1
        if self.sword_only_d5_check(run_stats):
            counters["sword_only_d5"] = max(counters.get("sword_only_d5", 0), 1)
        if run_stats.get("coal_at_level5", 0) >= 500:
            counters["coal_early"] = max(counters.get("coal_early", 0), 500)
        if run_stats.get("boss_no_damage"):
            counters["bosses_no_damage"] += 1
