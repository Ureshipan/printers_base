# CLAUDE.md — PrinterBase: Система управления фермой 3D-принтеров

> **Проект:** Мониторинг и администрирование 25 FDM 3D-принтеров (Klipper + Moonraker).
> **Целевая платформа:** Raspberry Pi 4B (4GB RAM, ARM64).
> **Назначение:** Предприятие. Критична отказоустойчивость.

---

## Language Preferences
- **Chat:** Russian (Русский)
- **Code comments:** Russian (Русский)
- **Commits:** English (Conventional Commits)
- **Types:** feat, fix, refactor, test, docs, chore
- **Scopes:** api, db, moonraker, gcode, maintenance, spools, tasks, printers, notifications, deploy, infra

---

## Startup Command

```bash
git status && git log -n 3 --oneline
```

---

## Moonraker Integration & Documentation

**ВАЖНО:** В корне проекта находится папка `docs/`. В ней — **ОФИЦИАЛЬНАЯ документация Moonraker** (API reference).

**Правило работы (НЕ ОБСУЖДАЕТСЯ):**
1. При **ЛЮБОМ** упоминании Moonraker, написании запросов к API — **ОБЯЗАТЕЛЬНО** поиск по `docs/`.
2. Файлы большие — **НЕ читать целиком**. Используй Grep по конкретному endpoint.
3. **Приоритет:** `docs/` > знания модели. В `docs/` — актуальная документация Moonraker.
4. Если endpoint не найден в `docs/` — **СПРОСИ ПОЛЬЗОВАТЕЛЯ**, не придумывай.

---

## Commands

```bash
# Установка зависимостей
pip install -r requirements.txt

# Запуск (разработка)
python -m backend.api.web_interface
# Доступ: http://localhost:5000

# Запуск (продакшен / RPi 4B)
gunicorn --config gunicorn_config.py backend.api.web_interface:app

# Тесты
pytest tests/ --tb=short -q                              # Все тесты
pytest tests/unit/test_КОНКРЕТНЫЙ.py --tb=short -q       # Один файл (TDD)
pytest tests/ --cov=backend --cov-fail-under=70           # С покрытием

# Линтинг
ruff check backend/
ruff check --fix backend/

# CLI-инструменты
python backend/services/monitor_printer.py --host <IP> --interval 5
python backend/services/send_gcode.py --host <IP> --gcode "G28"
python backend/services/websocket_listener.py --host <IP>
python backend/services/moonraker_tool.py --host <IP>
```

---

## Sub-Agent Pipeline

```
implementation-coder (TDD: RED → GREEN → REFACTOR)
    ↓
moonraker-test-architect (реальные/mock запросы к Moonraker API)
    ↓
strict-qa-validator (SQLite, Flask, фоновые потоки, состояния принтеров)
    ↓
doc-architect (обновление документации)
```

### Orchestrator Rules (СТРОГО)

1. **Оркестратор НЕ пишет код** — делегирует `implementation-coder`.
2. **Промпт к кодеру ВСЕГДА начинается с `ultrathink`**.
3. **Оркестратор НЕ читает файлы**, которые создал/изменил субагент (экономия контекста).
4. **После кодера** — оркестратор запускает `pytest` (ТОЛЬКО конкретный тест-файл!).
5. **Валидация** — запуск `strict-qa-validator` перед любым коммитом.

---

## Architecture

```
Flask (web_interface.py)
    ├── REST API (44+ endpoints) → SQLite (data_model.py)
    ├── Background threads:
    │   ├── update_printer_states_loop() — опрос Moonraker API
    │   └── monitor_printing_tasks() — отслеживание заданий
    └── Moonraker API → 3D Printers (Klipper)
```

### Key Components

