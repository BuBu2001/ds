"""Генератор подземелий (ТЗ п.14): BSP-гибрид + клеточный автомат + валидация A*.

Алгоритм:
 1. Сетка по уровню (40/60/80/100).
 2. Заполнение 45% стен / 55% пол, границы всегда стены.
 3. Клеточный автомат, 5 итераций (>=5 соседей-стен -> стена).
 4. Оставляем самый большой связный компонент.
 5. Расстановка входа/выхода/костров/мобов/элиток/магов/ловушек/рун на стенах.
 6. Босс-рум вырезается у выхода (20x20 или 25x25 + колонны + точки механик).
 7. Валидация A* до 10 попыток, иначе принудительное пробитие коридоров.
"""
import random
from ..core import constants as C
from .pathfinding import astar, bfs_farthest, connected_component


class DungeonData:
    """Результат генерации одного уровня."""

    def __init__(self, grid, entrance, exit_pos, boss_room_center, boss_room_size,
                 campfires, mob_spawns, elite_spawns, mage_spawns, trap_spawns,
                 wall_runes, gravity_zones, pillars, mechanic_points, level):
        self.grid = grid
        self.entrance = entrance
        self.exit_pos = exit_pos
        self.boss_room_center = boss_room_center
        self.boss_room_size = boss_room_size
        self.campfires = campfires
        self.mob_spawns = mob_spawns
        self.elite_spawns = elite_spawns
        self.mage_spawns = mage_spawns
        self.trap_spawns = trap_spawns
        self.wall_runes = wall_runes
        self.gravity_zones = gravity_zones
        self.pillars = pillars
        self.mechanic_points = mechanic_points   # точки под тотемы/фонари
        self.level = level

    @property
    def floor_tiles(self):
        return sum(row.count(0) for row in self.grid)


