"""AI Layer (ТЗ п.21.2, слой 4): стейт-машины мобов и магов + LOD-планировщик."""
from .brain import MobBrain, MageBrain
from .lod import LodScheduler

__all__ = ["MobBrain", "MageBrain", "LodScheduler"]