| Файл | Назначение | Строк |
|------|-----------|-------|
| `backend/api/web_interface.py` | Flask приложение, REST API, фоновые потоки | ~2300 |
| `backend/db/data_model.py` | SQLAlchemy ORM, DBModel (все CRUD операции) | ~1200 |
| `backend/services/gcode_parser.py` | Парсер G-code (OrcaSlicer, Cura) | ~390 |
| `backend/services/moonraker_tool.py` | CLI для интерактивного управления | ~480 |
| `backend/services/health.py` | Circuit Breaker для принтеров (TODO) | — |
| `backend/services/notifications.py` | Telegram/Email уведомления (TODO) | — |

### ORM Models (data_model.py)

| Модель | Описание |
|--------|----------|
| `Printer` | Физические и виртуальные принтеры (is_virtual, print_hours, nozzle_diameter) |
| `Task` | Задачи печати с G-code файлами, прогрессом, трекингом |
| `Project` | Группировка задач (проекты) |
| `Vendor` | Производитель филамента |
| `Filament` | Тип филамента (материал, цвет, плотность) |
| `Coil` | Физическая катушка (остаток, история использования) |
| `SpoolHistory` | Журнал расхода материала |
| `MaintenanceType` | Типы ТО (сопло, ролики, экструдер) |
| `MaintenanceRecord` | Записи о проведённом ТО |
| `Material` | (deprecated, заменён на Filament) |

### API Endpoints (44+)

**Pages:** `GET /`, `/planning`, `/printer-control`, `/maintenance`, `/spools`

**Printers:** `GET/POST /api/printers`, `GET/PUT/DELETE /api/printers/<id>`, `POST /api/printers/virtual`

**Tasks:** `GET/POST /api/tasks`, `GET/PUT/PATCH/DELETE /api/tasks/<id>`, `POST/GET/DELETE /api/tasks/<id>/gcode`

**Print Control:** `POST /api/tasks/<id>/print/start|pause|resume|cancel`

**Projects:** `GET/POST /api/projects`, `GET/PUT/PATCH/DELETE /api/projects/<id>`

**Coils:** `GET/POST /api/coils`, `GET/PUT/DELETE /api/coils/<id>`, `POST /api/coils/<id>/archive|adjust`

**Maintenance:** `GET /api/maintenance/types|status|upcoming`, `POST /api/maintenance/records`

**Control:** `POST /api/command`, `POST /api/home`, `POST /api/temperature`

---

## Data Flow

1. Фоновый поток `update_printer_states_loop()` опрашивает Moonraker API (сверяясь с `docs/`).
2. Состояния кешируются в `printer_states: Dict[int, Dict]` с `threading.Lock`.
3. Frontend получает данные через REST API (`/api/state`, `/api/printers`).
4. Виртуальные принтеры возвращают статус из БД без сетевых запросов.
5. При завершении печати — автоматическое списание материала с катушки.

### State Machine (Printer)

```
idle → printing → complete → awaiting_removal → idle
  ↓         ↓                                     ↑
  └→ error ←┘ ────────→ maintenance ──────────────┘
```

### State Map (Moonraker → App)

| Moonraker state | App state |
|-----------------|-----------|
| "printing" | "work" |
| "paused" | "idle" |
| "standby" | "idle" |
| "complete" | "awaiting_removal" |
| "error" | "error" |
| "offline" | "offline" |

---

## Environment Variables

```env
MOONRAKER_PORT=7125              # Порт Moonraker (default: 7125)
MOONRAKER_DEFAULT_HOST=...       # Fallback хост для Moonraker
PRINTER_DISCOVERY_ENABLED=0      # Автопоиск принтеров в сети (default: отключён)
PRINTER_DISCOVERY_INTERVAL=60    # Интервал автопоиска (сек)
PRINTER_STATE_INTERVAL=1.0       # Интервал опроса состояний (сек)
TELEGRAM_BOT_TOKEN=              # Telegram бот для уведомлений (TODO)
TELEGRAM_CHAT_ID=                # Chat ID для уведомлений (TODO)
```

