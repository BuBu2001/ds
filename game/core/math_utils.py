"""Математические утилиты: Vector2, дистанции, нормализация."""
import math


class Vector2:
    __slots__ = ("x", "y")

    def __init__(self, x=0.0, y=0.0):
        self.x = float(x)
        self.y = float(y)

    def copy(self):
        return Vector2(self.x, self.y)

    def __add__(self, o): return Vector2(self.x + o.x, self.y + o.y)
    def __sub__(self, o): return Vector2(self.x - o.x, self.y - o.y)
    def __mul__(self, s): return Vector2(self.x * s, self.y * s)
    __rmul__ = __mul__

    def length(self):
        return math.hypot(self.x, self.y)

    def normalized(self):
        l = self.length()
        return Vector2(self.x / l, self.y / l) if l > 1e-9 else Vector2(0, 0)

    def distance_to(self, o):
        return math.hypot(self.x - o.x, self.y - o.y)

    def angle(self):
        return math.atan2(self.y, self.x)

    @staticmethod
    def from_angle(a, scale=1.0):
        return Vector2(math.cos(a) * scale, math.sin(a) * scale)

    def as_tuple(self):
        return (self.x, self.y)

    def __repr__(self):
        return f"Vector2({self.x:.1f},{self.y:.1f})"
