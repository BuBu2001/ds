"""Input Layer: RawInput + настраиваемые бинды (ТЗ п.2).

pygame-импорт ленивый: модуль можно использовать headless (тесты),
передавая события вручную через feed_key / feed_pygame_event.
"""
from dataclasses import dataclass, field


# Действия, доступные для ремапа (п.2: «Управление полностью ремапится»)
DEFAULT_BINDINGS = {
    "forward": "w",
    "back": "s",
    "left": "a",
    "right": "d",
    "attack_light": "button1",     # ЛКМ
    "attack_heavy": "button3",     # ПКМ (удержание)
    "dash": "lshift",              # Shift
    "cast_fire": "q",
    "cast_ice": "e",
    "interact": "f",
    "inventory": "i",
    "map": "m",
    "potion_1": "1",
    "potion_2": "2",
    "potion_3": "3",
    "potion_4": "4",
}


@dataclass
class KeyBinding:
    """Хранилище биндов; сериализуется в сейв, грузится из настроек."""
    bindings: dict = field(default_factory=lambda: dict(DEFAULT_BINDINGS))

    def rebind(self, action, key):
        if action not in self.bindings:
            raise KeyError(f"неизвестное действие: {action}")
        self.bindings[action] = key

    def reset(self):
        self.bindings = dict(DEFAULT_BINDINGS)

    def to_dict(self):
        return dict(self.bindings)

    @classmethod
    def from_dict(cls, d):
        b = cls()
        for k, v in (d or {}).items():
            if k in b.bindings:
                b.bindings[k] = v
        return b


@dataclass
class RawInput:
    """Снимок состояния ввода для одного тика World.update().

    Флаги направлений/кнопок заполняются pygame-циклом (game/engine/app.py)
    или напрямую в тестах. camera_yaw — угол прицела в радианах; мышь/камера
    НИКОГДА не инвертируются (п.16.4) — инверсию применяет process_input.
    """
    forward: bool = False
    back: bool = False
    left: bool = False
    right: bool = False
    running: bool = True          # удерживается ли «движение» (для LOD-анимаций)
    mouse_x: float = 0.0
    mouse_y: float = 0.0
    camera_yaw: float = 0.0
    # однократные события за кадр:
    pressed: set = field(default_factory=set)   # действия, нажатые этот кадр
    released: set = field(default_factory=set)  # действия, отпущенные этот кадр

    def was_pressed(self, action):
        return action in self.pressed

    def begin_frame(self):
        self.pressed = set()
        self.released = set()

    # ---------- интеграция с pygame ----------
    def feed_key(self, key_name, down, binding: KeyBinding):
        """key_name — имя клавиши pygame.key.name(...) или 'buttonN' для мыши."""
        for action, bound in binding.bindings.items():
            if bound == key_name:
                self._set_action(action, down)

    def _set_action(self, action, down):
        if action == "forward":
            self.forward = down
        elif action == "back":
            self.back = down
        elif action == "left":
            self.left = down
        elif action == "right":
            self.right = down
        if down and action in self.pressed:
            return
        if down:
            self.pressed.add(action)
        else:
            self.released.add(action)
        self.running = self.forward or self.back or self.left or self.right

    def feed_pygame_event(self, event, binding: KeyBinding):
        """Пропускает pygame-событие через бинды. Вызывается из app-цикла."""
        import pygame
        if event.type == pygame.KEYDOWN:
            self.feed_key(pygame.key.name(event.key), True, binding)
        elif event.type == pygame.KEYUP:
            self.feed_key(pygame.key.name(event.key), False, binding)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            self.feed_key(f"button{event.button}", True, binding)
        elif event.type == pygame.MOUSEBUTTONUP:
            self.feed_key(f"button{event.button}", False, binding)
        elif event.type == pygame.MOUSEMOTION:
            self.mouse_x, self.mouse_y = event.pos
