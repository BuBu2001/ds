"""Базовый класс стейт-машины (ТЗ п.12, 13, 16).

Универсальный механизм: состояния (Enum) + переходы + именованные таймеры.
Конкретные машины (игрок, мобы, маги, боссы) переопределяют check_transitions.
"""


class StateMachine:
    def __init__(self, initial):
        self.state = initial
        self.prev_state = None
        self.state_time = 0.0
        self.timers = {}

    # --- служебное ------------------------------------------------------
    def change(self, new_state):
        if new_state == self.state:
            return False
        self.prev_state = self.state
        self.state = new_state
        self.state_time = 0.0
        self.on_enter(new_state)
        return True

    def on_enter(self, state):
        """Хук входа в состояние (переопределяется потомками)."""

    def update(self, dt, context):
        self.state_time += dt
        for name in list(self.timers):
            self.timers[name] -= dt
            if self.timers[name] <= 0:
                del self.timers[name]
        self.check_transitions(context)

    def set_timer(self, name, duration):
        self.timers[name] = duration

    def timer_ready(self, name):
        """True, если таймер с таким именем не активен (истёк/не запущен)."""
        return name not in self.timers

    def check_transitions(self, context):
        """Переопределяется в конкретных стейт-машинах."""
        raise NotImplementedError

    @staticmethod
    def dist(a, b):
        return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5
