"""Маги-враги (ТЗ п.12): стейт-машины PATROL/SEEK_LOS/CASTING/RETREAT (+LAY_TRAP/SUMMON/CAST_FEAR).

Все маги: прекаст 1.5–2.5 сек, прерывание накопленным уроном > 10% макс HP за каст,
могут баффать союзников (+30% урона 10с / +50% скорости 5с / щит 200), приоритетная цель.
"""
import random
from enum import Enum
from ..core.state_machine import StateMachine
from .base import Entity, IcePuddle
from ..core.math_utils import Vector2


class MageState(Enum):
    PATROL = 1
    SEEK_LOS = 2
    CASTING = 3
    CAST_FEAR = 4
    LAY_TRAP = 5
    SUMMON = 6
    BUFF = 7
    RETREAT = 8
    DEAD = 9


DETECT_RANGE = 15.0
CLOSE_RANGE = 5.0
FAR_RANGE = 8.0


class Mage(Entity):
    """Базовый маг. Подтипы меняют поведение через `cast_fn` и набор состояний."""

    MAGE_TYPE = "fire"
    CAST_DURATION = 2.0
    CAST_COOLDOWN = 3.0
    HP = 60
    DAMAGE = 25

    def __init__(self, pos, mage_type=None, ng_dmg_mult=1.0, threat_stacks=0,
                 is_elite=False, modifiers=(), rng=random):
        mt = mage_type or self.MAGE_TYPE
        hp = self.HP * (2.0 if is_elite else 1.0)
        super().__init__(pos, hp=hp, radius=0.5)
        self.mage_type = mt
        self.kind = f"mage_{mt}"
        self.display_name = {"fire": "Огненный маг", "ice": "Ледяной маг",
                             "dark": "Тёмный маг", "summoner": "Призыватель"}[mt]
        if is_elite:
            self.display_name = "Элитный " + self.display_name
        self.is_elite = is_elite
        self.damage = self.DAMAGE * ng_dmg_mult * (1.5 if is_elite else 1.0) * (1 + 0.1 * threat_stacks)
        self.speed = 3.0
        self.rng = rng
        self.modifiers = modifiers
        self.silent = "silence_mod" in modifiers
        self.cast_timer = 0.0
        self.cast_damage_accum = 0.0     # урон, накопленный за текущий каст
        self.cooldown = 0.0
        self.last_known_player_pos = pos.copy()
        self.patrol_target = None
        self.seek_timeout = 0.0
        self.retreat_timer = 0.0
        self.buff_cd = 0.0
        self.sm = MageStateMachine(self)
        self.interrupted_bonus_taken = 0.0   # для Призывателя: +30% урона после прерывания

    @property
    def hp_ratio(self):
        return self.hp / max(1e-6, self.max_hp)

    def take_damage(self, amount, damage_type="physical"):
        # во время LAY_TRAP маг получает +20% урона; призыватель после прерванного
        # призыва — +30% получаемого урона (п.12.1)
        bonus = 1.0
        if self.sm.state == MageState.LAY_TRAP:
            bonus += 0.2
        if self.interrupted_bonus_taken > 0:
            bonus += 0.3
        dealt = super().take_damage(amount * bonus, damage_type=damage_type)
        if self.sm.state in (MageState.CASTING, MageState.CAST_FEAR, MageState.SUMMON):
            self.cast_damage_accum += dealt
            threshold = self.max_hp * 0.10
            if self.cast_damage_accum > threshold:
                self.on_cast_interrupted(self.sm.state)
                world = getattr(self, "world_ref", None)
                if world:
                    world.on_mage_interrupted(self)
                self.sm.change(MageState.RETREAT)
                self.retreat_timer = 2.0
                self.cooldown = 1.0
        return dealt

    def on_cast_interrupted(self, state):
        if self.mage_type == "summoner":
            self.interrupted_bonus_taken = 5.0   # +30% урона по призывателю на 5 сек

    def update(self, dt, world):
        self.world_ref = world
        if not self.alive:
            self.sm.change(MageState.DEAD)
            return
        self.update_status(dt, world)
        if not self.alive:
            world.on_enemy_death(self, by_burn=True)
            return
        if self.status.frozen:
            return
        self.cooldown = max(0.0, self.cooldown - dt)
        self.buff_cd = max(0.0, self.buff_cd - dt)
        # таймер штрафа призывателя: 5 сек после прерванного призыва
        if self.interrupted_bonus_taken > 0:
            self.interrupted_bonus_taken -= dt
            if self.interrupted_bonus_taken < 0:
                self.interrupted_bonus_taken = 0.0
        self.sm.update(dt, {"dt": dt, "world": world})
        self._act(dt, world)

    def effective_damage_taken_mult(self):
        m = 1.0 + self.interrupted_bonus_taken - (1.0 if self.interrupted_bonus_taken else 0)
        if self.sm.state == MageState.LAY_TRAP:
            m *= 1.2
        return m

    # ---------- поведение по состояниям ----------
    def _move_toward(self, target, dt, speed_mult=1.0, world=None):
        to = target - self.pos
        d = to.length()
        if d < 0.3:
            return
        step = to.normalized() * self.speed * (1 - self.status.slow_pct) * speed_mult * dt
        new = self.pos + step
        if world and not world.is_wall(int(new.x), int(new.y)):
            self.pos = new

    def _move_away(self, threat_pos, dt, world):
        away = (self.pos - threat_pos).normalized()
        new = self.pos + away * self.speed * dt
        if world and not world.is_wall(int(new.x), int(new.y)):
            self.pos = new
        else:
            # упёрся — идем перпендикулярно
            perp = Vector2(-away.y, away.x)
            new = self.pos + perp * self.speed * dt
            if not world.is_wall(int(new.x), int(new.y)):
                self.pos = new

    def _act(self, dt, world):
        st = self.sm.state
        p = world.player
        if st == MageState.PATROL:
            if self.patrol_target is None or self.pos.distance_to(self.patrol_target) < 0.5:
                ang = self.rng.uniform(0, 6.28)
                self.patrol_target = self.pos + Vector2.from_angle(ang, 4)
            self._move_toward(self.patrol_target, dt, 0.5, world)
        elif st == MageState.SEEK_LOS:
            self.seek_timeout -= dt
            self._move_toward(self.last_known_player_pos, dt, 1.0, world)
        elif st in (MageState.CASTING, MageState.CAST_FEAR, MageState.SUMMON):
            self.cast_timer -= dt
            if self.cast_timer <= 0:
                self.finish_cast(world)
        elif st == MageState.LAY_TRAP:
            self.cast_timer -= dt
            if self.cast_timer <= 0:
                world.puddles.append(IcePuddle(self.pos.copy()))
                self.cooldown = 6.0
                self.sm.change(MageState.SEEK_LOS)
        elif st == MageState.BUFF:
            self.cast_timer -= dt
            if self.cast_timer <= 0:
                self.apply_buff(world)
                self.cooldown = self.CAST_COOLDOWN
                self.sm.change(MageState.SEEK_LOS)
        elif st == MageState.RETREAT:
            self.retreat_timer -= dt
            self._move_away(p.pos, dt, world)

    def start_cast(self, state, duration):
        self.sm.state = state
        self.sm.state_time = 0
        self.cast_timer = duration
        self.cast_damage_accum = 0.0

    def finish_cast(self, world):
        p = world.player
        self.cooldown = self.CAST_COOLDOWN
        if self.sm.state in (MageState.CASTING,):
            self.do_attack_cast(world)
        elif self.sm.state == MageState.CAST_FEAR:
            fear_radius = 4.0
            if self.pos.distance_to(p.pos) <= fear_radius:
                world.inflict_fear(p)
        elif self.sm.state == MageState.SUMMON:
            for i in range(2):
                from .mobs import Mob
                skel = Mob("skeleton", self.pos + Vector2(i - 0.5, 1),
                           modifiers=self.modifiers)
                skel.summoned_by = self
                world.enemies_list.append(skel)
        self.sm.change(MageState.SEEK_LOS)

    def do_attack_cast(self, world):
        raise NotImplementedError

    def apply_buff(self, world):
        allies = [e for e in world.enemies_list
                  if e is not self and e.alive and self.pos.distance_to(e.pos) < 10]
        if not allies:
            return
        ally = max(allies, key=lambda a: a.hp)
        buff = self.rng.choice(["damage", "speed", "shield"])
        if buff == "damage":
            ally.damage *= 1.3
            ally._buff_expiry = 10.0
        elif buff == "speed":
            ally.speed *= 1.5
            ally._buff_expiry = 5.0
        else:
            ally.hp = min(ally.max_hp + 200, ally.hp + 200)
        world.spawn_float_text(ally.pos, "+бафф")

    # проверка истечения баффа
    def tick_buff_expiry(self, dt):
        if hasattr(self, "_buff_expiry"):
            self._buff_expiry -= dt
            if self._buff_expiry <= 0:
                pass


