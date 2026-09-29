"""Игрок: статы (п.4), прокачка (п.3.2), Player Combat State Machine (п.16)."""
import math
import random
from ..core import constants as C
from ..core.math_utils import Vector2
from ..core.state_machine import StateMachine
from ..entities.base import Entity
from ..economy.currency import Economy
from enum import Enum


class PlayerState(Enum):
    IDLE = 1
    MOVE = 2
    ATTACK_LIGHT = 3
    ATTACK_HEAVY = 4
    CASTING = 5
    DODGE = 6
    STUNNED = 7
    DEAD = 8


# Таблица прерываний (п.16.3): текущее -> {действие: 'now'|'buffer'|'charge'|'no'}
INTERRUPT_TABLE = {
    PlayerState.IDLE:          {"dodge": "now", "attack": "now", "cast": "now"},
    PlayerState.MOVE:          {"dodge": "now", "attack": "now", "cast": "now"},
    PlayerState.ATTACK_LIGHT:  {"dodge": "after50", "attack": "buffer", "cast": "no"},
    PlayerState.ATTACK_HEAVY:  {"dodge": "no", "attack": "no", "cast": "no"},
    PlayerState.CASTING:       {"dodge": "no", "attack": "no", "cast": "no"},
    PlayerState.DODGE:         {"dodge": "no", "attack": "no", "cast": "no"},
    PlayerState.STUNNED:       {"dodge": "no", "attack": "no", "cast": "no"},
}


class PlayerStats:
    """Уровни прокачки + перки + руны + мета-бонусы -> итоговые производные статы."""

    def __init__(self, meta=None):
        self.meta = meta or {}
        self.damage_level = 0
        self.speed_level = 0
        self.stamina_level = 0
        # счётчики достижений для перков
        self.counters = {
            "kills_fire": 0, "kills_ice": 0, "kills_sword": 0, "frozen_shattered": 0,
            "kills_steam": 0, "mages_interrupted": 0, "dungeons_no_rest": 0,
            "coal_total": 0, "bosses_no_damage": 0, "potions_used": 0,
            "kills_while_burning": 0, "freeze_kills": 0, "kills_steam_nohit": 0,
            "coal_early": 0, "sword_only_d5": 0, "ignited": 0, "freezes_anomaly": 0,
            "pacifist_runs": 0, "low_hp_executions": 0, "levels_no_rest": 0,
            "runes_applied": 0, "wall_runes": 0, "deaths": 0, "levels_no_damage": 0,
            "freezes": 0,
        }

    # --- базовые значения (п.4) ---
    def max_hp(self, perks=None, runes=None):
        v = C.HP_BASE + self.meta.get("hp", 0)
        v *= 1 + _sum_effect(perks, runes, "max_hp")
        return round(v)

    def max_mana(self, perks=None, runes=None):
        v = C.MANA_BASE + self.meta.get("mana", 0)
        v *= 1 + _sum_effect(perks, runes, "max_mana")
        return round(v)

    def max_stamina(self, perks=None, runes=None):
        v = C.STAMINA_BASE + self.stamina_level * C.STAMINA_PER_LEVEL + self.meta.get("stamina", 0)
        v *= 1 + _sum_effect(perks, runes, "max_stamina")
        return round(v)

    def base_damage(self, perks=None, runes=None):
        flat = 5 * _stacks(runes, "sharpening")
        v = C.DAMAGE_BASE + self.damage_level * C.DAMAGE_PER_LEVEL + flat
        v *= 1 + _sum_effect(perks, runes, "damage") + _sum_effect(perks, runes, "all_stats")
        return v

    def attack_speed(self, perks=None, runes=None):
        v = C.ATTACK_SPEED_BASE + self.speed_level * C.ATTACK_SPEED_PER_LEVEL
        v *= 1 + _sum_effect(perks, runes, "attack_speed")
        return v

    def stamina_regen(self, perks=None, runes=None):
        v = C.STAMINA_REGEN_BASE + self.stamina_level * C.STAMINA_REGEN_PER_LEVEL
        v += _flat_effect(perks, runes, "stamina_regen")
        return v

    def mana_regen(self, perks=None, runes=None):
        v = C.MANA_REGEN
        v += _flat_effect(perks, runes, "mana_regen")
        return v

    # --- стоимость действий с модификаторами ---
    def action_cost(self, action, perks=None, runes=None, anomaly_mult=1.0):
        base = {"light": C.COST_LIGHT_ATK, "heavy": C.COST_HEAVY_ATK,
                "dodge": C.COST_DODGE, "block": C.COST_BLOCK,
                "combo_frozen": C.COST_COMBO_FROZEN}[action]
        if action == "dodge":
            base *= 1 - _sum_effect(perks, runes, "dodge_cost_reduction")
        return base * anomaly_mult


