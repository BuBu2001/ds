"""UI Layer: pygame-рендерер. Вся графика генерируется кодом (ТЗ: «графика генерируемая»)."""
import math

TILE = 16
COLORS = {
    "wall": (40, 34, 48), "floor": (72, 60, 78), "floor_deep": (56, 40, 60),
    "player": (230, 210, 120), "mob": (120, 190, 90), "elite": (200, 120, 60),
    "mage_fire": (255, 110, 40), "mage_ice": (90, 170, 255), "mage_dark": (150, 70, 200),
    "summoner": (60, 200, 160), "boss": (255, 60, 60), "ghost": (160, 160, 200, 120),
    "campfire": (255, 170, 40), "campfire_off": (110, 80, 60), "exit": (80, 255, 200),
    "puddle": (70, 130, 220), "steam": (200, 200, 210), "trap": (200, 60, 60),
    "proj_fire": (255, 160, 60), "proj_ice": (140, 200, 255), "proj_spike": (180, 90, 220),
    "lava": (220, 60, 20), "anomaly": (120, 255, 180),
}


def _enemy_color(e):
    k = getattr(e, "kind", "")
    if getattr(e, "is_boss", False):
        return COLORS["boss"]
    if k.startswith("mage_fire"):
        return COLORS["mage_fire"]
    if k.startswith("mage_ice"):
        return COLORS["mage_ice"]
    if k.startswith("mage_dark"):
        return COLORS["mage_dark"]
    if k.startswith("mage_sum"):
        return COLORS["summoner"]
    if getattr(e, "is_elite", False):
        return COLORS["elite"]
    return COLORS["mob"]


class PygameRenderer:
    """Камера следует за игроком; рисует тайлы, сущности, HUD-полосы."""

    def __init__(self, surface_size=(960, 540)):
        self.size = surface_size

    def render(self, screen, world, hud_snap=None):
        import pygame
        sw, sh = self.size
        p = world.player
        camx = p.pos.x * TILE - sw // 2
        camy = p.pos.y * TILE - sh // 2
        deep = world.level >= 11
        screen.fill((15, 12, 20))
        x0, y0 = max(0, int(camx // TILE)), max(0, int(camy // TILE))
        x1 = min(len(world.grid[0]), x0 + sw // TILE + 2)
        y1 = min(len(world.grid), y0 + sh // TILE + 2)
        floor_c = COLORS["floor_deep"] if deep else COLORS["floor"]
        for gy in range(y0, y1):
            for gx in range(x0, x1):
                c = COLORS["wall"] if world.grid[gy][gx] else floor_c
                pygame.draw.rect(screen, c,
                                 (gx * TILE - camx, gy * TILE - camy, TILE, TILE))
        def W(pos):
            return (int(pos[0] * TILE - camx), int(pos[1] * TILE - camy))
        # лужи/пар
        for pd in world.puddles:
            pygame.draw.circle(screen, COLORS["puddle"], W(pd.pos.as_tuple()),
                               int(pd.radius * TILE), width=2)
        for sc in world.steam_clouds:
            s = pygame.Surface((int(sc.radius * TILE * 2),) * 2, pygame.SRCALPHA)
            pygame.draw.circle(s, (*COLORS["steam"], 70),
                               (int(sc.radius * TILE),) * 2, int(sc.radius * TILE))
            screen.blit(s, (W(sc.pos.as_tuple())[0] - sc.radius * TILE,
                            W(sc.pos.as_tuple())[1] - sc.radius * TILE))
        # ловушки
        for tr in world.traps:
            pygame.draw.circle(screen, COLORS["trap"], W(tr.pos.as_tuple()), 4)
        # костры / призрак / выход
        for cf in world.campfires:
            col = COLORS["campfire"] if cf.activated else COLORS["campfire_off"]
            pygame.draw.circle(screen, col, W(cf.pos.as_tuple()), 7)
        if world.ghost:
            pygame.draw.circle(screen, COLORS["ghost"][:3], W(world.ghost.pos.as_tuple()), 6, 2)
        pygame.draw.circle(screen, COLORS["exit"], W(world.exit_pos.as_tuple()), 8)
        # враги
        for e in world.enemies() + world.objects:
            if not getattr(e, "alive", True):
                continue
            r = int(getattr(e, "radius", 0.5) * TILE)
            pygame.draw.circle(screen, _enemy_color(e), W(e.pos.as_tuple()), max(4, r))
            hpf = e.hp / e.max_hp if e.max_hp else 1
            if hpf < 1:
                x, y = W(e.pos.as_tuple())
                pygame.draw.rect(screen, (200, 40, 40), (x - 10, y - r - 8, 20, 3))
                pygame.draw.rect(screen, (80, 200, 80), (x - 10, y - r - 8, int(20 * hpf), 3))
        # снаряды
        for pr in world.projectiles:
            col = COLORS.get("proj_" + pr.kind, COLORS["proj_fire"])
            pygame.draw.circle(screen, col, W(pr.pos.as_tuple()), 3)
        # игрок + направление атаки
        px, py = W(p.pos.as_tuple())
        pygame.draw.circle(screen, COLORS["player"], (px, py), 8)
        d = p.facing
        pygame.draw.line(screen, (255, 255, 255), (px, py),
                         (px + d.x * 14, py + d.y * 14), 2)
        # лава на 20 ур. (сужение арены, п.13.5)
        if getattr(world, "lava_margin", 0):
            m = world.lava_margin * TILE
            for rect in ((0, 0, m, sh), (sw - m, 0, m, sh), (0, 0, sw, m), (0, sh - m, sw, m)):
                pygame.draw.rect(screen, COLORS["lava"], rect)
        if hud_snap:
            self._hud(screen, hud_snap)

    def _hud(self, screen, snap):
        import pygame
        def bar(x, y, val, mx, color):
            pygame.draw.rect(screen, (30, 30, 30), (x, y, 220, 14), border_radius=4)
            w = int(220 * max(0.0, min(1.0, val / mx))) if mx else 0
            pygame.draw.rect(screen, color, (x, y, w, 14), border_radius=4)
        hp, hpm = snap["hp"]; mp, mpm = snap["mana"]; sp, spm = snap["stamina"]
        bar(12, 12, hp, hpm, (210, 60, 60))
        bar(12, 30, mp, mpm, (60, 100, 220))
        bar(12, 48, sp, spm, (90, 200, 90))
        f = pygame.font.SysFont(None, 22)
        screen.blit(f.render(f"Угли: {snap['coal']}  Осколки: {snap['shards']}",
                             True, (240, 220, 160)), (screen.get_width() - 240, 12))
        screen.blit(f.render(f"Ур.{snap['level']}  NG+{snap['ng_cycle']}",
                             True, (200, 200, 200)), (screen.get_width() - 240, 36))
        if snap.get("inverted"):
            screen.blit(f.render("ИНВЕРСИЯ!", True, (255, 80, 200)), (12, 68))
        # миникарта (п.20.1, левый низ)
        mm = pygame.Surface((120, 120), pygame.SRCALPHA)
        mm.fill((0, 0, 0, 120))
        for kind, pos in snap["minimap"]:
            cx = int(pos[0]) % 100 * 120 // 100
            cy = int(pos[1]) % 100 * 120 // 100
            col = {"player": COLORS["player"], "ghost": COLORS["ghost"],
                   "boss": COLORS["boss"], "exit": COLORS["exit"]}.get(
                      kind.split("_")[0], COLORS["campfire"])
            pygame.draw.circle(mm, col[:3], (cx, cy), 3)
        screen.blit(mm, (12, screen.get_height() - 132))