class FireMage(Mage):
    MAGE_TYPE = "fire"
    CAST_DURATION = 2.0
    CAST_COOLDOWN = 3.0
    HP = 60
    DAMAGE = 25

    def do_attack_cast(self, world):
        p = world.player
        dirv = (p.pos - self.pos).normalized()
        world.spawn_enemy_projectile_from(self, "fireball", dirv,
                                          damage=self.damage, aoe=3.0)


class IceMage(Mage):
    MAGE_TYPE = "ice"
    CAST_DURATION = 2.0
    CAST_COOLDOWN = 2.5
    HP = 60
    DAMAGE = 15

    def do_attack_cast(self, world):
        p = world.player
        dirv = (p.pos - self.pos).normalized()
        world.spawn_enemy_projectile_from(self, "spike", dirv,
                                          damage=self.damage, slow=True)

    def _try_lay_trap(self, world):
        if self.cooldown <= 0:
            self.start_cast(MageState.LAY_TRAP, 1.0)
            return True
        return False


class DarkMage(Mage):
    MAGE_TYPE = "dark"
    CAST_DURATION = 2.5
    CAST_COOLDOWN = 8.0
    HP = 55
    DAMAGE = 10

    def do_attack_cast(self, world):
        # страх: игрок бежит 2 сек в случайном направлении
        p = world.player
        if self.pos.distance_to(p.pos) <= 4.0:
            world.inflict_fear(p)


