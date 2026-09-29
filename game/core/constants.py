"""Глобальные игровые константы (ТЗ: разделы 2–4, 8, 10, 14–19)."""

# --- Мир / рендер ---
TILE = 32                    # пикселей на клетку (1 м = 1 клетка)
FPS = 60
SCREEN_W, SCREEN_H = 1280, 720
BASE_GRAVITY = 9.8           # «вниз» в экранных координатах для снарядов/сноса

# --- Прокачка статов (п.3.2): экспоненциальная стоимость ---
DMG_UP_BASE, DMG_UP_GROWTH, DMG_UP_MAX = 20, 1.35, 20      # cost = 20*1.35^(lvl-1), +2 урона/ур
SPD_UP_BASE, SPD_UP_GROWTH, SPD_UP_MAX = 30, 1.35, 15      # +0.05 уд/сек за уровень
STA_UP_BASE, STA_UP_GROWTH, STA_UP_MAX = 25, 1.30, 20      # +10 стамины, реген +0.5/ур

# --- Базовые статы (п.4) ---
HP_BASE, HP_PER_META = 100, 20
MANA_BASE, MANA_PER_META = 100, 20
STAMINA_BASE, STAMINA_PER_LEVEL = 100, 10
DAMAGE_BASE, DAMAGE_PER_LEVEL = 10, 2
ATTACK_SPEED_BASE, ATTACK_SPEED_PER_LEVEL = 1.0, 0.05
MANA_REGEN = 5.0             # фиксировано
STAMINA_REGEN_BASE, STAMINA_REGEN_PER_LEVEL = 10.0, 0.5
STAMINA_REGEN_DELAY = 1.0    # сек после действия

# --- Стоимость действий стаминой (п.4) ---
COST_LIGHT_ATK = 10
COST_HEAVY_ATK = 25
COST_DODGE = 20
COST_RUN = 5                 # в секунду
COST_BLOCK = 15              # за удар
COST_COMBO_FROZEN = 20

# --- Дроп валют (п.3.1) ---
COAL_NORMAL = (1, 3)
COAL_ELITE = (5, 10)
COAL_BOSS = (50, 100)
SHARD_ELITE_CHANCE = 0.05          # +1% за каждый уровень выше 10
SHARD_BOSS = (1, 2)
COAL_TO_SHARD_RATE = 10            # 10 углей = 1 осколок
SOULS_BY_BOSS = {5: 1, 10: 2, 15: 3}
GOLD_INGOTS_BOSS = (1, 3)

# --- Death penalty (п.10) ---
COAL_LOSS_PCT = 0.30               # перк «Самоубийца»: 0.15

# --- Костёр (п.5) ---
REST_LIMIT_BASE = 3
REST_LIMIT_MAX = 5
REST_THREAT_POWER = 0.10           # мобы +10% силы за отдых
REST_THREAT_DROP = 0.15            # дроп углей +15% за отдых
CAMPFIRE_UPGRADES = {
    "rest_charge": {"cost_shards": 4, "max": 2},
    "craft_slot": {"cost_shards": 6, "max": 1},
    "stat_discount": {"cost_shards": 8, "max": 1},   # -10% стоимости прокачки
}

# --- Магия (п.8) ---
FIRE_COST, ICE_COST = 15, 12
BURN_DPS_PCT, BURN_DURATION, BURN_STACKS = 0.05, 4.0, 3
BRITTLE_SLOW, BRITTLE_DURATION, BRITTLE_CRIT_VULN = 0.30, 3.0, 0.20
FREEZE_NORMAL, FREEZE_BOSS = 1.5, 0.5
STEAM_RADIUS, STEAM_DMG_PCT, STEAM_ACC_DEBUFF, STEAM_DURATION = 3.0, 0.30, 0.50, 4.0
ICE_EXTINGUISH_DMG_PCT, BRITTLE_ON_EXTINGUISH = 0.20, 5.0
SWORD_BREAK_ARMOR_PCT, SWORD_BREAK_ARMOR_DUR = 0.20, 5.0

# --- Руны (п.9) ---
RUNE_SLOTS_BASE = 1
RUNE_SLOT_UNLOCK_LEVEL = {2: 10, 3: 15}   # слот N открывается после босса уровня X

# --- Инвентарь / мета (п.6.1) ---
INV_SLOTS_BASE, INV_SLOTS_MAX = 6, 12
META_MAX = {"hp": 200, "mana": 200, "stamina": 200, "inventory": 12,
            "start_perks": 3, "start_runes": 3, "coal_drop": 0.25, "shard_drop": 0.15}
TALENT_PRICES = [1, 1, 2, 2, 3, 3, 5, 5, 8, 13]

# --- Генератор (п.14) ---
def grid_size(level):
    if level <= 5: return 40
    if level <= 10: return 60
    if level < 20: return 80
    return 100

WALL_CHANCE = 0.45
CA_ITERATIONS = 5
CA_WALL_THRESHOLD = 5
GEN_ATTEMPTS = 10
MOBS_PER_TILES = 20
ELITES_PER_TILES = 100
MAGES_PER_TILES = 150
TRAPS_PER_TILES = 50
WALL_RUNES_PER_TILES = 80
BOSS_ROOM_MIN = 20
BOSS_ROOM_LARGE = 25

# --- Аномалии (п.15) ---
ANOMALY_GLOBAL_PERIOD = 30.0
ANOMALY_GLOBAL_DURATION = 10.0
ANOMALY_LOCAL_RADIUS = (4, 6)
ANOMALY_LOCAL_COUNT = (2, 3)

# --- Ловушки / лужи (п.12.2) ---
PUDDLE_RADIUS, PUDDLE_DURATION, PUDDLE_CAST_CD = 2.0, 10.0, 6.0
INVERT_DURATION = 0.5
BRITTLE_PUDDLE_ADD, BRITTLE_PUDDLE_CAP = 3.0, 6.0

# --- NG+ (п.19) ---
NG_ENCHANT_CHANCE = 0.05
NG_ENCHANT_BOSS_CHANCE = 0.10
ABYSS_KEYS_REQUIRED = 3
