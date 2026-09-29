"""Загрузка JSON-данных (материалы, рецепты, перки, руны, модификаторы, лор)."""
import json
import os

DATA_DIR = os.path.join(os.path.dirname(__file__))
_cache = {}


def load(name):
    """Загружает data/<name>.json с кэшированием."""
    if name not in _cache:
        with open(os.path.join(DATA_DIR, f"{name}.json"), encoding="utf-8") as f:
            _cache[name] = json.load(f)
    return _cache[name]


def materials():
    return {m["id"]: m for m in load("materials")["materials"]}


def recipes():
    return {r["id"]: r for r in load("recipes")["recipes"]}


def perks():
    return {p["id"]: p for p in load("perks")["perks"]}


def runes():
    data = load("runes")
    all_runes = {}
    for r in data["temporary_runes"]:
        all_runes[r["id"]] = {**r, "permanent": False}
    for r in data["permanent_runes"]:
        all_runes[r["id"]] = {**r, "permanent": True}
    return all_runes


def modifiers():
    return {m["id"]: m for m in load("modifiers")["modifiers"]}


def legacies():
    return {l["id"]: l for l in load("modifiers")["legacies"]}


def lore():
    return load("lore")