class Summoner(Mage):
    MAGE_TYPE = "summoner"
    CAST_DURATION = 3.0
    CAST_COOLDOWN = 8.0
    HP = 70
    DAMAGE = 0

    def do_attack_cast(self, world):
        pass

    def on_cast_interrupted(self, state):
        self.interrupted_bonus_taken = 0.3
        # статистика игрока — засчитает мир
        world = getattr(self, "world_ref", None)
        if world:
            world.on_mage_interrupted(self)


MAGE_CLASSES = {"fire": FireMage, "ice": IceMage, "dark": DarkMage, "summoner": Summoner}


def make_mage(pos, rng=random.Random(), modifiers=(), ng_dmg_mult=1.0, threat=0):
    t = rng.choice(["fire", "ice", "dark", "summoner"])
    return MAGE_CLASSES[t](pos, modifiers=modifiers, ng_dmg_mult=ng_dmg_mult,
                           threat_stacks=threat, rng=rng)


class MageStateMachine(StateMachine):
    """Реализует таблицу триггеров ТЗ п.12.1 для всех магов."""

    def __init__(self, mage):
        super().__init__(MageState.PATROL)
        self.m = mage

    def check_transitions(self, ctx):
        m = self.m
        world = ctx["world"]
        p = world.player
        dist = m.distance_to(p)
        los = world.has_los(m.pos.as_tuple(), p.pos.as_tuple())
        if dist < 25:
            m.last_known_player_pos = p.pos.copy()
        st = self.state

        if st == MageState.PATROL:
            if dist < DETECT_RANGE and los and not m.silent:
                if dist < CLOSE_RANGE:
                    self._to_retreat()
                else:
                    self._begin_action()
            elif dist < DETECT_RANGE and not los:
                m.seek_timeout = 5.0
                self.change(MageState.SEEK_LOS)
        elif st == MageState.SEEK_LOS:
            if m.seek_timeout <= 0:
                self.change(MageState.PATROL)
            elif los and dist >= CLOSE_RANGE and m.cooldown <= 0 and not m.silent:
                self._begin_action()
            elif los and dist < CLOSE_RANGE:
                self._to_retreat()
        elif st in (MageState.CASTING, MageState.CAST_FEAR, MageState.SUMMON,
                    MageState.LAY_TRAP, MageState.BUFF):
            pass  # завершение/прерывание в Mage.update
        elif st == MageState.RETREAT:
            if m.retreat_timer <= 0 or dist > FAR_RANGE:
                if m.cooldown <= 0 and los and not m.silent:
                    self._begin_action()
                else:
                    self.change(MageState.SEEK_LOS)
            elif dist <= 2.0 and los:
                # «зажат» → кастует стоя
                if m.cooldown <= 0:
                    self._begin_action()

    def _to_retreat(self):
        self.m.retreat_timer = 2.0
        self.change(MageState.RETREAT)

    def _begin_action(self):
        m = self.m
        world = m.world_ref if hasattr(m, "world_ref") else None
        # Ледяной маг: если игрок на его луже и далеко → прямая атака; близко → retreat
        if m.mage_type == "ice" and world:
            on_puddle = any(pd.contains(m.pos) for pd in world.puddles)
            dist = m.distance_to(world.player)
            if on_puddle and dist < CLOSE_RANGE:
                self._to_retreat()
                return
        # иногда баффает союзников (приоритет ниже выживания)
        if m.buff_cd <= 0 and world and self._has_wounded_ally(world):
            m.buff_cd = 12.0
            m.start_cast(MageState.BUFF, 1.5)
            return
        if m.mage_type == "ice":
            dist = m.distance_to(world.player) if world else 10
            if dist < CLOSE_RANGE:
                self._to_retreat()
                return
            if world and m.cooldown <= 0 and m.rng.random() < 0.35:
                m.start_cast(MageState.LAY_TRAP, 1.0)
                return
            m.start_cast(MageState.CASTING, m.CAST_DURATION)
        elif m.mage_type == "dark":
            m.start_cast(MageState.CAST_FEAR, m.CAST_DURATION)
        elif m.mage_type == "summoner":
            m.start_cast(MageState.SUMMON, m.CAST_DURATION)
        else:
            m.start_cast(MageState.CASTING, m.CAST_DURATION)

    @staticmethod
    def _has_wounded_ally(world):
        for e in world.enemies_list:
            if e is not world.player and e.alive and getattr(e, "hp_ratio", 1) < 0.6 \
                    and e is not world.player:
                if world.player.distance_to(e) < 15:
                    return True
        return False
