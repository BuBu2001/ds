"""World Layer: связывает все 9 слоёв логики ТЗ п.21.2 в один игровой цикл.

Генерирует данж, спавнит мобы/элиток/магов/босса, обрабатывает бой
(меч/огонь/лёд + комбо п.8.2), смерть и призрака (п.10), костры (п.5),
лужи/пар/снаряды/аномалии, дроп валют и материалов (п.3, 17).
Headless-совместим: не требует pygame (рендер — отдельный слой UI/Engine).
"""
import math
import random
from ..core import constants as C
from ..core.math_utils import Vector2
from ..entities.base import Projectile, IcePuddle, SteamCloud, SpikeTrap, on_player_enter_puddle
from ..entities.mobs import Mob, MOB_TABLE, mobs_for_level
from ..entities.elites import ELITE_BY_MOB
from ..entities.mages import make_mage
from ..entities.player import Player, PlayerStats, PlayerState
from ..economy.currency import Economy, Wallet
from ..economy.crafting import Inventory, Crafter
from ..magic.combos import sword_hit, fire_hit, ice_hit
from ..magic.runes import RuneSystem
from ..magic.perks import PerkSystem
from ..magic.anomalies import AnomalyManager, GravityAnomaly, AnomalyType
from ..generation.dungeon import DungeonGenerator
from ..bosses import boss_for_level
from ..data import loader


class Campfire:
    """Костёр в данже (п.5): отдых, сохранение, крафт, руны, прокачка."""

    def __init__(self, pos, index):
        self.pos = Vector2(*pos) if not isinstance(pos, Vector2) else pos
        self.index = index
        self.activated = False
        self.rests_left = C.REST_LIMIT_BASE
        self.threat_stacks = 0
        self.notes_shown = False
        self._closed = True   # экран костра: открыт/закрыт (для паузы в app)

    def can_rest(self):
        return self.rests_left > 0

    def rest(self, player, rune_system=None):
        if not self.can_rest():
            return False
        self.rests_left -= 1
        self.threat_stacks += 1
        player.hp = min(player.max_hp, player.hp + player.max_hp * 0.5)
        player.mana = min(player.max_mana, player.mana + player.max_mana * 0.5)
        # временные руны слетают при отдыхе (п.9.1)
        if rune_system:
            rune_system.clear_temporary()
        # перк «Без костра» (+15% HP/маны) сгорает при первом отдыхе за забег (п.7)
        if player.perks is not None:
            player.perks.burn_on_rest(player.stats_obj.counters)
        return True


class Ghost:
    """Пепельный призрак (п.10): хранит потерянные угли на месте смерти."""

    def __init__(self, pos, coal):
        self.pos = pos.copy() if isinstance(pos, Vector2) else Vector2(*pos)
        self.coal = coal