def _sum_effect(perks, runes, key):
    total = 0.0
    for p in perks or []:
        total += p.get("effects", {}).get(key, 0.0)
    for r in runes or []:
        e = r.get("effects", {}).get(key, 0.0)
        total += e * r.get("stacks", 1) * (1 + 0.2 * r.get("enchanted", False))
    return total


def _flat_effect(perks, runes, key):
    return _sum_effect(perks, runes, key)


def _stacks(runes, rid):
    for r in runes or []:
        if r["id"] == rid:
            return r.get("stacks", 1)
    return 0


class Player(Entity):
    """Игрок со стейт-машиной, буфером ввода и инверсией управления."""

    def __init__(self, pos, economy: Economy, stats=None, perks=None, runes=None):
        st = stats or PlayerStats()
        super().__init__(pos, hp=st.max_hp(perks, runes))
        self.is_player = True
        self.kind = "player"
        self.stats_obj = st
        self.economy = economy
        self.perks = perks or []
        self.runes = runes or []
        self.perksystem = None  # ссылка на PerkSystem мира; назначает World
        self.mana = st.max_mana(self.perks, self.runes)
        self.stamina = st.max_stamina(self.perks, self.runes)
        self.wallet = None  # назначает мир
        self.aim_direction = Vector2(1, 0)
        self.control_inverted_timer = 0.0
        self.brittle_duration = 0.0
        self.input_buffer = None
        self.buffer_timer = 0.0
        self.stamina_regen_delay = 0.0
        self.heavy_charge = 0.0
        self.in_boss_room = False
        self.sm = PlayerStateMachine(self)
        self.speed = 5.0
        self.dodge_speed_bonus = 0.0
        self.inventory = None
        self.buffs = []      # {"kind","value","duration"} (+ опц. "orig_duration")
        self.talent_effects = []   # активные капстоуны/узлы Древа
        self.death_save_used = False
        self.facing = Vector2(1, 0)
        self.ng_modifiers = set()
        self.aura_slow_mult = 1.0          # аура демона-владыки (п.11)
        self.fear_dir = None               # направление паники тёмного мага
        self.fear_timer = 0.0
        self.blocking = False
        self._blood_thirst_active = False

    # ---------- производные ----------
    @property
    def max_hp(self):
        return self.stats_obj.max_hp(self.perks, self.runes)

    @property
    def max_mana(self):
        return self.stats_obj.max_mana(self.perks, self.runes)

    @property
    def max_stamina(self):
        return self.stats_obj.max_stamina(self.perks, self.runes)

    def damage(self):
        return self.stats_obj.base_damage(self.perks, self.runes) * (1 + self._buff("damage"))

    def attack_speed(self):
        v = self.stats_obj.attack_speed(self.perks, self.runes)
        if getattr(self, "_blood_thirst_active", False):
            v *= 1.25   # узел Крови 4: +25% при HP < 30%
        return v

    def crit_chance(self):
        from ..core.constants import TILE
        c = 0.05 + _sum_effect(self.perks, self.runes, "crit_chance")
        return c

    def freeze_chance(self):
        return _sum_effect(self.perks, self.runes, "freeze_chance")

    def _buff(self, kind):
        return sum(b["value"] for b in self.buffs if b["kind"] == kind)

    # ---------- main update (п.16.4) ----------
    def update(self, dt, raw_input, world):
        # таймер инверсии обновляется в update_player, НЕ в process_input
        if self.control_inverted_timer > 0:
            self.control_inverted_timer -= dt
        if self.brittle_duration > 0:
            self.brittle_duration = max(0.0, self.brittle_duration - dt)
        for b in list(self.buffs):
            b["duration"] -= dt
            if b["duration"] <= 0:
                self.buffs.remove(b)
        # реген стамины с задержкой 1 сек после действия
        self.stamina_regen_delay = max(0.0, self.stamina_regen_delay - dt)
        if self.stamina_regen_delay <= 0 and self.sm.state != PlayerState.DEAD:
            self.stamina = min(self.max_stamina,
                               self.stamina + self.stats_obj.stamina_regen(self.perks, self.runes) * dt)
            if self._out_of_combat(world):
                self.stamina = min(self.max_stamina, self.stamina + 2 * dt)
        self.mana = min(self.max_mana,
                        self.mana + self.stats_obj.mana_regen(self.perks, self.runes) * dt)
        # реген HP вне боя (капстоун Плоть-8)
        if any(t == "regen_ooc" for t in self.talent_effects) and self._out_of_combat(world):
            self.hp = min(self.max_hp, self.hp + 1 * dt)
        # heal over time от зелий (hot: value — общий объём лечения)
        for b in list(self.buffs):
            if b["kind"] == "hot":
                orig = b.get("orig_duration") or b.get("duration", 1.0) or 1.0
                self.hp = min(self.max_hp, self.hp + b["value"] / orig * dt)
        move = process_input(raw_input, self)
        # страх тёмного мага: бежим в random-направлении, команды WASD игнорируются
        if self.fear_timer > 0:
            self.fear_timer -= dt
            move = self.fear_dir.copy() if self.fear_dir else Vector2(0, 0)
        self.sm.update(dt, {"move": move, "world": world, "dt": dt})
        # действия из Input Layer (п.2, п.16): ЛКМ/ПКМ-удержание, Q/E, Shift
        if raw_input is not None and world is not None:
            self._handle_actions(raw_input, world)
        self.update_status(dt, world)
        # движение
        if self.sm.state in (PlayerState.IDLE, PlayerState.MOVE, PlayerState.DODGE):
            speed = self.speed * getattr(self, "aura_slow_mult", 1.0)
            if self.sm.state == PlayerState.DODGE:
                speed = 14.0 * (1 + self.dodge_speed_bonus)
            if self.status.slow_pct:
                speed *= 1 - self.status.slow_pct
            anomaly = world.anomalies.player_mods(self.pos.as_tuple()) if world else \
                {"drift": Vector2(0, 0)}
            vel = move.normalized() * speed + anomaly["drift"]
            new_pos = self.pos + vel * dt
            if world is None or not world.is_wall(int(new_pos.x), int(new_pos.y)):
                self.pos = new_pos
        if self.sm.state == PlayerState.MOVE and raw_input.running:
            cost = C.COST_RUN * dt * (world.anomalies.player_mods(self.pos.as_tuple())
                                      ["stamina_cost_mult"] if world else 1)
            self.try_spend_stamina(cost)

    def _out_of_combat(self, world):
        if world is None:
            return True
        return all(e.distance_to(self) > 12 for e in world.enemies() if e.alive)

    def _handle_actions(self, raw_input, world):
        """События нажатия/отпускания → PlayerStateMachine.queue (п.16.3)."""
        ri = raw_input
        if ri.was_pressed("attack_light"):
            self.sm.queue("attack_light")
        if ri.was_pressed("attack_heavy"):
            self.sm.queue("attack_heavy_start")
        if "attack_heavy" in getattr(ri, "released", ()):
            self.sm.release_heavy(world)
        if ri.was_pressed("dash"):
            self.sm.queue("dodge")
        if ri.was_pressed("cast_fire"):
            self.sm.queue("cast_fire")
        if ri.was_pressed("cast_ice"):
            self.sm.queue("cast_ice")

    # ---------- ресурсы ----------
    def try_spend_stamina(self, amount):
        if self.stamina >= amount:
            self.stamina -= amount
            self.stamina_regen_delay = C.STAMINA_REGEN_DELAY
            return True
        return False

    def try_spend_mana(self, amount):
        discount = 0.9 if "cast_cost_minus" in self.talent_effects else 1.0
        amount *= discount
        if self.mana >= amount:
            self.mana -= amount
            return True
        return False

    def take_damage(self, amount):
        if self.sm.state == PlayerState.DODGE:
            return 0  # i-frames рывка
        evasion = _sum_effect(self.perks, self.runes, "evasion")
        if random.random() < evasion:
            return 0
        taken = amount * (1 + self._buff("damage_taken"))
        if "glass_cannon" in getattr(self, "ng_modifiers", set()):
            taken *= 2.0
        blocked = getattr(self, "blocking", False)
        if blocked:
            if self.try_spend_stamina(C.COST_BLOCK):
                taken *= 0.3
            else:
                blocked = False
        dmg = super().take_damage(taken)
        if dmg > 0 and self.hp <= 0:
            # Капстоун «Плоть»: один раз за забег 30% HP
            if ("flesh_deathsave" in self.talent_effects and not self.death_save_used):
                self.death_save_used = True
                self.hp = self.max_hp * 0.3
                return dmg
            self.sm.change(PlayerState.DEAD)
        elif dmg > 0 and self.hp < self.max_hp * 0.3 and "blood_thirst" in self.talent_effects:
            # узел Крови 4: +25% скорости атаки при HP < 30%
            self._blood_thirst_active = True
        else:
            self._blood_thirst_active = False
        return dmg

    def on_kill(self, victim, method, world):
        c = self.stats_obj.counters
        c[f"kills_{method}"] = c.get(f"kills_{method}", 0) + 1
        if method == "sword" and victim.status.has("burn"):
            c["kills_while_burning"] += 1
        if victim.status.frozen and method == "sword":
            c["frozen_shattered"] += 1
        if method == "steam":
            c["kills_steam"] += 1
        if getattr(victim, "hp_ratio", 1.0) < 0.1:
            c["low_hp_executions"] += 1

    @property
    def hp_ratio(self):
        return self.hp / max(1, self.max_hp)


