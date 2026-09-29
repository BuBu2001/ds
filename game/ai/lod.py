"""LOD-планировщик (ТЗ п.21.3): мобы — 60 FPS, маги и боссы — 30 FPS."""


class LodScheduler:
    MOB_HZ = 60
    HEAVY_HZ = 30   # маги, боссы

    def __init__(self):
        self._acc = {}   # id(ent) -> накопитель dt

    def _rate(self, ent):
        heavy = getattr(ent, "is_boss", False) or getattr(ent, "kind", "").startswith("mage")
        return self.HEAVY_HZ if heavy else self.MOB_HZ

    def step(self, ent, dt, update_fn, *args):
        """Вызывает update_fn(ent, dt_eff, *args) с квантованным шагом для тяжёлых сущностей."""
        rate = self._rate(ent)
        if rate >= self.MOB_HZ:
            update_fn(ent, dt, *args)
            return True
        key = id(ent)
        self._acc[key] = self._acc.get(key, 0.0) + dt
        frame_t = 1.0 / rate
        if self._acc[key] < frame_t:
            return False
        eff_dt = self._acc[key]
        self._acc[key] = 0.0
        update_fn(ent, eff_dt, *args)
        return True

    def forget(self, ent):
        self._acc.pop(id(ent), None)
