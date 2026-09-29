# 🐧 Установка на Debian / Ubuntu (и производные: Linux Mint, Pop!_OS, Zorin)

«Экономика и Прогрессия» — Souls-like рогалик на Python.
Общая инструкция: [INSTALL.md](../../INSTALL.md). Навигация по руководствам: [index](README.md).

> Проверено на: Debian 12 (bookworm), Ubuntu 22.04 / 24.04 LTS, Linux Mint 21+.

> 💡 Быстрее всего — автоматический установщик в корне проекта:
> `bash setup.sh` (поддерживает Debian/Ubuntu, Arch, Fedora/RHEL, openSUSE, macOS).
> Ниже — ручная установка шаг за шагом.


---

## 1. Системные пакеты

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip libsdl2-dev libsdl2-image-dev libsdl2-mixer-dev build-essential
```

| Пакет | Зачем |
|-------|-------|
| `python3` | интерпретатор (нужен ≥ 3.10) |
| `python3-venv` | виртуальные окружения (в Debian идут отдельным пакетом) |
| `libsdl2-dev` | SDL2 — бэкенд pygame для окна и ввода |
| `build-essential` | компилятор на случай сборки pygame из исходников |

Проверка версии Python:

```bash
python3 --version   # должно быть >= 3.10
```

На **Debian 11/Ubuntu 20.04** системный Python может быть 3.9 — установите новый:

```bash
sudo apt install -y software-properties-common
sudo add-apt-repository ppa:deadsnakes/ppa     # только Ubuntu
sudo apt install -y python3.12 python3.12-venv
```

## 2. Виртуальное окружение и зависимости

```bash
cd ~/projects/economy-progress        # папка с игрой
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install pygame
```

> ⚠️ На Debian 12 / Ubuntu 24.04 включён PEP 668 («externally-managed
> environment»). Не ставьте пакеты через `sudo apt install python3-pygame` в
> системный Python — используйте `.venv`, как выше. Ошибка
> `error: externally-managed-environment` означает, что окружение не активировано.

## 3. Проверка и запуск

```bash
python -c "from game.engine.world import World; print('OK: модули собраны')"
python -m game.engine.app
```

## 4. Wayland / X11

Игра работает под обоими серверами дисплея. Если на Wayland окно не появляется
или мышь «дёргается», форсируйте X11-бэкенд SDL:

```bash
GDK_BACKEND=x11 SDL_VIDEODRIVER=x11 python -m game.engine.app
```

Без монитора (SSH, CI):

```bash
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python -m game.engine.app
```

## 5. Неприятности и решения

| Симптом | Решение |
|---------|---------|
| `The virtual environment was not created successfully` | `sudo apt install python3-venv` |
| `externally-managed-environment` | активируйте `.venv` (`source .venv/bin/activate`) |
| `pygame.error: Unable to open a console` | установите `libsdl2-dev`, либо запустите headless (п. 4) |
| Нет звука | `sudo apt install libasound2-plugins pipewire-pulse` |

## 6. Деинсталляция

```bash
rm -rf ~/projects/economy-progress
rm -f ~/.abyss_economy_save.json
```

---
© 2026. Копирование и распространение регулируются [LICENSE](../../LICENSE).
