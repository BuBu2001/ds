"""Игровой цикл (связка Input → World → UI). Точка входа: python -m game.engine.app."""
import time
from ..input import RawInput, KeyBinding
from .world import World
from ..meta.save_data import MetaState, save_game, load_game
from ..ui.screens import HudModel, InventoryModel, CampfireScreenModel, DeathScreenModel
from ..ui.renderer import PygameRenderer
from ..entities.player import PlayerState


def run(seed=None):
    import pygame
    pygame.init()
    screen = pygame.display.set_mode((960, 540))
    pygame.display.set_caption("Экономика и Прогрессия — souls-like roguelike")
    clock = pygame.time.Clock()
    meta = load_game() or MetaState()
    world = World(meta, level=1, seed=seed)
    binding = KeyBinding.from_dict(meta.settings.get("bindings"))
    ri = RawInput()
    renderer = PygameRenderer()
    hud = HudModel(world)
    inv_model = InventoryModel(world)
    camp_model = None
    death_shown = False
    fps_cap = 60
    running = True

    def rebuild_models():
        nonlocal hud, inv_model, camp_model
        hud = HudModel(world)
        inv_model = InventoryModel(world)
        camp_model = None

    while running:
        dt = clock.tick(fps_cap) / 1000.0
        ri.begin_frame()
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                if camp_model is not None:      # ESC закрывает экран костра (паузу)
                    camp_model.close()
                    camp_model = None
                else:
                    save_game(meta)
                    running = False
            else:
                ri.feed_pygame_event(ev, binding)
        # однократные действия
        if ri.was_pressed("interact"):
            cf = world.interact()
            if cf is not None:
                camp_model = CampfireScreenModel(world, cf)
                cf._closed = False              # экран открыт → мир на паузе
            elif camp_model is not None:
                camp_model.close()
                camp_model = None
        if ri.was_pressed("inventory"):
            print(inv_model.tabs())
        for i, act in enumerate(("potion_1", "potion_2", "potion_3", "potion_4")):
            if ri.was_pressed(act):
                inv_model.use_potion(i)
        paused = camp_model is not None and not getattr(camp_model.campfire, "_closed", True)
        if not paused:
            world.update(dt, ri)
        if world.player.sm.state == PlayerState.DEAD and not death_shown:
            print(DeathScreenModel(world).info())
            death_shown = True
        if world.boss_defeated and world.exit_reached():
            save_game(meta)
            world = World(meta, level=min(20, world.level + 1),
                          ng_cycle=world.ng_cycle, seed=seed)
            death_shown = False
            rebuild_models()
        renderer.render(screen, world, hud.snapshot())
        pygame.display.flip()
    pygame.quit()


if __name__ == "__main__":
    run()
