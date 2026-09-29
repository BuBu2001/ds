# 🏔️ Установка на Arch Linux (и производные: EndeavourOS, Manjaro, Garuda)

«Экономика и Прогрессия» — Souls-like рогалик на Python.
Общая инструкция: [INSTALL.md](../../INSTALL.md). Навигация: [index](README.md).

> Проверено на: Arch Linux (rolling), EndeavourOS. Manjaro — то же, если
> синхронизированы зеркала (`sudo pacman -Sy`).

> 💡 Быстрее всего — автоматический установщик в корне проекта:
> `bash setup.sh` (поддерживает Debian/Ubuntu, Arch, Fedora/RHEL, openSUSE, macOS).
> Ниже — ручная установка шаг за шагом.


---

## 1. Системные пакеты

В Arch Python всегда свежий (3.12+), а SDL2 ставится одной командой:

```bash
sudo pacman -Syu --needed python python-pip sdl2_image sdl2_mixer base-devel
```

| Пакет | Зачем |
|-------|-------|
| `python` | интерпретатор (≥ 3.10 гарантирован в extra) |
| `python-pip` | менеджер пакетов Python |
| `sdl2_image`, `sdl2_mixer` | расширенные SDL-библиотеки для pygame |
| `base-devel` | gcc/make — на случай сборки pygame из исходников |

`pygame` есть и в репозитории — это самый «арчевый» путь:

```bash
sudo pacman -S --needed python-pygame     # вариант А: системный pygame
```

Но для игры рекомендуется изолированное окружение (вариант Б ниже),
т.к. в Arch действует защита системного site-packages (PEP 668).

## 2. Виртуальное окружение и зависимости (рекомендуется)

```bash
cd ~/projects/economy-progress            # папка с игрой
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install pygame
```

> ⚠️ `pip install` без `.venv` в Arch завершится ошибкой
> `error: externally-managed-environment`. Это не баг — так защищается
> система. Либо используйте venv (этот шаг), либо `python-pygame` из pacman,
> либо `pipx`. Флаг `--break-system-packages` применять не рекомендуется.

## 3. Проверка и запуск

```bash
python -c "from game.engine.world import World; print('OK: модули собраны')"
python -m game.engine.app
```

## 4. Wayland / X11 и Pipewire

Arch по умолчанию часто стоит на Wayland + Pipewire — всё поддерживается.
Если pygame-окно не появляется:

```bash
SDL_VIDEODRIVER=x11 python -m game.engine.app   # через XWayland
```

Без звука проверьте:

```bash
systemctl --user status pipewire pulseaudio    # должен быть активен хотя бы один
```

Headless (SSH/CI):

```bash
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python -m game.engine.app
```

## 5. AUR-путь (по желанию)

При желании игру можно упаковать как PKGBUILD и ставить через `yay`/`paru`
(сохранение при этом остаётся в `~/.abyss_economy_save.json`). Сборка из AUR
не требуется для запуска — достаточно шагов 1–3.

## 6. Неприятности и решения

| Симптом | Решение |
|---------|---------|
| `externally-managed-environment` | активируйте `.venv` или ставьте `python-pygame` из pacman |
| `ModuleNotFoundError: No module named 'game'` | запускайте из корня проекта (`cd` в папку с `game/`) |
| Окно не открывается на Wayland | `SDL_VIDEODRIVER=x11` (п. 4) |
| Partial upgrade / ключring после долгого перерыва | `sudo pacman -Sy archlinux-keyring && sudo pacman -Su` |

## 7. Деинсталляция

```bash
rm -rf ~/projects/economy-progress
rm -f ~/.abyss_economy_save.json
```

---
© 2026. Копирование и распространение регулируются [LICENSE](../../LICENSE).
