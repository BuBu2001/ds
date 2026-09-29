# 🐧 Установка на openSUSE (Tumbleweed / Leap)

«Экономика и Прогрессия» — Souls-like рогалик на Python.
Общая инструкция: [INSTALL.md](../../INSTALL.md). Навигация: [index](README.md).

> 💡 Быстрее всего — автоматический установщик в корне проекта:
> `bash setup.sh` (поддерживает Debian/Ubuntu, Arch, Fedora/RHEL, openSUSE, macOS).
> Ниже — ручная установка шаг за шагом.


---

## 1. Системные пакеты

```bash
sudo zypper install -y python3 python3-pip python3-venv sdl2-devel libSDL2_image-devel libSDL2_mixer-devel patterns_devel_C_c++_compiler
```

Короткий вариант без паттернов:

```bash
sudo zypper install -y python3 python3-pip python3-venv sdl2-devel gcc
```

## 2. Виртуальное окружение и зависимости

```bash
cd ~/projects/economy-progress
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install pygame
```

Альтернатива из репозитория: `sudo zypper install python3-pygame`.

## 3. Проверка и запуск

```bash
python -c "from game.engine.world import World; print('OK: модули собраны')"
python -m game.engine.app
```

Headless: `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python -m game.engine.app`

## 4. Особенности

- Tumbleweed (rolling) сопоставим с Arch: всегда свежий Python, PEP 668 может
  защищать системный site-packages — используйте `.venv`.
- Leap 15.x несёт старый Python 3.6 в базе — поставьте `python311` через
  `zypper install python311 python311-pip` и создавайте venv им:
  `python3.11 -m venv .venv`.
- Wayland по умолчанию в Tumbleweed; при проблемах с окном —
  `SDL_VIDEODRIVER=x11`.

## 5. Деинсталляция

```bash
rm -rf ~/projects/economy-progress
rm -f ~/.abyss_economy_save.json
```

---
© 2026. Копирование и распространение регулируются [LICENSE](../../LICENSE).
