# 🪟 Установка на Windows 10 / 11

«Экономика и Прогрессия» — Souls-like рогалик на Python.
Общая инструкция: [INSTALL.md](../../INSTALL.md). Навигация: [index](README.md).

---

## 1. Установите Python

Скачайте установщик с https://python.org (версия ≥ 3.10, например 3.12) и при
установке отметьте **«Add python.exe to PATH»**. Проверка:

```powershell
python --version
```

## 2. Получите файлы проекта

Распакуйте архив игры, например в `C:\Games\economy-progress`.
(Распространение файлов регулируется [LICENSE](../../LICENSE).)

## 3. Виртуальное окружение и pygame

**PowerShell:**

```powershell
cd C:\Games\economy-progress
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install pygame
```

**cmd:**

```bat
cd C:\Games\economy-progress
python -m venv .venv
\.venv\Scripts\activate.bat
pip install pygame
```

> Если PowerShell блокирует скрипты:
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

SDL2 для pygame на Windows **не требуется** — бинарные wheels включают всё необходимое.

## 4. Проверка и запуск

```powershell
python -c "from game.engine.world import World; print('OK: модули собраны')"
python -m game.engine.app
```

Headless: `$env:SDL_VIDEODRIVER='dummy'; python -m game.engine.app`

## 5. Деинсталляция

Удалите папку `C:\Games\economy-progress` и сохранение
`%USERPROFILE%\.abyss_economy_save.json`.

---
© 2026. Копирование и распространение регулируются [LICENSE](../../LICENSE).
