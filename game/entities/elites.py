"""Элитные версии мобов (ТЗ п.11): ×2 HP, ×1.5 урона, +1 уникальная механика."""
import random
from .mobs import Mob, MOB_TABLE
from ..core.math_utils import Vector2


class EliteBase(Mob):
    """Общий каркас элитки: аура «Аура элиток» лечит мобов рядом (модификатор NG+)."""

    ELITE_MECHANIC = "none"

    def __init__(self, base_mob_id, pos, **kw):
        super().__init__(base_mob_id, pos, is_elite=True, **kw)
        self.mechanic = self.ELITE_MECHANIC
        self.phase_cd = 0.0

    def update(self, dt, world):
        super().update(dt, world)
        if not self.alive:
            return
        self.phase_cd = max(0.0, self.phase_cd - dt)
        self._mechanic_tick(dt, world)

    def _mechanic_tick(self, dt, world):
        pass


class GoblinShamanElite(EliteBase):
    """Гоблин-шаман (элитка): лечение союзника на 30% каждые 8 сек."""
    ELITE_MECHANIC = "heal_ally"

    def _mechanic_tick(self, dt, world):
        if self.phase_cd <= 0:
            allies = [e for e in world.enemies_list
                      if e is not self and e.alive and self.distance_to(e) < 10
                      and e.hp_ratio < 1.0]
            if allies:
                ally = min(allies, key=lambda a: a.hp_ratio)
                ally.heal(ally.max_hp * 0.30)
                world.spawn_float_text(ally.pos, "-30% хил")
                self.phase_cd = 8.0


class SkeletonKnightElite(EliteBase):
    """Скелет-рыцарь: щит спереди — блокирует все атаки во фронтальной дуге 120°."""
    ELITE_MECHANIC = "front_shield"

    def blocks_from(self, attack_dir):
        facing = getattr(self, "facing", None) or (self.summon_facing())
        d = attack_dir.normalized()
        f = facing.normalized()
        dot = d.x * f.x + d.y * f.y
        return dot < -0.5   # удар приходит «в щит» (спереди)

    def summon_facing(self):
        return Vector2(1, 0)


class SpiderQueenElite(EliteBase):
    """Паучиха: раз в 10 сек распыляет паутину — игрок замедлен на 30%, 5 сек."""
    ELITE_MECHANIC = "web_spray"

    def _mechanic_tick(self, dt, world):
        if self.phase_cd <= 0 and self.distance_to(world.player) < 6:
            world.player.status.apply("slow", 5.0, stacks=1)
            world.spawn_float_text(world.player.pos, "Паутина!")
            self.phase_cd = 10.0


class ZombieButcherElite(EliteBase):
    """Зомби-мясник: бросает топор (дальняя атака), затем подбирает."""
    ELITE_MECHANIC = "throw_axe"

    def _mechanic_tick(self, dt, world):
        if self.phase_cd <= 0 and self.sm.state == MobStateCache.CHASE \
                and 4 < self.distance_to(world.player) < 9:
            dirv = (world.player.pos - self.pos).normalized()
            world.spawn_enemy_projectile_from(self, "axe", dirv, damage=self.damage)
            self.phase_cd = 4.0


class MutantBehemothElite(EliteBase):
    """Мутант-бегемот: рывок к игроку каждые 12 сек."""
    ELITE_MECHANIC = "charge"

    def _mechanic_tick(self, dt, world):
        if self.phase_cd <= 0 and self.distance_to(world.player) < 12:
            self.dash_timer = 0.5
            self.dash_dir = (world.player.pos - self.pos).normalized()
            self.phase_cd = 12.0
        if getattr(self, "dash_timer", 0) > 0:
            self.dash_timer -= dt
            new = self.pos + self.dash_dir * 14 * dt
            if not world.is_wall(int(new.x), int(new.y)):
                self.pos = new
            if self.distance_to(world.player) < 1.0:
                world.damage_player(self.damage * 1.5)
                self.dash_timer = 0


class DemonOverlordElite(EliteBase):
    """Демон-владыка: аура страха радиус 5 м — игрок медленнее на 20%."""
    ELITE_MECHANIC = "fear_aura"

    def _mechanic_tick(self, dt, world):
        if self.distance_to(world.player) < 5:
            world.player.aura_slow_mult = 0.8
        else:
            world.player.aura_slow_mult = 1.0


ELITE_BY_MOB = {
    "goblin": GoblinShamanElite,
    "skeleton": SkeletonKnightElite,
    "spider": SpiderQueenElite,
    "zombie": ZombieButcherElite,
    "mutant": MutantBehemothElite,
    "wolf": MutantBehemothElite,
}


# мини-кэш состояний, чтобы не таскать enum между модулями
class MobStateCache:
    from ..entities.mobs import MobState as _MS
    CHASE = _MS.CHASE


def make_elite(pos, level, rng=random, **kw):
    pool = [k for k, v in MOB_TABLE.items() if v["tiers"][0] <= level <= v["tiers"][1]]
    mob_id = rng.choice(pool) if pool else "goblin"
    cls = ELITE_BY_MOB.get(mob_id, EliteBase)
    elite = cls(mob_id, pos, **kw)
    elite.display_name = "Элитный " + MOB_TABLE[mob_id]["name"]
    return elite