class PlayerStateMachine(StateMachine):
    """Стейт-машина игрока по таблице прерываний (п.16.3)."""

    LIGHT_DURATION = 0.35
    HEAVY_CHARGE_MIN = 0.4
    HEAVY_DURATION = 0.6
    DODGE_DURATION = 0.3
    CAST_DURATION = 0.45
    BUFFER_WINDOW = 0.3

    def __init__(self, player):
        super().__init__(PlayerState.IDLE)
        self.p = player
        self.action = None       # ('attack_light'|'attack_heavy'|'cast_fire'|...)
        self.hit_done = False
        self.can_cancel = True

    def queue(self, action):
        """Вход из Input Layer: проверяет таблицу прерываний."""
        table = INTERRUPT_TABLE[self.state]
        kind = "dodge" if action == "dodge" else (
            "cast" if action.startswith("cast") else "attack")
        rule = table.get(kind, "no")
        if rule == "now":
            self._start(action)
        elif rule == "after50" and self.state_time > self.LIGHT_DURATION * 0.5:
            self._start(action)
        elif rule == "buffer":
            self.p.input_buffer = action
            self.p.buffer_timer = self.BUFFER_WINDOW

    def _start(self, action):
        self.action = action
        self.hit_done = False
        if action == "dodge":
            mult = 1.0
            if self.p.economy and "mods" in dir(self.p.economy):
                pass
            cost = self.p.stats_obj.action_cost("dodge", self.p.perks, self.p.runes)
            if not self.p.try_spend_stamina(cost):
                return
            self.change(PlayerState.DODGE)
            self.set_timer("dodge", self.DODGE_DURATION)
        elif action == "attack_light":
            if not self.p.try_spend_stamina(
                    self.p.stats_obj.action_cost("light", self.p.perks, self.p.runes)):
                return
            self.change(PlayerState.ATTACK_LIGHT)
            self.set_timer("atk", self.LIGHT_DURATION / max(0.5, self.p.attack_speed()))
        elif action == "attack_heavy_start":
            self.change(PlayerState.ATTACK_HEAVY)
            self.p.heavy_charge = 0.0
        elif action.startswith("cast_fire"):
            if not self.p.try_spend_mana(C.FIRE_COST):
                return
            self.change(PlayerState.CASTING)
            self.set_timer("cast", self.CAST_DURATION)
        elif action.startswith("cast_ice"):
            if not self.p.try_spend_mana(C.ICE_COST):
                return
            self.change(PlayerState.CASTING)
            self.set_timer("cast", self.CAST_DURATION)

    def release_heavy(self, world):
        if self.state == PlayerState.ATTACK_HEAVY:
            charged = self.p.heavy_charge >= self.HEAVY_CHARGE_MIN
            cost = self.p.stats_obj.action_cost("heavy", self.p.perks, self.p.runes)
            if charged and self.p.try_spend_stamina(cost):
                self.hit_done = False
                self.action = "attack_heavy"
                self.execute_hit(world)
            self.change(PlayerState.IDLE)

    def execute_hit(self, world):
        if self.hit_done:
            return
        self.hit_done = True
        world.player_attack(self.p, self.action)

    def check_transitions(self, ctx):
        world = ctx.get("world")
        st = self.state
        if st == PlayerState.DODGE and self.timer_ready("dodge"):
            self.change(PlayerState.IDLE)
        elif st == PlayerState.ATTACK_LIGHT:
            if self.state_time > self.LIGHT_DURATION * 0.4:
                self.execute_hit(world)
            if self.timer_ready("atk"):
                self._flush_buffer()
                self.change(PlayerState.IDLE)
        elif st == PlayerState.ATTACK_HEAVY:
            self.p.heavy_charge += ctx["dt"] if "dt" in ctx else 0.016
            if self.p.heavy_charge >= 1.2 and not self.hit_done:
                self.release_heavy(world)   # авто-спуск при полном заряде
        elif st == PlayerState.CASTING:
            if self.timer_ready("cast"):
                self.execute_hit(world)
                self.change(PlayerState.IDLE)
        elif st == PlayerState.STUNNED and self.timer_ready("stun"):
            self.change(PlayerState.IDLE)
        if self.p.buffer_timer > 0:
            self.p.buffer_timer -= ctx.get("dt", 0.016)
            if self.p.buffer_timer <= 0:
                self.p.input_buffer = None

    def _flush_buffer(self):
        if self.p.input_buffer:
            act = self.p.input_buffer
            self.p.input_buffer = None
            self._start(act)

    def stun(self, duration):
        self.change(PlayerState.STUNNED)
        self.set_timer("stun", duration)


def process_input(raw_input, player):
    """Input Layer (п.16.4): WASD-вектор + инверсия только движения, мышь не трогаем."""
    move = Vector2(0, 0)
    if raw_input.forward: move.y -= 1
    if raw_input.back:    move.y += 1
    if raw_input.left:    move.x -= 1
    if raw_input.right:   move.x += 1
    if player.control_inverted_timer > 0:
        move.x = -move.x
        move.y = -move.y
    # камера/прицел — не инвертируются
    player.aim_direction = Vector2.from_angle(raw_input.camera_yaw)
    if move.length() > 0:
        player.facing = move.normalized()
        if player.sm.state == PlayerState.IDLE:
            player.sm.change(PlayerState.MOVE)
    elif player.sm.state == PlayerState.MOVE:
        player.sm.change(PlayerState.IDLE)
    return move
