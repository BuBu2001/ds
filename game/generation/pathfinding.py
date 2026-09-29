"""A* и BFS по сетке данжа (ТЗ п.14.3 валидация, п.12 LOS)."""
import heapq
from collections import deque


def neighbors4(x, y, w, h):
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nx, ny = x + dx, y + dy
        if 0 <= nx < w and 0 <= ny < h:
            yield nx, ny


def bfs_farthest(grid, start):
    """Самая дальняя достижимая клетка (для выхода) + карта дистанций."""
    h = len(grid)
    w = len(grid[0])
    dist = {start: 0}
    q = deque([start])
    far, far_d = start, 0
    while q:
        cur = q.popleft()
        d = dist[cur]
        for nb in neighbors4(cur[0], cur[1], w, h):
            if grid[nb[1]][nb[0]] == 0 and nb not in dist:
                dist[nb] = d + 1
                q.append(nb)
                if d + 1 > far_d:
                    far, far_d = nb, d + 1
    return far, dist


def connected_component(grid, start):
    h, w = len(grid), len(grid[0])
    seen = {start}
    q = deque([start])
    while q:
        cur = q.popleft()
        for nb in neighbors4(cur[0], cur[1], w, h):
            if grid[nb[1]][nb[0]] == 0 and nb not in seen:
                seen.add(nb)
                q.append(nb)
    return seen


def astar(grid, start, goal):
    """Возвращает путь (список клеток) или None. 0 = пол, 1 = стена."""
    h, w = len(grid), len(grid[0])

    def passable(p):
        x, y = int(p[0]), int(p[1])
        return 0 <= x < w and 0 <= y < h and grid[y][x] == 0

    if not (passable(start) and passable(goal)):
        return None
    open_heap = [(0, start)]
    came = {start: None}
    g = {start: 0}
    while open_heap:
        _, cur = heapq.heappop(open_heap)
        if cur == goal:
            path = []
            while cur is not None:
                path.append(cur)
                cur = came[cur]
            return list(reversed(path))
        for nb in neighbors4(cur[0], cur[1], w, h):
            if not passable(nb):
                continue
            tentative = g[cur] + 1
            if tentative < g.get(nb, float("inf")):
                came[nb] = cur
                g[nb] = tentative
                f = tentative + abs(nb[0] - goal[0]) + abs(nb[1] - goal[1])
                heapq.heappush(open_heap, (f, nb))
    return None


def line_of_sight(grid, a, b):
    """Bresenham-проверка прямой видимости между клетками."""
    x0, y0 = int(a[0]), int(a[1])
    x1, y1 = int(b[0]), int(b[1])
    dx, dy = abs(x1 - x0), abs(y1 - y0)
    sx, sy = (1 if x1 > x0 else -1), (1 if y1 > y0 else -1)
    err = dx - dy
    while True:
        if grid[y0][x0] == 1 and (x0, y0) != (a[0], a[1]):
            return False
        if (x0, y0) == (x1, y1):
            return True
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x0 += sx
        if e2 < dx:
            err += dx
            y0 += sy
