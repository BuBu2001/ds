# 📖 ИНСТРУКЦИЯ ПО УСТАНОВКЕ
«Экономика и Прогрессия» — Souls-like рогалик на Python (самописный движок)

> ℹ️ Это общая, дистрибутив-независимая инструкция. Отдельные пошаговые
> руководства для конкретных систем — в папке [`docs/install/`](docs/install/README.md):
>
> - 🐧 [Debian / Ubuntu / Linux Mint](docs/install/DEBIAN-UBUNTU.md)
> - 🏔️ [Arch Linux / EndeavourOS / Manjaro](docs/install/ARCH-LINUX.md)
> - 🎩 [Fedora / RHEL / CentOS Stream](docs/install/FEDORA-RHEL.md)
> - 🦎 [openSUSE Tumbleweed / Leap](docs/install/OPENSUSE.md)
> - 🍎 [macOS](docs/install/MACOS.md)
> - 🪟 [Windows 10/11](docs/install/WINDOWS.md)

---

## 0. Автоматическая установка (рекомендуется)

В корне проекта лежит скрипт [`setup.sh`](setup.sh), который сам определяет вашу
систему (Debian/Ubuntu, Arch, Fedora/RHEL, openSUSE, macOS), устанавливает все
системные и Python-зависимости, создаёт окружение `.venv`, проверяет целостность
сборки и запускает игру:

```bash
chmod +x setup.sh
./setup.sh              # установить, проверить и запустить
./setup.sh --no-run     # только установить и проверить (для CI / headless)
./setup.sh --uninstall  # удалить .venv и кэши сборки
./setup.sh --help       # справка
```

Если вы предпочитаете ручную установку или используете Windows — читайте разделы ниже.

---

## 1. Системные требования

| Компонент | Минимум | Рекомендовано |
|-----------|---------|---------------|
| ОС        | Linux (Ubuntu 20.04+, Fedora, Arch) / Windows 10+ | Linux |
| Python    | 3.10 | **3.12** |
| RAM       | 2 ГБ | 4 ГБ |
| GPU/DRM   | любая с поддержкой SDL2-софта | дискретная GPU |
| Диск      | ~50 МБ (код + генерируемые ассеты) | — |

## 2. Зависимости

Проект требует только **pygame** (ввод/рендер). Остальное — стандартная библиотека.

```bash
python3 -m pip install --upgrade pip
python3 -m pip install pygame
```

На Linux для корректной работы SDL2 могут понадобиться системные пакеты:

```bash
# Debian/Ubuntu
sudo apt update && sudo apt install -y libsdl2-dev python3-venv

# Fedora
sudo dnf install -y SDL2-devel python3-virtualenv
```

## 3. Установка (пошагово)

### Шаг 1. Получите файлы проекта
Скопируйте архив/папку проекта к себе (распространение файлов регулируется
файлом [LICENSE](LICENSE)):

```bash
mkdir -p ~/projects && cd ~/projects
# распакуйте архив игры сюда, например:
tar -xzf economy-and-progress.tar.gz -C economy-progress
cd economy-progress
```

### Шаг 2. Создайте виртуальное окружение (рекомендуется)

```bash
python3 -m venv .venv
source .venv/bin/activate          # Linux/macOS
# .venv\Scripts\activate           # Windows (cmd)
# & .venv\Scripts\Activate.ps1     # Windows (PowerShell)
```

### Шаг 3. Установите зависимости

```bash
pip install pygame
```

### Шаг 4. Проверьте целостность установки

```bash
python -c "from game.engine.world import World; print('OK: модули собраны')"
```

Должно вывести `OK: модули собраны`.

## 4. Запуск

```bash
python -m game.engine.app
```

Или, находясь в папке проекта:

```bash
python game/engine/app.py
```

Первый запуск генерирует подземелье (уровень 1) и открывает окно с костром.

## 5. Управление (по умолчанию, всё ремапится в настройках)

| Действие | Клавиша |
|----------|---------|
| Движение | `W A S D` |
| Камера | Мышь |
| Лёгкая атака | ЛКМ |
| Тяжёлая атака | ПКМ (удержание) |
| Рывок (додж) | `Shift` |
| Каст Огня | `Q` |
| Каст Льда | `E` |
| Взаимодействие (костёр, лут) | `F` |
| Инвентарь | `I` |
| Карта уровня | `M` |
| Зелье (быстрые слоты) | `1`–`4` |
| Пауза / закрыть экран | `ESC` |

## 6. Сохранения и настройки

- Сохранение метасостояния (Главный Костёр, Древо Талантов, NG+) пишется в
  единый файл `~/.abyss_economy_save.json` (константа `SAVE_PATH` в
  `game/meta/save_data.py`).
- Ремопы клавиш задаются в модуле `game/input/raw_input.py` / настройках UI.
- Чтобы начать «с нуля», удалите файл `~/.abyss_economy_save.json`.

## 7. Headless-режим (без окна, для проверки баланса)

```bash
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python -m game.engine.app
```

Используется в CI/смоук-тестах: логика мира работает без дисплея.

## 8. Структура проекта (модульность)

```
game/
├── core/         константы, стейт-машины, математика урона
├── data/         JSON-баланс: материалы, рецепты, перки, руны, лор
├── economy/      валюты (Угли/Осколки), крафт, дроп, NG+
├── generation/   A*-поиск, генератор данжей с валидацией связности
├── magic/        статусы, комбо, аномалии, перки, руны
├── entities/     игрок, мобы, элитки, маги
├── bosses/       4 босса + фабрика
├── meta/         Древо Талантов, Алтарь Наследий, сохранения, Кузница
├── input/        сырой ввод, ремап
├── ui/           рендерер, HUD, экраны (костёр, инвентарь, карта, смерть)
└── engine/       world.py (симуляция), app.py (главный цикл)
```

## 9. Устранение неполадок

| Симптом | Решение |
|---------|---------|
| `ModuleNotFoundError: No module named 'game'` | запускайте из корня проекта (`cd` в папку с `game/`) |
| `pygame.error: Unable to open a console` | запустите с `SDL_VIDEODRIVER=dummy` или установите SDL2 (п. 2) |
| Пустой чёрный экран | обновите видеодрайвер; попробуйте `SDL_RENDER_DRIVER=software` |
| Медленная генерация уровня | нормально для CPU-генератора; проверьте, что не включён режим отладки логов |
| Конфликт версий зависимостей | пересоздайте `.venv` (шаг 3.2) |

## 10. Деинсталляция

```bash
rm -rf ~/projects/economy-progress   # удалить игру
rm -f ~/.abyss_economy_save.json     # удалить сохранение
deactivate && rm -rf .venv           # удалить окружение
```

---

© 2026. Установка разрешена при соблюдении [LICENSE](LICENSE):
копирование, публикация и создание производных работ — запрещены.
