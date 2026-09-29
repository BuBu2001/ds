# 📚 Руководства по установке — навигация

«Экономика и Прогрессия» (Souls-like рогалик на Python).
Выберите руководство под вашу систему:

| Система / дистрибутив | Пакетный менеджер | Руководство |
|-----------------------|-------------------|-------------|
| Debian, Ubuntu, Linux Mint, Pop!_OS, Zorin | `apt` | [DEBIAN-UBUNTU.md](DEBIAN-UBUNTU.md) |
| **Arch Linux**, EndeavourOS, Manjaro, Garuda | `pacman` | [ARCH-LINUX.md](ARCH-LINUX.md) |
| Fedora, RHEL, CentOS Stream, Nobara | `dnf` | [FEDORA-RHEL.md](FEDORA-RHEL.md) |
| openSUSE Tumbleweed / Leap | `zypper` | [OPENSUSE.md](OPENSUSE.md) |
| macOS (Intel / Apple Silicon) | `brew` | [MACOS.md](MACOS.md) |
| Windows 10 / 11 | `python.org` + pip | [WINDOWS.md](WINDOWS.md) |

Общая (дистро-независимая) инструкция со структурой проекта, управлением и
устранением неполадок: [../../INSTALL.md](../../INSTALL.md).

## Если вашей системы нет в списке

Логика установки одинакова для всех Unix-систем:

1. Python ≥ 3.10 + SDL2 (`sdl2`, `libsdl2`, `SDL2-devel` — как называется пакет
   в вашем репозитории);
2. виртуальное окружение: `python3 -m venv .venv && source .venv/bin/activate`;
3. `pip install pygame`;
4. запуск из корня проекта: `python -m game.engine.app`.

Сохранение всегда в `~/.abyss_economy_save.json`; headless-режим —
через `SDL_VIDEODRIVER=dummy`.

---
© 2026. Копирование и распространение регулируются [LICENSE](../../LICENSE).
