# 🍎 Установка на macOS (Intel и Apple Silicon)

«Экономика и Прогрессия» — Souls-like рогалик на Python.
Общая инструкция: [INSTALL.md](../../INSTALL.md). Навигация: [index](README.md).

---

## 1. Системные зависимости

Рекомендуется Homebrew:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"   # если brew нет
brew install python@3.12 sdl2_image sdl2_mixer
```

Проверка:

```bash
python3 --version   # >= 3.10
```

## 2. Виртуальное окружение и pygame

```bash
cd ~/projects/economy-progress
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install pygame        # wheels есть под arm64 и x86_64
```

## 3. Проверка и запуск

```bash
python -c "from game.engine.world import World; print('OK: модули собраны')"
python -m game.engine.app
```

## 4. Особенности macOS

- На **Apple Silicon** убедитесь, что используется нативная сборка Python
  (`arch -arm64 python3 -m venv .venv`), иначе pygame встанет через Rosetta.
- При первом запуске Gatekeeper может предупредить о неизвестном разработчике —
  «System Settings → Privacy & Security → Open Anyway».
- Headless-режим: `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python -m game.engine.app`.

## 5. Деинсталляция

```bash
rm -rf ~/projects/economy-progress
rm -f ~/.abyss_economy_save.json
```

---
© 2026. Копирование и распространение регулируются [LICENSE](../../LICENSE).