---

## Database

- **SQLite:** `backend/db/database.db` — создаётся автоматически при старте.
- **WAL mode** — обязателен для конкурентного доступа (фоновый поток + API).
- **Миграции:** `DBModel._ensure_schema()` — добавляет недостающие колонки/таблицы.
- **Загрузки:** `backend/uploads/gcode/` — G-code файлы (макс 200MB).

---

## Testing Rules (СТРОГО)

### Scope тестов (КРИТИЧЕСКИ ВАЖНО!)

```bash
# На шагах TDD (RED/GREEN/REFACTOR) — ТОЛЬКО свой тест-файл:
pytest tests/unit/test_КОНКРЕТНЫЙ.py --tb=short -q

# Промежуточная проверка (каждые 3-4 шага):
pytest tests/unit/ --tb=no -q 2>&1 | tail -10

# Перед коммитом (ОДИН РАЗ):
pytest --tb=short -q
```

**ЗАПРЕЩЕНО:**
- `pytest -v` после каждого шага
- Запуск всех тестов внутри TDD-цикла
- Фиктивные тесты (assert True)

### Test Patterns

| Тип | Директория | Описание |
|-----|-----------|----------|
| Unit | `tests/unit/` | Изолированные тесты (tmpdir SQLite, mock HTTP) |
| Integration | `tests/integration/` | Flask test client + тестовая БД |
| E2E | `tests/e2e/` | Mock Moonraker server + полный flow |

### Fixtures (conftest.py)

```python
@pytest.fixture
def db(tmp_path):
    """Тестовая SQLite БД в tmpdir — не трогает продакшен."""
    return DBModel(db_path=str(tmp_path / "test.db"))

@pytest.fixture
def client(db):
    """Flask test client с тестовой БД."""
    app.config['TESTING'] = True
    # Подставляем тестовую БД
    with app.test_client() as client:
        yield client
```

---

## Target Platform: Raspberry Pi 4B

### Hardware Constraints
- **CPU:** BCM2711, 4× Cortex-A72 @ 1.5GHz (ARM64)
- **RAM:** 4GB LPDDR4
- **Storage:** microSD (High Endurance) или USB SSD
- **OS:** Raspberry Pi OS (Bookworm, 64-bit)

### Production Stack
```
Nginx (reverse proxy, static files)
    └── Gunicorn (gthread, 2 workers × 4 threads)
        └── Flask app (PrinterBase)
            └── SQLite (WAL mode, PRAGMA-оптимизации)
```

### SD-Card Protection
- WAL mode + `synchronous=NORMAL` — минимум записей
- tmpfs для `/tmp` и `/var/log`
- `noatime` + `commit=600` в fstab
- log2ram для логов
- Рекомендуется USB SSD для БД

### systemd
- `Restart=on-failure`, `RestartSec=5s`
- `MemoryMax=512M`, `CPUQuota=80%`
- `RuntimeMaxSec=86400` — принудительный перезапуск раз в сутки

---

## Safety Rules (НЕ ОБСУЖДАЕТСЯ)

### ❌ NEVER:
- Запускать Flask dev server в продакшене
- Использовать `print()` вместо `logging`
- Придумывать Moonraker API endpoints (смотри `docs/`)
- Писать код без предварительного чтения существующего
- Коммитить `.env`, `database.db`, `uploads/`
- Добавлять необоснованные абстракции или over-engineering
- Запускать все тесты при каждом мелком изменении

### ✅ ALWAYS:
- Читать существующий код перед модификацией
- Следовать TDD: RED → GREEN → REFACTOR
- Использовать type hints (PEP 8)
- Писать комментарии на русском
- Сверяться с `docs/` при работе с Moonraker
- Учитывать ограничения RPi 4B (RAM, SD-карта)
- Проверять thread safety при работе с shared state

---

## Plan

Подробный план доработки: **`PLAN.md`** в корне проекта.
