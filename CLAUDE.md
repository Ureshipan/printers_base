# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Language Preferences
- Chat: Russian (Русский)
- Code comments: Russian (Русский)
- Commits: English (Conventional Commits)

## Moonraker Integration & Documentation
**ВАЖНО:** В корне проекта находится папка `docs/`. В ней содержится вся **ОФИЦИАЛЬНАЯ документация по Moonraker**, включая справочник по API.

**Правило работы:**
При любом упоминании Moonraker, написании запросов к API или реализации взаимодействия с ним:
1. **ОБЯЗАТЕЛЬНО** выполни поиск по файлам в папке `docs/`.
2. Сверяй эндпоинты, методы и структуру данных с этой документацией.
3. Отдавай приоритет информации из локальной папки `docs/` перед общими знаниями модели.

## Commands

```bash
# Установка зависимостей
pip install -r requirements.txt

# Запуск веб-интерфейса (основная точка входа)
python -m backend.api.web_interface
# Доступ: http://localhost:5000

# CLI-инструменты (отдельные скрипты)
python backend/services/monitor_printer.py --host <IP> --interval 5
python backend/services/send_gcode.py --host <IP> --gcode "G28"
python backend/services/websocket_listener.py --host <IP>
python backend/services/moonraker_tool.py --host <IP>
```

## Architecture

```
Flask (web_interface.py)
    ├── REST API → SQLite (data_model.py)
    └── Moonraker API → 3D Printers (Klipper)
```

### Key Components

**backend/api/web_interface.py** — Flask приложение, точка входа. Маршруты:
- `/` — dashboard, `/planning` — задачи, `/printer-control` — управление
- API: `/api/printers`, `/api/tasks`, `/api/projects`, `/api/state`, `/api/command`

**backend/db/data_model.py** — SQLAlchemy ORM модели:
- `Printer` — физические и виртуальные принтеры (is_virtual, virtual_status)
- `Task` — задачи печати с G-code файлами
- `Project`, `Coil`, `Material` — группировка и расходники

**backend/services/** — CLI-инструменты для работы с Moonraker API:
- `moonraker_tool.py` — интерактивное управление принтером
- `monitor_printer.py` — мониторинг состояния
- `send_gcode.py` — отправка G-code команд
- `websocket_listener.py` — real-time события

**discovery/** — автопоиск принтеров в сети (по умолчанию отключён)

### Data Flow

1. Фоновый поток `update_printer_states_loop()` опрашивает Moonraker API (сверяясь с `docs/`).
2. Состояния кешируются в `printer_states: Dict[int, Dict]` с блокировкой
3. Frontend получает данные через REST API (`/api/state`, `/api/printers`)
4. Виртуальные принтеры возвращают статус из БД без сетевых запросов

### Environment Variables

```
MOONRAKER_PORT=7125              # Порт Moonraker
MOONRAKER_DEFAULT_HOST=...       # Fallback хост
PRINTER_DISCOVERY_ENABLED=0      # Автопоиск (отключён)
PRINTER_STATE_INTERVAL=1.0       # Интервал опроса (сек)
```

### Database

SQLite: `backend/db/database.db` — создаётся автоматически при старте.
Миграции колонок выполняются в `DBModel._ensure_columns()`.