class World:
    def __init__(self, meta, level=1, ng_cycle=0, modifiers=(), seed=None):
        self.meta = meta
        self.rng = random.Random(seed)
        self.level = level
        self.ng_cycle = ng_cycle
        self.modifiers = set(modifiers)
        self.economy = Economy(meta=meta, modifiers=self.modifiers)
        self.wallet = Wallet()
        self.perksystem = PerkSystem(rng=self.rng)
        # в сохранении могут остаться id перков/трофеев из более старой версии данных — фильтруем
        self.perksystem.unlocked |= {p for p in meta.unlocked_perks if p in self.perksystem.defs}
        self.rune_system = RuneSystem(self.wallet, rng=self.rng)
        trophy_ids = {r.get("trophy") for r in loader.runes().values() if r.get("trophy")}
        self.rune_system.trophies |= {t for t in meta.trophies if t in trophy_ids}
        self.inventory = Inventory(slots=meta.inventory_slots)
        self.crafter = Crafter(self.wallet, rng=self.rng)

        # --- генерация (п.14) ---
        gen = DungeonGenerator(rng=self.rng)
        self.data = gen.generate(level)
        self.grid = self.data.grid

        # --- игрок ---
        stats = PlayerStats(meta=meta.as_dict_for_player())
        start_perks = self._starting_perk_defs()
        # руны, уже наложенные в убежище (мета-постоянные), переносим в забег
        carried_runes = [dict(r) for r in self.rune_system.active()]
        self.player = Player(Vector2(*self.data.entrance), self.economy,
                             stats=stats, perks=start_perks, runes=carried_runes)
        self.player.wallet = self.wallet
        self.player.inventory = self.inventory
        self.player.rune_system = self.rune_system
        self.player.ng_modifiers = self.modifiers
        self.player.stats_obj.counters["deaths"] = meta.total_deaths

        # --- содержимое уровня ---
        self.enemies_list = []
        self.projectiles = []
        self.puddles = []
        self.steam_clouds = []
        self.traps = []
        self.objects = []          # тотемы/фонари/копии — не «враги» для LOD
        self.campfires = [Campfire(p, i) for i, p in enumerate(self.data.campfires)]
        self.last_campfire = None
        self.ghost = None
        self.boss = None
        self.boss_defeated = False
        self.exit_pos = Vector2(*self.data.exit_pos)
        self.lava_margin = 0
        self.threat_stacks = 0
        self.used_rest_this_run = False
        self.damage_taken_this_dungeon = 0.0
        self.kills_this_dungeon = 0
        self.sword_only = True
        self.anomalies = AnomalyManager(level, modifiers=self.modifiers, rng=self.rng)
        for zp in self.data.gravity_zones:
            self.anomalies.add_local_zone(zp)
        self.wall_runes_remaining = list(self.data.wall_runes)
        self.float_texts = []
        self.events = []           # журнал для UI (открытия перков, лор)
        self._death_done = False
        self._boss_loot_done = False

        self._spawn_all()
        # применяем эффекты Древа Талантов к игроку сразу после спавна
        self._apply_talents()
        # ссылка на систему перков для спец-эффектов (сгорание «Без костра» при отдыхе, п.7)
        self.player.perksystem = self.perksystem

    # ---------- начальная сборка ----------
    def _starting_perk_defs(self):
        defs = []
        for pid in list(self.perksystem.unlocked)[:3]:
            d = dict(self.perksystem.defs[pid])
            defs.append(d)
        if self.meta.start_perk and self.meta.start_perk in self.perksystem.defs:
            defs.append(dict(self.perksystem.defs[self.meta.start_perk]))
        return defs

    def _apply_talents(self):
        """Эффекты Древа Талантов (п.6.2): флэты в PlayerStats.meta, спец-ключи — в talent_effects."""
        effs, specials = self.meta.talents.aggregate_effects()
        pm = self.player.stats_obj.meta
        for k, v in effs.items():
            if k.endswith("_flat"):
                base = {"max_hp_flat": "hp", "max_mana_flat": "mana",
                        "max_stamina_flat": "stamina"}[k]
                pm[base] = pm.get(base, 0) + int(v)
        self.player.talent_effects = list(specials)
        self.talent_rest_bonus = int(effs.get("rest_charge_bonus", 0))
        for cf in self.campfires:
            cf.rests_left += self.talent_rest_bonus
        self._talent_effs = effs

    def _ng_mults(self):
        cycle = self.ng_cycle
        if cycle <= 0:
            return 1.0, 1.0
        table_hp = {1: 1.5, 2: 2.0, 3: 2.8, 4: 3.5}
        table_dmg = {1: 1.3, 2: 1.6, 3: 2.0, 4: 2.5}
        hp = table_hp.get(cycle, 3.5 + 0.7 * (cycle - 4))
        dmg = table_dmg.get(cycle, 2.5 + 0.4 * (cycle - 4))
        if "blood_moon" in self.modifiers:
            hp *= 1.5
        return hp, dmg

    def _spawn_all(self):
        hp_m, dmg_m = self._ng_mults()
        pool = mobs_for_level(self.level, self.rng)
        for pos in self.data.mob_spawns:
            mid = self.rng.choice(pool)
            grp = MOB_TABLE[mid].get("group")
            n = self.rng.randint(*grp) if grp else 1
            for i in range(n):
                off = Vector2(self.rng.uniform(-1, 1), self.rng.uniform(-1, 1))
                m = Mob(mid, Vector2(*pos) + off, ng_hp_mult=hp_m,
                        ng_dmg_mult=dmg_m, threat_stacks=self.threat_stacks,
                        modifiers=self.modifiers)
                self.enemies_list.append(m)
        elite_ids = ("goblin", "skeleton", "spider", "mutant")
        for pos in self.data.elite_spawns:
            base = self.rng.choice([i for i in elite_ids
                                    if MOB_TABLE[i]["tiers"][0] <= self.level
                                    <= MOB_TABLE[i]["tiers"][1]] or ["goblin"])
            cls = ELITE_BY_MOB.get(base)
            e = cls(base, Vector2(*pos), ng_hp_mult=hp_m, ng_dmg_mult=dmg_m,
                    threat_stacks=self.threat_stacks) if cls else \
                Mob(base, Vector2(*pos), is_elite=True, ng_hp_mult=hp_m,
                    ng_dmg_mult=dmg_m, modifiers=self.modifiers)
            e.is_elite = True
            self.enemies_list.append(e)
        if self.level >= 6:
            for pos in self.data.mage_spawns:
                mg = make_mage(Vector2(*pos), rng=self.rng, modifiers=self.modifiers,
                               ng_dmg_mult=dmg_m, threat=self.threat_stacks)
                self.enemies_list.append(mg)
        if self.level >= 6:
            for pos in self.data.trap_spawns:
                self.traps.append(SpikeTrap(Vector2(*pos)))
        # босс на 5/10/15/20 уровнях
        if self.level in (5, 10, 15, 20):
            self.spawn_boss()

    def spawn_boss(self):
        hp_m, dmg_m = self._ng_mults()
        b = boss_for_level(self.level, Vector2(*self.data.boss_room_center),
                           mech_points=self.data.mechanic_points,
                           ng_hp_mult=hp_m, ng_dmg_mult=dmg_m,
                           threat_stacks=self.threat_stacks,
                           first_kill=True, rng=self.rng)
        if b is None:
            return
        # первое ли это убийство этого босса (глобально, через мета-прогресс)
        b.first_kill = self._boss_uid(b) not in self.meta.bosses_first_kill
        self.boss = b
        if hasattr(b, "spawn_totems"):
            b.spawn_totems(self)
        if hasattr(b, "spawn_lanterns"):
            b.spawn_lanterns(self)
        self.enemies_list.append(b)

    def _boss_uid(self, boss):
        """Уникальный id первого убийства: id босса + уровень-врата."""
        return f"{boss.boss_id}_L{boss.level_gate}" if boss else ""

    # ---------- базовые запросы ----------
    def is_wall(self, x, y):
        if 0 <= y < len(self.grid) and 0 <= x < len(self.grid[0]):
            return self.grid[y][x] == 1
        return True

    def enemies(self):
        return [e for e in self.enemies_list if e.alive]

    def has_los(self, a, b):
        """Bresenham по сетке: LOS пока луч не режет стену."""
        x0, y0 = int(a[0]), int(a[1])
        x1, y1 = int(b[0]), int(b[1])
        dx, dy = abs(x1 - x0), abs(y1 - y0)
        sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
        err = dx - dy
        while True:
            if self.is_wall(x0, y0):
                return False
            if x0 == x1 and y0 == y1:
                return True
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x0 += sx
            if e2 < dx:
                err += dx
                y0 += sy

    def move_entity(self, ent, target_pos, dt, speed=None):
        to = target_pos - ent.pos
        d = to.length()
        if d < 0.4:
            return
        sp = (speed or ent.speed) * (1 - ent.status.slow_pct)
        new = ent.pos + to.normalized() * min(sp * dt, d)
        if not self.is_wall(int(new.x), int(new.y)):
            ent.pos = new

    def spawn_object(self, obj):
        self.objects.append(obj)

    def spawn_float_text(self, pos, text):
        self.float_texts.append({"pos": pos.copy(), "text": text, "t": 1.5})

    # ---------- главный тик ----------
    def update(self, dt, raw_input):
        p = self.player
        if p.sm.state != PlayerState.DEAD:
            p.update(dt, raw_input, self)
        self.anomalies.update(dt)
        # лужи: инверсия игрока (п.12.2)
        for pd in list(self.puddles):
            if not pd.update(dt):
                self.puddles.remove(pd)
                continue
            if pd.contains(p.pos):
                on_player_enter_puddle(p, pd)
        # пар
        for sc in list(self.steam_clouds):
            if not sc.update(dt):
                self.steam_clouds.remove(sc)
                continue
            for e in self.enemies():
                if id(e) not in sc.applied and e.pos.distance_to(sc.pos) <= sc.radius:
                    sc.applied.add(id(e))
                    e.take_damage(sc.damage)
                    e.status.apply("accuracy_down", C.STEAM_DURATION)
                    if "steam_capstone" in getattr(p, "talent_effects", []):
                        e.status.apply("stun", 0.5)
        # снаряды
        for pr in list(self.projectiles):
            anom = self.anomalies.anomaly_at(pr.pos.as_tuple())
            pr.update(dt, anom, self)
            if pr.source == "enemy":
                if pr.pos.distance_to(p.pos) < 0.6:
                    pr.dead = True
                    self._impact_enemy_projectile(pr)
            else:
                for e in self.enemies() + self.objects:
                    if e.alive and pr.pos.distance_to(e.pos) < e.radius + 0.4:
                        pr.dead = True
                        self.on_projectile_impact(pr, target=e)
                        break
            if pr.dead:
                self.projectiles.remove(pr)
        # враги (LOD: маги/боссы 30 FPS — аккумулируем半步)
        for e in list(self.enemies_list):
            if not e.alive:
                continue
            if getattr(e, "is_boss", False) or e.kind.startswith("mage"):
                e._lod_acc = getattr(e, "_lod_acc", 0.0) + dt
                if e._lod_acc < 1 / 30:
                    continue
                dt_e, e._lod_acc = e._lod_acc, 0.0
                e.update(dt_e, self)
            else:
                e.update(dt, self)
        for o in list(self.objects):
            if hasattr(o, "update") and getattr(o, "alive", True) and o.kind in (
                    "true_reflection", "fake_reflection"):
                o.update(dt, self)
        # ловушки
        for tr in self.traps:
            tr.update(dt)
            if tr.try_trigger(p.pos):
                self.damage_player(tr.damage, kind="trap")
        # аура элиток (модификатор NG+)
        if "elite_aura" in self.modifiers:
            params = loader.modifiers()["elite_aura"]["params"]
            for e in self.enemies():
                if getattr(e, "is_elite", False):
                    for a in self.enemies():
                        if a is not e and a.hp_ratio < 1.0 and \
                                e.pos.distance_to(a.pos) < params["radius"]:
                            a.heal(a.max_hp * params["heal_pct"] * dt)
        # взрывные трупы обработаны в on_enemy_death
        for ft in list(self.float_texts):
            ft["t"] -= dt
            if ft["t"] <= 0:
                self.float_texts.remove(ft)
        # смерть игрока
        if p.hp <= 0 and p.sm.state == PlayerState.DEAD and not getattr(self, "_death_done", False):
            self.on_player_death()

    # ---------- атаки игрока ----------
    def player_attack(self, player, action):
        if action in ("attack_light", "attack_heavy"):
            self._melee_sweep(player, heavy=(action == "attack_heavy"))
        elif action == "cast_fire":
            self._player_cast(player, "fire")
        elif action == "cast_ice":
            self._player_cast(player, "ice")

    def _melee_sweep(self, player, heavy=False):
        reach = 2.2 if heavy else 1.8
        arc = math.radians(140 if heavy else 100)
        facing = player.facing
        targets = [e for e in self.enemies() + self.objects
                   if getattr(e, "alive", True) and e is not player
                   and player.pos.distance_to(e.pos) <= reach + e.radius]
        base = player.damage() * (1.8 if heavy else 1.0)
        if heavy and "steel_execution" in getattr(player, "talent_effects", []):
            for t in targets:
                if t.alive and not getattr(t, "is_boss", False) and \
                        getattr(t, "hp_ratio", 1) < 0.2 and self.rng.random() < 0.2:
                    t.take_damage(t.hp)
                    self.spawn_float_text(t.pos, "КАЗНЬ!")
                    targets.remove(t)
        hit_any = False
        for t in targets:
            to_t = (t.pos - player.pos)
            if to_t.length() > 1e-6:
                dot = to_t.normalized().dot(facing) if hasattr(to_t, "dot") else \
                    (to_t.x * facing.x + to_t.y * facing.y)
                if dot < math.cos(arc):
                    continue
            stats_ctx = {"crit_chance": player.crit_chance(),
                         "combo_bonus": self._combo_frozen_bonus(player)}
            res = sword_hit(t, base, stats=stats_ctx)
            dealt = t.take_damage(res["damage"], damage_type="physical")
            hit_any = True
            if res["crit"]:
                self.spawn_float_text(t.pos, "КРИТ!" if not res["shatter"] else "РАЗЛОМ!")
            if res["shatter"]:
                player.stats_obj.counters["frozen_shattered"] += 1
            # стамина за комбо-удар по замороженному (п.4)
            if t.status.frozen or res["shatter"]:
                player.try_spend_stamina(C.COST_COMBO_FROZEN)
            if dealt > 0 and t.alive is False:
                self.on_enemy_death(t, method="sword")
            if getattr(t, "kind", "") in ("totem", "lantern") and not t.alive:
                self._on_mech_death(t)
        if heavy and self.boss and self.boss.alive:
            self.boss.note_player_attack("sword") if hasattr(self.boss, "note_player_attack") else None
        if hit_any:
            player.stats_obj.counters["kills_sword"] += 0  # счётчик убийств — в on_enemy_death
        self._apply_rune_on_attack(player, targets)

    def _combo_frozen_bonus(self, player):
        bonus = 0.5 if "combo_bonus" in str(getattr(player, "talent_effects", [])) else 0.0
        return bonus

    def _apply_rune_on_attack(self, player, targets):
        t0 = next((t for t in targets if getattr(t, "alive", True)), None)
        if t0:
            self.rune_system.on_attack(player, t0, self)

    def _player_cast(self, player, element):
        origin = player.pos + player.aim_direction * 0.6
        if element == "fire":
            proj = Projectile(origin, player.aim_direction * 12.0,
                              damage=25 * (1 + self._elem_bonus(player, "fire")),
                              kind="fire", source="player", aoe_radius=1.5,
                              effect={"burn": True})
        else:
            proj = Projectile(origin, player.aim_direction * 16.0,
                              damage=18 * (1 + self._elem_bonus(player, "ice")),
                              kind="spike", source="player", always_straight=True,
                              effect={"freeze": True})
        self.projectiles.append(proj)
        if element == "fire":
            self.sword_only = False
        else:
            self.sword_only = False

    def _elem_bonus(self, player, kind):
        tot = 0.0
        for src in (player.perks or []) + (player.runes or []):
            tot += src.get("effects", {}).get(f"{kind}_damage", 0.0)
        for t in getattr(player, "talents_effect_map", {}).items() if False else []:
            pass
        return tot

    # ---------- попадания снарядов ----------
    def on_projectile_impact(self, proj, target=None):
        if proj.source == "player":
            if target is not None:
                self._hit_enemy_with_projectile(proj, target)
        else:
            # взрыв файербола мага: АОЕ 3м
            if proj.kind == "fireball":
                for e in self.enemies() + [self.player]:
                    if e.pos.distance_to(proj.pos) <= 3.0:
                        self.damage_player(proj.damage, kind="fire")
                        break
            elif target is None:
                self.damage_player(proj.damage, kind=proj.kind)

    def _hit_enemy_with_projectile(self, proj, target):
        if proj.kind == "fire":
            res = fire_hit(target, proj.damage, stats=self._fire_stats())
            target.take_damage(res["damage"], damage_type="fire")
            if res["steam"]:
                self.spawn_steam(target.pos, C.STEAM_RADIUS, res["steam_damage"])
        elif proj.kind == "spike":
            res = ice_hit(target, proj.damage, freeze_chance=self.player.freeze_chance(),
                          stats=self._ice_stats())
            target.take_damage(res["damage"], damage_type="ice")
            if "freezes" in res.get("stats_delta", {}) or res["effects"] and "Заморозка" in res["effects"]:
                self.player.stats_obj.counters["freezes"] += 1
                if self.anomalies.enabled and self.anomalies.anomaly_at(target.pos.as_tuple()).kind != AnomalyType.NONE:
                    self.player.stats_obj.counters["freezes_anomaly"] += 1
        if not target.alive:
            method = "fire" if proj.kind == "fire" else "ice"
            self.on_enemy_death(target, method=method)
            if getattr(target, "kind", "") in ("totem", "lantern"):
                self._on_mech_death(target)

    def _fire_stats(self):
        p = self.player
        extra = 1 if "burn_extra_stacks" in str(getattr(p, "talent_effects", [])) else 0
        return {"burn_extra_stacks": extra,
                "fire_damage": sum(s.get("effects", {}).get("fire_damage", 0)
                                   for s in (p.perks or []))}

    def _ice_stats(self):
        p = self.player
        return {"freeze_bonus": p.freeze_chance(),
                "freezes": p.stats_obj.counters["freezes"]}

    def spawn_steam(self, pos, radius, damage, duration=C.STEAM_DURATION):
        self.steam_clouds.append(SteamCloud(pos, radius, damage, duration))

    def enemy_cast_fire(self, caster, player, damage):
        dirv = (player.pos - caster.pos).normalized()
        self.projectiles.append(Projectile(caster.pos.copy(), dirv * 10,
                                           damage, kind="fireball", source="enemy",
                                           aoe_radius=3.0))

    def enemy_cast_ice(self, caster, player, damage):
        dirv = (player.pos - caster.pos).normalized()
        self.projectiles.append(Projectile(caster.pos.copy(), dirv * 14,
                                           damage, kind="spike", source="enemy",
                                           always_straight=True))

    def enemy_cast_steam(self, caster, player, damage):
        self.spawn_steam(player.pos, 2.5, damage)

    def spawn_twisted_bolt(self, boss, player):
        dirv = (player.pos - boss.pos).normalized()
        self.projectiles.append(Projectile(boss.pos.copy(), dirv * 9,
                                           boss.damage, kind="fireball",
                                           source="enemy", aoe_radius=2.5))

    def spawn_enemy_projectile(self, mob, kind):
        p = self.player
        dirv = (p.pos - mob.pos).normalized()
        self.projectiles.append(Projectile(mob.pos.copy(), dirv * 12,
                                           mob.damage, kind="beam", source="enemy",
                                           ignore_gravity=True))

    def spawn_enemy_projectile_from(self, mage, kind, dirv, damage, aoe=0.0, slow=False):
        eff = {"slow": 3.0} if slow else {}
        self.projectiles.append(Projectile(mage.pos.copy(), dirv * 11, damage,
                                           kind=kind, source="enemy",
                                           aoe_radius=aoe, effect=eff))

    def force_gravity_flip(self):
        """Босс меняет гравитацию — форсируем глобальную аномалию сейчас."""
        kind = self.rng.choice(AnomalyManager.GLOBAL_KINDS)
        self.anomalies.global_anomaly = GravityAnomaly(kind)
        self.anomalies.global_anomaly.duration = C.ANOMALY_GLOBAL_DURATION

    def set_lava_margin(self, margin):
        """Фаза 3 Сердца: лава сужает арену — края становятся стенами."""
        self.lava_margin = margin
        h, w = len(self.grid), len(self.grid[0])
        cx, cy = self.data.boss_room_center
        box = (max(0, cx - 12 + margin), max(0, cy - 12 + margin),
               min(w, cx + 12 - margin), min(h, cy + 12 - margin))
        self.lava_box = box
        p = self.player
        if not (box[0] <= p.pos.x <= box[2] and box[1] <= p.pos.y <= box[3]):
            self.damage_player(30, kind="lava", unreachable=True)

    # ---------- урон игроку ----------
    def damage_player(self, amount, kind="melee", source=None, unreachable=False):
        p = self.player
        resist = 0.0
        if kind == "fire":
            resist = self._talent_resist("fire_resist")
        elif kind == "ice":
            resist = self._talent_resist("ice_resist")
        acc = 0.0
        mult = 1.0
        if source is not None and getattr(source, "status", None):
            acc = source.status.accuracy_debuff
        if self.rng.random() < acc:
            return 0   # промах из-за пара
        before = p.hp
        dealt = p.take_damage(amount * (1 - resist))
        if unreachable:
            p.hp = 0
            dealt = before
            self._teleport_loss = True
        self.damage_taken_this_dungeon += dealt
        return dealt

    # совместимость с сигнатурой боссов: deal_damage_to_player(amount, source=..., kind=...)
    def deal_damage_to_player(self, amount, source=None, kind="melee"):
        return self.damage_player(amount, kind=kind, source=source)

    def _talent_resist(self, key):
        effs, _ = self.meta.talents.aggregate_effects()
        return min(0.75, effs.get(key, 0.0))

    def inflict_fear(self, player):
        """Страх тёмного мага: бежит 2 сек в случайном направлении (п.12.3)."""
        ang = self.rng.uniform(0, 6.28)
        player.fear_dir = Vector2.from_angle(ang)
        player.fear_timer = 2.0
        player.sm.stun(0.0)  # страх ≠ стан; движение задаётся через fear_dir в input
        self.spawn_float_text(player.pos, "СТРАХ!")

    def on_thaw(self, entity):
        pass

    def on_mage_interrupted(self, mage):
        self.player.stats_obj.counters["mages_interrupted"] += 1

    def summon_minions(self, boss, count, mob_id):
        hp_m, dmg_m = self._ng_mults()
        for i in range(count):
            off = Vector2(self.rng.uniform(-2, 2), self.rng.uniform(-2, 2))
            m = Mob(mob_id, boss.pos + off, ng_hp_mult=hp_m, ng_dmg_mult=dmg_m,
                    modifiers=self.modifiers)
            m.summoned_by = boss
            boss.summons.append(m)
            self.enemies_list.append(m)

    # ---------- смерти ----------
    def on_enemy_death(self, enemy, by_burn=False, method=None):
        if getattr(enemy, "_death_processed", False):
            return
        enemy._death_processed = True
        p = self.player
        self.kills_this_dungeon += 1
        if not by_burn:
            p.on_kill(enemy, method or "sword", self)
        else:
            p.on_kill(enemy, "fire", self)
        if enemy.kind.startswith("mage"):
            p.stats_obj.counters["kills_ice" if method == "ice" else
                                  ("kills_fire" if method == "fire" else "kills_sword")] += 0
        # взрывные трупы (модификатор) + мутант (п.11.1)
        boom = 0
        if "explosive_corpses" in self.modifiers and not getattr(enemy, "is_boss", False):
            boom = loader.modifiers()["explosive_corpses"]["params"]["damage"]
            radius = loader.modifiers()["explosive_corpses"]["params"]["radius"]
        if getattr(enemy, "explode_damage", 0):
            boom, radius = enemy.explode_damage, 2.0
        if boom:
            if p.pos.distance_to(enemy.pos) <= radius:
                self.damage_player(boom, kind="explosion")
        # дроп
        kind = "boss" if getattr(enemy, "is_boss", False) else (
            "elite" if getattr(enemy, "is_elite", False) else "normal")
        if kind != "boss":
            coal = self.economy.coal_drop(kind, self.level, self.threat_stacks,
                                          rng=self.rng)
            self.wallet.add_coal(coal)
            p.stats_obj.counters["coal_total"] = self.wallet.total_coal_earned
            shards = self.economy.shard_drop_elite(self.level, rng=self.rng) \
                if kind == "elite" else 0
            if shards:
                self.wallet.add_shards(shards)
            mats = self.economy.roll_materials(loader.materials(), kind == "elite",
                                               self.level, ng_plus=self.ng_cycle > 0,
                                               rng=self.rng)
            for mid, n in mats.items():
                self.inventory.add_material(mid, n)
        if getattr(enemy, "is_boss", False):
            self.on_boss_death(enemy)

    def _on_mech_death(self, mech):
        if self.boss and mech.kind == "totem" and hasattr(self.boss, "on_totem_death"):
            self.boss.on_totem_death(self)
        if self.boss and mech.kind == "lantern" and hasattr(self.boss, "on_lantern_death"):
            self.boss.on_lantern_death(self)

    def on_boss_death(self, boss):
        if getattr(self, "_boss_loot_done", False):
            return
        self._boss_loot_done = True
        self.boss_defeated = True
        p = self.player
        coal = self.economy.coal_drop("boss", self.level, self.threat_stacks, rng=self.rng)
        self.wallet.add_coal(coal)
        self.wallet.add_shards(self.economy.shard_drop_boss(rng=self.rng))
        mats = self.economy.boss_materials(loader.materials(), self.level,
                                           ng_plus=self.ng_cycle > 0, rng=self.rng)
        for mid, n in mats.items():
            self.inventory.add_material(mid, n)
        boss_uid = f"{boss.boss_id}_L{boss.level_gate}"
        first = boss_uid not in self.meta.bosses_first_kill
        if first:
            self.meta.bosses_first_kill.add(boss_uid)
            if boss.TROPHY:
                self.meta.trophies.add(boss.TROPHY)
                self.rune_system.add_trophy(boss.TROPHY)
                self.events.append(("trophy", boss.TROPHY))
            souls = self.meta.grant_boss_souls(boss.boss_id, boss.level_gate,
                                               self.ng_cycle)
            if souls:
                self.events.append(("souls", souls))
        else:
            self.meta.gold_ingots += self.rng.randint(*C.GOLD_INGOTS_BOSS)
        # Ключи Бездны в NG+2+ (п.19.7)
        if self.ng_cycle >= 2 and self.level in (5, 10, 15):
            self.meta.trophies.add("abyss_key")
        # открытие слотов рун после боссов 10/15 (п.9)
        if self.level in C.RUNE_SLOT_UNLOCK_LEVEL:
            self.rune_system.unlock_slot()
        if self.level == 20:
            self.events.append(("ending", "choice"))

    # ---------- смерть игрока / призрак (п.10) ----------
    def on_player_death(self):
        self._death_done = True
        p = self.player
        self.meta.total_deaths += 1
        p.stats_obj.counters["deaths"] = self.meta.total_deaths
        loss_pct = 0.15 if self.perksystem.has("suicide_gambler") else C.COAL_LOSS_PCT
        lost = self.economy.death_loss(self.wallet, perk_loss_override=loss_pct)
        if getattr(self, "_teleport_loss", False) or self.in_unreachable_zone():
            # смерть в недостижимой зоне: угли сгорают сразу
            self.ghost = None
        else:
            if self.ghost:
                # старый призрак сгорает
                self.ghost = None
            self.ghost = Ghost(p.pos.copy(), lost)
        # временные руны слетают
        self.rune_system.clear_temporary()
        # респавн на последнем костре; мобы возрождаются, босс сбрасывается
        self.respawn_at_campfire()

    def in_unreachable_zone(self):
        return False

    def respawn_at_campfire(self):
        p = self.player
        spot = self.last_campfire.pos if self.last_campfire else Vector2(*self.data.entrance)
        p.pos = spot.copy()
        p.hp = p.max_hp
        p.mana = p.max_mana
        p.stamina = p.max_stamina
        p.sm.change(PlayerState.IDLE)
        p.control_inverted_timer = 0
        self._death_done = False
        # все обычные мобы возрождаются, босс сбрасывается
        for e in list(self.enemies_list):
            if getattr(e, "is_boss", False):
                self.enemies_list.remove(e)
                self.objects = [o for o in self.objects if o not in
                                (getattr(self.boss, "totems", []) +
                                 getattr(self.boss, "lanterns", []) +
                                 getattr(self.boss, "clones", []))]
                self.boss = None
                self._boss_loot_done = False
                if self.level in (5, 10, 15, 20):
                    self.spawn_boss()
            elif not e.alive and not e.kind.startswith("mage"):
                e.alive = True
                e.hp = e.max_hp
                e._death_processed = False
            elif not e.alive:
                self.enemies_list.remove(e)
        # призрак остаётся на месте смерти; в босс-арене — внутри арены
        # (позиция уже сохранена в Ghost)

    def touch_ghost(self):
        """Касание призрака возвращает ВСЕ угли (п.10)."""
        if self.ghost and self.player.pos.distance_to(self.ghost.pos) < 1.2:
            self.wallet.add_coal(self.ghost.coal)
            got = self.ghost.coal
            self.ghost = None
            return got
        return 0

    # ---------- костры / взаимодействие ----------
    def nearest_campfire(self):
        p = self.player
        return min(self.campfires, key=lambda c: c.pos.distance_to(p.pos),
                   default=None)

    def interact(self):
        """Клавиша F: активация костра / подбор призрака / стена-руна."""
        p = self.player
        cf = self.nearest_campfire()
        if cf and cf.pos.distance_to(p.pos) < 2.0:
            cf.activated = True
            self.last_campfire = cf
            self.show_campfire_notes(cf.index)
            newly = self.perksystem.check_unlocks(p.stats_obj.counters)
            for per in newly:
                self.events.append(("perk", per["name"]))
                self.meta.unlocked_perks.add(per["id"])
            return {"campfire": cf}
        got = self.touch_ghost()
        if got:
            self.events.append(("ghost", got))
            return {"ghost_coal": got}
        wr = self._nearest_wall_rune()
        if wr:
            return {"wall_rune": self.trigger_wall_rune(wr)}
        return None

    def _nearest_wall_rune(self):
        p = self.player
        for cell in self.wall_runes_remaining:
            if math.hypot(cell[0] - p.pos.x, cell[1] - p.pos.y) < 1.5:
                return cell
        return None

    def trigger_wall_rune(self, cell):
        """Руна на стене (п.18.2): +10% маны на 30 сек ИЛИ ловушка; кусочек лора."""
        self.wall_runes_remaining.remove(cell)
        lore = loader.lore()
        idx = self.meta.wall_rune_total % max(1, len(lore.get("wall_runes", [""])))
        self.meta.wall_rune_total += 1
        self.meta.discovered_runes.add(f"wall_{self.meta.wall_rune_total}")
        self.player.stats_obj.counters["wall_runes"] = self.meta.wall_rune_total
        if self.rng.random() < 0.25:
            self.damage_player(20, kind="trap")
            return {"lore": lore["wall_runes"][idx], "trap": True}
        self.player.buffs.append({"kind": "mana_max_temp", "value": 0.1,
                                  "duration": 30.0, "orig_duration": 30.0})
        return {"lore": lore["wall_runes"][idx], "trap": False}

    def show_campfire_notes(self, index):
        notes = loader.lore().get("campfire_notes", {})
        note = notes.get(str(index + 1)) or notes.get(index + 1)
        if note:
            self.events.append(("lore", note))

    # ---------- переход уровня ----------
    def descend(self):
        """Выход на следующем уровне (для конструктора нового World)."""
        return self.level + 1

    def exit_reached(self):
        return self.boss_defeated and \
            self.player.pos.distance_to(self.exit_pos) < 2.0
