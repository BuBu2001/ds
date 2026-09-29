# 🎩 Установка на Fedora / RHEL / CentOS Stream (и производные: Nobara, Bazzite)

«Экономика и Прогрессия» — Souls-like рогалик на Python.
Общая инструкция: [INSTALL.md](../../INSTALL.md). Навигация: [index](README.md).

> Проверено на: Fedora Workstation 40/41. Для RHEL/CentOS Stream замените
> `dnf` на `yum` там, где он указан в старых ветках, пакеты те же.

> 💡 Быстрее всего — автоматический установщик в корне проекта:
> `bash setup.sh` (поддерживает Debian/Ubuntu, Arch, Fedora/RHEL, openSUSE, macOS).
> Ниже — ручная установка шаг за шагом.


---

## 1. Системные пакеты

```bash
sudo dnf install -y python3 python3-pip python3-virtualenv SDL2-devel libSDL2_image-devel libSDL2_mixer-devel gcc
```

| Пакет | Зачем |
|-------|-------|
| `python3-virtualenv` | venv в Fedora отдельным пакетом |
| `SDL2-devel` | заголовки/либы SDL2 для pygame |
| `gcc` | сборка pygame из исходников при необходимости |

Проверка:

```bash
python3 --version   # Fedora 38+ поставляет Python 3.12 — подходит
```

## 2. Виртуальное окружение и зависимости

```bash
cd ~/projects/economy-progress
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install pygame
```

Альтернатива без venv (через системный пакет):

```bash
sudo dnf install -y python3-pygame
```

Но `.venv` предпочтительнее — игра не зависит от обновлений RPM-базы.

## 3. Проверка и запуск

```bash
python -c "from game.engine.world import World; print('OK: модули собраны')"
python -m game.engine.app
```

## 4. Wayland / X11

Fedora по умолчанию Wayland. Если окно pygame ведёт себя нестабильно:

```bash
SDL_VIDEODRIVER=x11 python -m game.engine.app
```

Headless (сервер/CI):

```bash
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python -m game.engine.app
```

## 5. SELinux

На Fedora включён enforcing-SELinux. Запуск из домашней директории работает без
вмешательств. Если игру разместили в нестандартном пути (например, `/opt/game`)
и получили `PermissionError`:

```bash
sudo semanage fcontext -a -t bin_t '/opt/game(/.*)?'
sudo restorecon -Rv /opt/game
```

(обычному пользователю в `~/projects` это не требуется).

## 6. Неприятности и решения

| Симптом | Решение |
|---------|---------|
| `No module named virtualenv` | `sudo dnf install python3-virtualenv` |
| `pygame.error: Unable to open a console` | `sudo dnf install SDL2-devel`, либо headless-режим (п. 4) |
| Нет звука | Fedora использует PipeWire; проверьте `wpctl status` |
| Блокировки SELinux в логах | `sudo ausearch -m avc -ts recent` + п. 5 |

## 7. Деинсталляция

```bash
rm -rf ~/projects/economy-progress
rm -f ~/.abyss_economy_save.json
```

---
© 2026. Копирование и распространение регулируются [LICENSE](../../LICENSE).
