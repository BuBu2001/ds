# 🕯️ ЭКОНОМИКА И ПРОГРЕССИЯ

**Souls-like рогалик на Python с самописным движком и процедурной экономикой.**

> *«Угли гаснут. Осколки помнят.»*

- 📖 Обложка и синопсис — [COVER.md](COVER.md)
- 📥 Установка и запуск — [INSTALL.md](INSTALL.md)
- 🐧 Отдельные руководства: [Debian/Ubuntu](docs/install/DEBIAN-UBUNTU.md) ·
  [Arch Linux](docs/install/ARCH-LINUX.md) · [Fedora/RHEL](docs/install/FEDORA-RHEL.md) ·
  [openSUSE](docs/install/OPENSUSE.md) · [macOS](docs/install/MACOS.md) · [Windows](docs/install/WINDOWS.md)
- ⚖️ Лицензия (копирование запрещено) — [LICENSE](LICENSE)

## Кратко
15 уровней подземелья (+ секретный 20-й в NG+2), две валюты (Угли/Осколки),
комбо-магия, костры-хабы, death penalty с призраком, стейт-машины для всех
сущностей, мета-прогрессия и NG+ с модификаторами правил.

## Быстрый старт
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install pygame
python -m game.engine.app
```

## Структура (модульная)
`game/core · data · economy · generation · magic · entities · bosses · meta · input · ui · engine`

---
© 2026. Все права защищены. Использование файлов проекта регулируется
лицензией [LICENSE](LICENSE): копирование, распространение и создание
производных работ без письменного разрешения правообладателя запрещены.