class DungeonGenerator:
    def __init__(self, rng=None):
        self.rng = rng or random.Random()

    # ---------- шаги 1–4 ----------
    def build_grid(self, size):
        return [[1] * size for _ in range(size)]

    def fill_random(self, grid):
        size = len(grid)
        for y in range(1, size - 1):
            for x in range(1, size - 1):
                grid[y][x] = 1 if self.rng.random() < C.WALL_CHANCE else 0

    def ca_step(self, grid):
        size = len(grid)
        new = [row[:] for row in grid]
        for y in range(1, size - 1):
            for x in range(1, size - 1):
                walls = 0
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        if dx == 0 and dy == 0:
                            continue
                        walls += grid[y + dy][x + dx]
                new[y][x] = 1 if walls >= C.CA_WALL_THRESHOLD else 0
        for i in range(size):  # граница — всегда стена
            new[0][i] = new[size - 1][i] = new[i][0] = new[i][size - 1] = 1
        return new

    def keep_largest_component(self, grid):
        size = len(grid)
        seen_all = set()
        best = set()
        for y in range(size):
            for x in range(size):
                if grid[y][x] == 0 and (x, y) not in seen_all:
                    comp = connected_component(grid, (x, y))
                    seen_all |= comp
                    if len(comp) > len(best):
                        best = comp
        new = [[1] * size for _ in range(size)]
        for (x, y) in best:
            new[y][x] = 0
        return new, best

    # ---------- шаг 5: расстановка ----------
    def pick_entrance(self, floors):
        edge = [f for f in floors if f[0] <= 1 or f[1] <= 1 or
                f[0] >= len(floors) ** 0.5 - 2 or f[1] >= len(floors) ** 0.5 - 2]
        return self.rng.choice(edge if edge else list(floors))

    def place_on_floors(self, floors, count, avoid=(), min_dist=3):
        placed, floors_list = [], list(floors)
        self.rng.shuffle(floors_list)
        for p in floors_list:
            if len(placed) >= count:
                break
            if any(((p[0] - a[0]) ** 2 + (p[1] - a[1]) ** 2) < min_dist ** 2
                   for a in list(avoid) + placed):
                continue
            placed.append(p)
        return placed

    # ---------- шаг 6: босс-рум ----------
    def carve_boss_room(self, grid, center, size):
        h = len(grid)
        cx, cy = center
        half = size // 2
        x0, y0 = max(1, cx - half), max(1, cy - half)
        x1, y1 = min(h - 1, cx + half), min(h - 1, cy + half)
        for y in range(y0, y1):
            for x in range(x0, x1):
                grid[y][x] = 0
        # 4–8 колонн 2x2
        pillars = []
        n_pillars = self.rng.randint(4, 8)
        for _ in range(n_pillars):
            px = self.rng.randint(x0 + 2, max(x0 + 3, x1 - 4))
            py = self.rng.randint(y0 + 2, max(y0 + 3, y1 - 4))
            for dy in (0, 1):
                for dx in (0, 1):
                    if y0 <= py + dy < y1 and x0 <= px + dx < x1:
                        grid[py + dy][px + dx] = 1
            pillars.append((px, py))
        # 5 точек под механики: центр + 4 «угла арены»
        margin = max(2, size // 5)
        mech_points = [
            ((x0 + x1) // 2, (y0 + y1) // 2),
            (x0 + margin, y0 + margin), (x1 - margin, y0 + margin),
            (x0 + margin, y1 - margin), (x1 - margin, y1 - margin),
        ]
        return (x0, y0, x1, y1), pillars, mech_points

    # ---------- шаг 7: валидация / принудительная связность ----------
    def validate(self, grid, entrance, exit_pos, boss_center, campfires, spawns):
        if astar(grid, entrance, exit_pos) is None:
            return False
        if astar(grid, entrance, boss_center) is None:
            return False
        for cf in campfires:
            if astar(grid, entrance, cf) is None:
                return False
        for sp in spawns:
            if sp not in connected_component(grid, entrance):
                return False
        return True

    def force_connect(self, grid, points):
        """Пробивает L-образные коридоры между всеми точками."""
        def dig(a, b):
            x0, y0 = a
            x1, y1 = b
            for x in range(min(x0, x1), max(x0, x1) + 1):
                if 0 < y0 < len(grid) - 1:
                    grid[y0][x] = 0
            for y in range(min(y0, y1), max(y0, y1) + 1):
                if 0 < x1 < len(grid) - 1:
                    grid[y][x1] = 0
        for i in range(len(points) - 1):
            dig(points[i], points[i + 1])

    # ---------- публичный API ----------
    def generate(self, level):
        size = C.grid_size(level)
        for attempt in range(C.GEN_ATTEMPTS):
            grid = self.build_grid(size)
            self.fill_random(grid)
            for _ in range(C.CA_ITERATIONS):
                grid = self.ca_step(grid)
            grid, floors = self.keep_largest_component(grid)
            if len(floors) < 50:
                continue
            entrance = self.pick_entrance(floors)
            exit_pos, _ = bfs_farthest(grid, entrance)
            boss_size = C.BOSS_ROOM_LARGE if level >= 11 else C.BOSS_ROOM_MIN
            room_box, pillars, mech_points = self.carve_boss_room(grid, exit_pos, boss_size)
            boss_center = ((room_box[0] + room_box[2]) // 2,
                           (room_box[1] + room_box[3]) // 2)
            grid, floors = self.keep_largest_component(grid)
            entrance = entrance if grid[entrance[1]][entrance[0]] == 0 else self.pick_entrance(floors)

            floor_count = len(floors)
            # костры: каждые 5 комнат, минимум 3; таблица из ТЗ
            if level <= 5:
                cf_count = 3
            elif level <= 10:
                cf_count = self.rng.randint(4, 5)
            elif level < 20:
                cf_count = self.rng.randint(6, 7)
            else:
                cf_count = 8
            campfires = self.place_on_floors(floors, cf_count,
                                             avoid=[entrance, boss_center], min_dist=6)
            mobs = self.place_on_floors(floors, max(1, floor_count // C.MOBS_PER_TILES),
                                        avoid=campfires + [boss_center], min_dist=2)
            elites = self.place_on_floors(floors, max(1, floor_count // C.ELITES_PER_TILES),
                                          avoid=campfires + mobs + [boss_center], min_dist=4)
            mages = traps = []
            if level >= 6:
                mages = self.place_on_floors(floors, max(1, floor_count // C.MAGES_PER_TILES),
                                             avoid=campfires + mobs + [boss_center], min_dist=5)
                traps = self.place_on_floors(floors, max(1, floor_count // C.TRAPS_PER_TILES),
                                             avoid=campfires + mobs, min_dist=2)
            runes = self.place_wall_runes(grid, floors,
                                          max(1, floor_count // C.WALL_RUNES_PER_TILES))
            gravity_zones = []
            if level >= 11:
                n_local = self.rng.randint(*C.ANOMALY_LOCAL_COUNT)
                gravity_zones = self.place_on_floors(floors, n_local,
                                                     avoid=campfires, min_dist=8)
            spawns = mobs + elites + mages
            if self.validate(grid, entrance, boss_center, boss_center, campfires, spawns):
                return DungeonData(grid, entrance, exit_pos, boss_center, boss_size,
                                   campfires, mobs, elites, mages, traps, runes,
                                   gravity_zones, pillars, mech_points, level)
        # не повезло 10 раз — принудительное пробитие
        grid = self.build_grid(size)
        self.fill_random(grid)
        for _ in range(C.CA_ITERATIONS):
            grid = self.ca_step(grid)
        grid, floors = self.keep_largest_component(grid)
        entrance = self.pick_entrance(floors)
        exit_pos, _ = bfs_farthest(grid, entrance)
        boss_size = C.BOSS_ROOM_LARGE if level >= 11 else C.BOSS_ROOM_MIN
        room_box, pillars, mech_points = self.carve_boss_room(grid, exit_pos, boss_size)
        boss_center = ((room_box[0] + room_box[2]) // 2, (room_box[1] + room_box[3]) // 2)
        floors = {(x, y) for y in range(len(grid)) for x in range(len(grid[0]))
                  if grid[y][x] == 0}
        campfires = self.place_on_floors(floors, 3, avoid=[entrance, boss_center], min_dist=5)
        self.force_connect(grid, [entrance] + campfires + [boss_center])
        floors = {(x, y) for y in range(len(grid)) for x in range(len(grid[0]))
                  if grid[y][x] == 0}
        mobs = self.place_on_floors(floors, max(1, len(floors) // C.MOBS_PER_TILES),
                                    avoid=campfires, min_dist=2)
        elites = self.place_on_floors(floors, max(1, len(floors) // C.ELITES_PER_TILES),
                                      avoid=campfires + mobs, min_dist=4)
        return DungeonData(grid, entrance, exit_pos, boss_center, boss_size,
                           campfires, mobs, elites, [], [], [], [], pillars,
                           mech_points, level)

    def place_wall_runes(self, grid, floors, count):
        """Руны на стенах: полуклетка рядом со стеной."""
        h, w = len(grid), len(grid[0])
        candidates = []
        for (x, y) in floors:
            adjacent_wall = any(0 <= nx < w and 0 <= ny < h and grid[ny][nx] == 1
                                for nx, ny in ((x+1, y), (x-1, y), (x, y+1), (x, y-1)))
            if adjacent_wall:
                candidates.append((x, y))
        self.rng.shuffle(candidates)
        return candidates[:count]
