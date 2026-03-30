# PLAN: Доработка системы управления фермой 3D-принтеров

> **Цель:** Довести проект до enterprise-уровня: отказоустойчивость, тесты, деплой на Raspberry Pi 4B.
> **Метод:** TDD + полный пайплайн субагентов (implementation-coder → moonraker-test-architect → strict-qa-validator → doc-architect).
> **Целевая платформа:** Raspberry Pi 4B (4GB RAM, ARM64, Raspberry Pi OS).
> **Тестовое окружение:** WSL2 (локально).
> **Текущее состояние:** Ветка `5-integrate-data-model-with-services`, 15 коммитов поверх main, ~85% ТЗ.
> **Дата составления:** 2026-03-30.

---

## КОНТЕКСТ ПРОЕКТА

### Оборудование (из ТЗ)
- 25 FDM 3D-принтеров: Creality Ender 3 (10 шт), Flying Bear Ghost 6 (14 шт), Hercules G4 (1 шт)
- Все принтеры прошиты Klipper + Moonraker
- Среднее время печати 1 изделия: 1-4 часа
- Пользователи: студенты + персонал предприятия

### Архитектура
```
Flask (web_interface.py) — 2300+ строк, ТРЕБУЕТ ДЕКОМПОЗИЦИИ
    ├── REST API (44+ эндпоинтов)
    ├── SQLite (data_model.py, 1200+ строк)
    ├── Background threads (опрос принтеров, мониторинг задач)
    └── Moonraker API → 3D-принтеры (Klipper)
```

### Критические проблемы (выявлены при аудите)
1. **Нет WSGI-сервера** — Flask dev server в продакшене
2. **Нет WAL mode** для SQLite — `database is locked` при конкурентном доступе
3. **Последовательный опрос** принтеров — 25 принтеров × 2 сек timeout = до 50 сек
4. **Нет Circuit Breaker** — один зависший принтер блокирует мониторинг
5. **Нет тестов** — ни одного unit/integration/e2e теста
6. **web_interface.py = 2300+ строк** — монолит, невозможно поддерживать
7. **Нет логирования** — print() вместо structured logging
8. **Нет retry/backoff** — при сбое Moonraker API запрос просто падает
9. **SD-карта** на RPi — износ при частой записи SQLite

---

## ⛔ ГЛОБАЛЬНЫЕ ПРАВИЛА

### Правило чистого контекста
> **Каждый шаг = отдельный вызов оркестратора (чистый контекст!).**
> Каждый шаг ОБЯЗАН содержать полный контекст: пути к файлам, предусловия, ожидаемый результат.
> **ЗАПРЕЩЕНО**: "см. ШАГ X", "аналогично предыдущему", "как было выше".

### Правило субагента-кодера
> Промпт к **implementation-coder** ВСЕГДА начинается со слова **`ultrathink`**.
> Оркестратор НЕ пишет код сам — делегирует кодеру.
> После кодера — оркестратор запускает `pytest` для проверки (ТОЛЬКО конкретный тест-файл!).
> Оркестратор НЕ читает файлы, которые создал/изменил кодер — экономия контекста.

### Правило тестирования
> **НЕ запускать все тесты при каждом изменении!**
>
> | Ситуация | Команда |
> |----------|---------|
> | TDD-цикл кодера | `pytest tests/unit/test_КОНКРЕТНЫЙ.py --tb=short -q` |
> | Промежуточная проверка | `pytest tests/unit/ --tb=no -q 2>&1 \| tail -10` |
> | Перед коммитом (1 раз) | `pytest --tb=short -q` |

### Правило Moonraker API
> При любом взаимодействии с Moonraker API — **ОБЯЗАТЕЛЬНО** сверяться с `docs/` (локальная документация).
> Приоритет: `docs/` > знания модели. В `docs/` — официальная документация Moonraker.

### Целевая платформа
> **Raspberry Pi 4B** (4GB RAM, ARM Cortex-A72, SD-карта / USB SSD).
> Все решения принимаются с учётом ограничений: RAM, CPU, износ SD-карты.
> Тестирование — локально под WSL2, деплой — на RPi через systemd.

---

## СВОДНАЯ ТАБЛИЦА ФАЗ

| Фаза | Название | Приоритет | Статус |
|------|----------|-----------|--------|
| 0 | Инфраструктура и инструменты | P0 | ✅ Завершено |
| 1 | Критические исправления | P0 | ✅ Завершено |
| 2 | Декомпозиция и архитектура | P1 | ✅ Завершено |
| 3 | Тестирование | P1 | 🔶 Частично (90 тестов, 52% coverage) |
| 3.5 | Фронтенд: UX и производительность | P1 | 🔶 Частично |
| 4 | Недостающий функционал по ТЗ | P2 | ⬜ Не начато |
| 5 | Деплой и эксплуатация на RPi 4B | P2 | ⬜ Не начато |

---

## ФАЗА 0: Инфраструктура и инструменты

> **Цель:** Настроить окружение разработки, линтинг, структуру тестов.
> **Результат:** Проект готов к TDD-разработке с автоматической проверкой кода.

### ШАГ 0.1 — Создать pyproject.toml

**Файлы:** создать `pyproject.toml` в корне проекта.

**Содержание:**
```toml
[project]
name = "printers-base"
version = "1.0.0"
description = "3D Printer Farm Management System"
requires-python = ">=3.9"

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = "--tb=short -q"

[tool.ruff]
line-length = 120
target-version = "py39"

[tool.ruff.lint]
select = ["E", "F", "W", "I"]
ignore = ["E501"]

[tool.mypy]
python_version = "3.9"
warn_return_any = true
warn_unused_ignores = true
```

**Проверка:** `ruff check backend/` должен пройти (с warnings).

---

### ШАГ 0.2 — Обновить requirements.txt

**Файл:** `requirements.txt`

**Добавить:**
```
# Продакшен
gunicorn>=21.0.0

# Тестирование
pytest>=8.0.0
pytest-cov>=4.0.0
responses>=0.25.0

# Качество кода
ruff>=0.4.0

# Логирование
python-json-logger>=2.0.0

# Retry/resilience
tenacity>=8.0.0
```

**Убедиться:** все зависимости устанавливаются: `pip install -r requirements.txt`

---

### ШАГ 0.3 — Создать структуру тестов

**Создать директории и файлы:**
```
tests/
├── __init__.py
├── conftest.py              # Общие фикстуры (test DB, Flask test client)
├── unit/
│   ├── __init__.py
│   ├── test_data_model.py   # Тесты ORM и DBModel
│   └── test_gcode_parser.py # Тесты парсера G-code
├── integration/
│   ├── __init__.py
│   └── test_api.py          # Тесты Flask API endpoints
└── e2e/
    ├── __init__.py
    └── test_moonraker.py    # Тесты с mock Moonraker
```

**conftest.py:** фикстура `db` — создаёт тестовую SQLite БД в tmp_path. Фикстура `client` — Flask test client с тестовой БД.

**Проверка:** `pytest --collect-only` показывает структуру тестов.

---

### ШАГ 0.4 — Настроить .gitignore

**Файл:** `.gitignore`

**Добавить:**
```
# Python
__pycache__/
*.py[cod]
*.egg-info/
.eggs/
dist/
build/

# Testing
.pytest_cache/
htmlcov/
.coverage

# IDE
.vscode/
.idea/

# Environment
.env
*.db

# Uploads
backend/uploads/gcode/*
!backend/uploads/gcode/.gitkeep

# RPi specific
*.log
```

---

## ФАЗА 1: Критические исправления (P0)

> **Цель:** Устранить блокирующие проблемы: стабильность БД, WSGI-сервер, error handling.
> **Результат:** Приложение работает стабильно под нагрузкой (25 принтеров).

### ШАГ 1.1 — SQLite WAL mode + PRAGMA оптимизации

**Файл:** `backend/db/data_model.py`

**Проблема:** Строка `self.engine = create_engine(f'sqlite:///{self.db_path}')` — нет WAL mode, нет PRAGMA, нет настройки пула. При конкурентном доступе (фоновый поток обновления + Flask API) — `database is locked`.

**Решение:**
```python
from sqlalchemy import event

engine = create_engine(
    f'sqlite:///{db_path}',
    pool_size=5,
    max_overflow=0,
    connect_args={
        "check_same_thread": False,
        "timeout": 15,
    },
)

@event.listens_for(engine, "connect")
def _set_sqlite_pragmas(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA cache_size=-8000")        # 8MB кэш
    cursor.execute("PRAGMA temp_store=MEMORY")
    cursor.execute("PRAGMA mmap_size=67108864")       # 64MB mmap
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()
```

**Почему WAL критичен:** Позволяет одновременное чтение (фоновый поток) и запись (API), без `database is locked`.
**Почему `synchronous=NORMAL`:** В 2-3 раза меньше записей на SD-карту. При WAL потеря — только последняя транзакция при внезапном выключении.

**Тест:** `tests/unit/test_data_model.py::test_concurrent_read_write`

---

### ШАГ 1.2 — Structured logging вместо print()

**Файлы:** `backend/api/web_interface.py`, `backend/db/data_model.py`, `backend/services/*.py`

**Проблема:** Везде `print()` — нет уровней, нет timestamps, нет structured output.

**Решение:** Заменить все `print()` на `logging`:
```python
import logging
logger = logging.getLogger(__name__)

# Конфигурация в точке входа (web_interface.py):
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
```

**Правила:**
- `logger.error()` — ошибки Moonraker API, БД, критические
- `logger.warning()` — таймауты, принтер offline, degraded state
- `logger.info()` — смена статуса принтера, начало/конец печати
- `logger.debug()` — каждый poll цикл, детали запросов

**Тест:** интеграционный тест проверяет что логи пишутся при ошибке принтера.

---

### ШАГ 1.3 — Gunicorn + конфигурация для RPi 4B

**Файлы:** создать `gunicorn_config.py` в корне проекта.

**Содержание:**
```python
# gunicorn_config.py — оптимизирован для Raspberry Pi 4B (4GB RAM)
bind = "0.0.0.0:5000"
workers = 2                    # RPi 4B: 4 ядра, но RAM ограничена
worker_class = "gthread"       # Потоки — экономнее RAM чем fork
threads = 4                    # 4 потока на воркер = 8 concurrent requests
timeout = 60                   # Загрузка G-code может быть долгой
graceful_timeout = 30
max_requests = 500             # Recycling воркеров — борьба с утечками
max_requests_jitter = 50
preload_app = True             # Экономия RAM через copy-on-write
accesslog = "-"
errorlog = "-"
loglevel = "warning"
```

**Запуск:** `gunicorn --config gunicorn_config.py backend.api.web_interface:app`

**Важно:** `gthread` + `preload_app = True` — критично для RPi 4B. Потоки разделяют память, preload даёт copy-on-write.

---

### ШАГ 1.4 — Retry + exponential backoff для Moonraker API

**Файл:** `backend/api/web_interface.py` (функции `moonraker_get()`, `moonraker_post()`)

**Проблема:** При сбое Moonraker API — запрос просто падает с исключением. Нет retry, нет backoff.

**Решение:** Использовать `tenacity`:
```python
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout)),
    reraise=True,
)
def moonraker_request(host, port, endpoint, method="GET", payload=None, timeout=5):
    ...
```

**Тест:** `tests/unit/test_moonraker_client.py::test_retry_on_timeout`

---

### ШАГ 1.5 — Circuit Breaker для каждого принтера

**Файл:** создать `backend/services/health.py`

**Проблема:** Один зависший принтер (timeout 2 сек) блокирует опрос остальных. При 25 принтерах — до 50 секунд на цикл.

**Решение:** Circuit Breaker + per-printer health state:
```python
@dataclass
class PrinterHealthState:
    consecutive_failures: int = 0
    circuit_open: bool = False
    backoff_until: float = 0
    MAX_FAILURES: int = 5
    MAX_BACKOFF: float = 60.0

    def record_failure(self): ...
    def record_success(self): ...
    def should_skip(self) -> bool: ...
```

**Интеграция:** `update_printer_states_loop()` проверяет `should_skip()` перед опросом каждого принтера.

**Тест:** `tests/unit/test_health.py::test_circuit_breaker_opens_after_failures`

---

### ШАГ 1.6 — Параллельный опрос принтеров (ThreadPoolExecutor)

**Файл:** `backend/api/web_interface.py`, функция `update_printer_states_loop()`

**Проблема:** Принтеры опрашиваются последовательно. 25 принтеров × 2 сек timeout = до 50 сек.

**Решение:**
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

executor = ThreadPoolExecutor(max_workers=10)

def update_printer_states_loop():
    while True:
        active_printers = db.get_printers(include_inactive=False)
        futures = {
            executor.submit(fetch_printer_state, p): p.id
            for p in active_printers
            if not printer_health[p.id].should_skip()
        }
        for future in as_completed(futures, timeout=15):
            printer_id = futures[future]
            try:
                state = future.result()
                with printer_state_lock:
                    printer_states[printer_id] = state
            except Exception:
                logger.exception("Ошибка опроса принтера %s", printer_id)
        time.sleep(PRINTER_STATE_INTERVAL)
```

**Результат:** 25 принтеров опрашиваются за ~2 сек вместо ~50 сек.

**Тест:** `tests/integration/test_polling.py::test_parallel_polling_faster_than_sequential`

---

## ФАЗА 2: Декомпозиция и архитектура (P1)

> **Цель:** Разбить монолитный web_interface.py на модули. Добавить blueprints.
> **Результат:** Каждый модуль < 300 строк, легко тестировать и поддерживать.

### ШАГ 2.1 — Выделить Moonraker-клиент в отдельный модуль

**Создать:** `backend/services/moonraker_client.py`

**Перенести из web_interface.py:**
- `moonraker_get()`, `moonraker_post()`
- `_request_with_fallback()`
- `fetch_printer_state()`
- `upload_gcode_to_printer()`, `start_print_on_printer()`, `pause_print_on_printer()`, и т.д.
- `get_printer_print_status()`

**Результат:** Класс `MoonrakerClient` с методами для всех операций с Moonraker API.

**Тест:** `tests/unit/test_moonraker_client.py` — mock HTTP responses.

---

### ШАГ 2.2 — Flask Blueprints для API

**Создать:**
```
backend/api/
├── __init__.py
├── app.py                    # Фабрика приложения create_app()
├── blueprints/
│   ├── __init__.py
│   ├── printers.py           # /api/printers/*
│   ├── tasks.py              # /api/tasks/*
│   ├── projects.py           # /api/projects/*
│   ├── coils.py              # /api/coils/*, /api/vendors/*, /api/filaments/*
│   ├── maintenance.py        # /api/maintenance/*
│   ├── control.py            # /api/command, /api/home, /api/temperature
│   └── pages.py              # HTML-страницы (/, /planning, и т.д.)
└── web_interface.py           # Только точка входа (import app from app.py)
```

**Почему:** web_interface.py = 2300+ строк. Невозможно поддерживать, тестировать, ревьюить.
**Результат:** Каждый blueprint < 300 строк. Легко тестировать изолированно.

---

### ШАГ 2.3 — Выделить фоновые задачи в отдельный модуль

**Создать:** `backend/services/background.py`

**Перенести из web_interface.py:**
- `update_printer_states_loop()`
- `monitor_printing_tasks()`
- `handle_print_complete()`, `handle_print_error()`, `handle_print_cancelled()`
- `start_background_threads()`

**Результат:** Фоновая логика изолирована. web_interface.py — только Flask routes.

---

### ШАГ 2.4 — Application Factory Pattern

**Файл:** `backend/api/app.py`

**Создать:** функцию `create_app(config=None)`:
```python
def create_app(config=None):
    app = Flask(__name__, ...)
    # Загрузка конфига
    # Регистрация blueprints
    # Инициализация БД
    # Запуск фоновых потоков
    return app
```

**Почему:** Необходимо для тестирования (изолированные тестовые приложения), Gunicorn, и будущего масштабирования.

---

## ФАЗА 3: Тестирование (P1)

> **Цель:** Покрыть тестами критический функционал. Target: coverage >= 70%.
> **Метод:** TDD — RED → GREEN → REFACTOR с субагентом implementation-coder.

### ШАГ 3.1 — Unit-тесты data_model.py

**Файл:** `tests/unit/test_data_model.py`

**Покрытие:**
| Группа | Методы | Кол-во тестов |
|--------|--------|---------------|
| Printer CRUD | add, get, update, delete, get_all | 6 |
| Task CRUD | add, get, update, delete, get_by_status | 6 |
| Project CRUD | add, get, update, delete | 4 |
| Coil CRUD + logic | add, get, adjust_remains, archive | 6 |
| Vendor/Filament | add, get, update, delete | 4 |
| Maintenance | add_record, get_status, is_overdue | 4 |
| SpoolHistory | add, deduct on task complete | 3 |
| Schema migration | _ensure_schema на пустой БД | 2 |
| **Итого** | | **~35 тестов** |

**Фикстура:**
```python
@pytest.fixture
def db(tmp_path):
    return DBModel(db_path=str(tmp_path / "test.db"))
```

---

### ШАГ 3.2 — Unit-тесты gcode_parser.py

**Файл:** `tests/unit/test_gcode_parser.py`

**Покрытие:**
| Тест | Описание |
|------|----------|
| test_parse_orcaslicer | Парсинг файла OrcaSlicer |
| test_parse_cura | Парсинг файла Cura |
| test_parse_unknown_slicer | Fallback для неизвестного слайсера |
| test_parse_empty_file | Пустой файл не крашится |
| test_time_string_parsing | "1h 30m 45s" → 5445 секунд |
| test_estimate_fallback | Оценка по размеру файла |
| **Итого** | **~8 тестов** |

---

### ШАГ 3.3 — Integration-тесты Flask API

**Файл:** `tests/integration/test_api.py`

**Покрытие (через Flask test client):**
| Группа | Endpoints | Кол-во тестов |
|--------|-----------|---------------|
| Pages | GET /, /planning, /maintenance, /spools | 5 |
| Printers API | GET/POST /api/printers, PUT/DELETE | 6 |
| Tasks API | GET/POST /api/tasks, PATCH, upload gcode | 6 |
| Projects API | GET/POST /api/projects | 4 |
| Coils API | GET/POST /api/coils, adjust, archive | 5 |
| Maintenance API | GET /api/maintenance/status, POST records | 4 |
| State API | GET /api/state | 2 |
| **Итого** | | **~32 теста** |

---

### ШАГ 3.4 — E2E-тесты Moonraker интеграции

**Файл:** `tests/e2e/test_moonraker.py`

**Метод:** Mock Moonraker API через `responses` library.

**Покрытие:**
| Сценарий | Описание |
|----------|----------|
| Fetch state — online printer | Mock Moonraker, проверить что статус "idle" |
| Fetch state — offline printer | Timeout, проверить "offline" |
| Upload + start print | Загрузка G-code + запуск печати |
| Print complete flow | Состояние "complete" → awaiting_removal → confirmed |
| Print error flow | Состояние "error" → task cancelled |
| Circuit breaker activation | 5 failures → skip printer |
| **Итого** | **~10 тестов** |

---

### ШАГ 3.5 — CI: Coverage и линтинг

**Действия:**
1. Добавить `pytest --cov=backend --cov-report=html --cov-fail-under=70` в финальный прогон
2. Добавить `ruff check backend/` как pre-commit check
3. Создать `Makefile` с командами:
   ```makefile
   test:
       pytest tests/ --tb=short -q
   test-cov:
       pytest tests/ --cov=backend --cov-report=html --cov-fail-under=70
   lint:
       ruff check backend/
   lint-fix:
       ruff check --fix backend/
   ```

---

## ФАЗА 3.5: Фронтенд — UX и производительность (P1)

> **Цель:** Убрать задержки при навигации, сделать интерфейс отзывчивым и плавным.
> **Проблема:** При переходе между страницами — белый экран ~500мс, потом подгрузка данных. Для оператора фермы из 25 принтеров это неприемлемо.

### ШАГ 3.5.1 — Кеширование данных в localStorage (мгновенный рендер)

**Проблема:** Каждая страница загружает данные с нуля через fetch → API → SQLite → JSON. Пользователь видит пустую страницу до завершения запроса.

**Решение:** Паттерн **stale-while-revalidate**:
1. При загрузке страницы — сразу рендерить данные из `localStorage` (мгновенно)
2. Параллельно делать fetch к API
3. Когда свежие данные получены — обновить DOM и localStorage

```javascript
// Пример для Dashboard
async function loadPrinters() {
  // Мгновенный рендер из кеша
  const cached = localStorage.getItem('printers_cache');
  if (cached) {
    renderPrinters(JSON.parse(cached));
  }
  // Обновление из API
  const fresh = await fetchPrinters();
  localStorage.setItem('printers_cache', JSON.stringify(fresh));
  renderPrinters(fresh);
}
```

**Файлы:** `frontend/static/js/script.js`, `printer-control.js`, `planning.js`, `maintenance.js`, `spools.js`

**Результат:** Переход между страницами — данные видны мгновенно, обновляются через ~200мс.

---

### ШАГ 3.5.2 — WebSocket подписка вместо HTTP polling

**Проблема:** Dashboard опрашивает `/api/printers` каждые 5 сек (HTTP GET). Printer Control — `/api/state` каждую 1 сек. При 25 принтерах это ~30 запросов/сек.

**Решение:** Moonraker поддерживает WebSocket подписки (docs/external_api). Бэкенд может:
1. Подписаться на изменения состояний принтеров через Moonraker WebSocket
2. Пробрасывать изменения на фронт через Flask-SocketIO или Server-Sent Events (SSE)

**Вариант А (SSE — проще):**
- Бэкенд: endpoint `GET /api/events/stream` — Server-Sent Events
- Фронт: `EventSource('/api/events/stream')` — получает обновления без polling
- Плюсы: не нужна библиотека, работает через HTTP
- Минусы: однонаправленный (сервер → клиент)

**Вариант Б (WebSocket через Moonraker напрямую):**
- Фронт подключается напрямую к Moonraker WebSocket (ws://host:port/websocket)
- Плюсы: real-time без задержек, полная информация
- Минусы: фронт должен знать IP каждого принтера, нет агрегации

**Рекомендация:** SSE (Вариант А) — проще, работает через один endpoint, агрегирует данные со всех принтеров.

---

### ШАГ 3.5.3 — Плавные переходы между страницами

**Проблема:** Полная перезагрузка HTML при навигации (каждая страница — отдельный route).

**Решение (минимальное):** CSS-анимация fade-in при загрузке:
```css
body { animation: fadeIn 0.15s ease-in; }
@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
```

**Решение (продвинутое):** SPA-подобная навигация через `fetch` + `history.pushState` — загрузка только контента без перезагрузки sidebar и header. Требует значительной переработки шаблонов.

**Рекомендация:** Начать с CSS fade-in + localStorage кеш. Этого достаточно для ощущения "мгновенности".

---

### ШАГ 3.5.4 — Исправления UX по результатам тестирования (ВЫПОЛНЕНО)

**Выполнено 2026-03-30:**
- ✅ Auto-refresh Dashboard каждые 5 сек
- ✅ Цветные обводки карточек (синий idle, зелёный work, красный error)
- ✅ "Без проекта" в выборе проекта при создании задачи
- ✅ Температуры по умолчанию 0 вместо 210/60
- ✅ Async загрузка state+tasks при выборе принтера (без мерцания)
- ✅ Исправлен API-контракт: coil adjust (new_remains), history (task_id)

---

## ФАЗА 4: Недостающий функционал по ТЗ (P2)

> **Цель:** Довести соответствие ТЗ с 85% до 95%+.

### ШАГ 4.1 — Telegram-уведомления

**Создать:** `backend/services/notifications.py`

**Функционал:**
- Класс `TelegramNotifier` — отправка сообщений через Telegram Bot API
- Уведомления при:
  - Ошибке принтера (status → "error")
  - Завершении печати (status → "complete")
  - Необходимости планового ТО (is_overdue = True)
- Настройка: `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` в `.env`

**Интеграция:** Вызывается из `handle_print_complete()`, `handle_print_error()`, `update_printer_states_loop()`.

**Тест:** Mock Telegram API, проверить что сообщение формируется корректно.

---

### ШАГ 4.2 — Журнал событий (Event Log)

**Модель:** `EventLog` в `data_model.py`:
```python
class EventLog(Base):
    __tablename__ = 'event_log'
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    event_type = Column(String)    # printer_error, print_complete, maintenance_due, etc.
    printer_id = Column(Integer, ForeignKey('printers.id'), nullable=True)
    task_id = Column(Integer, ForeignKey('tasks.id'), nullable=True)
    message = Column(Text)
    severity = Column(String)      # info, warning, error, critical
```

**API:** `GET /api/events?printer_id=X&type=Y&limit=50`
**UI:** Новая страница "Журнал" или виджет на Dashboard.

---

### ШАГ 4.3 — Очередь печати (автоназначение)

**Функционал:**
- Задачи со статусом `queued` автоматически назначаются на свободные принтеры
- Логика: найти idle принтер с подходящей катушкой → назначить задачу → начать печать
- Конфигурация: `AUTO_QUEUE_ENABLED=0` в `.env` (по умолчанию отключена)

**Приоритет:** Низкий. Реализовать после стабилизации основного функционала.

---

### ШАГ 4.4 — Email-уведомления (опционально)

**Создать:** расширить `backend/services/notifications.py`

**Функционал:**
- Класс `EmailNotifier` — отправка через SMTP
- Настройка: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `NOTIFY_EMAIL` в `.env`

**Приоритет:** Средний. Telegram важнее для оперативного реагирования.

---

## ФАЗА 5: Деплой и эксплуатация на RPi 4B (P2)

> **Цель:** Подготовить проект к работе на Raspberry Pi 4B в режиме 24/7.
> **Результат:** Автозапуск, watchdog, защита SD-карты, мониторинг.

### ШАГ 5.1 — systemd unit для автозапуска

**Создать:** `deploy/printerbase.service`

```ini
[Unit]
Description=PrinterBase 3D Printer Farm Manager
After=network-online.target
Wants=network-online.target
StartLimitIntervalSec=300
StartLimitBurst=5

[Service]
Type=simple
User=pi
Group=pi
WorkingDirectory=/opt/printerbase
Environment="PATH=/opt/printerbase/.venv/bin:/usr/bin"
ExecStart=/opt/printerbase/.venv/bin/gunicorn \
    --config gunicorn_config.py \
    backend.api.web_interface:app
Restart=on-failure
RestartSec=5s
RuntimeMaxSec=86400

# Безопасность
NoNewPrivileges=true
ProtectSystem=strict
ReadWritePaths=/opt/printerbase/backend/db /opt/printerbase/backend/uploads
PrivateTmp=true

# Лимиты
MemoryMax=512M
CPUQuota=80%

[Install]
WantedBy=multi-user.target
```

---

### ШАГ 5.2 — Nginx reverse proxy

**Создать:** `deploy/nginx-printerbase.conf`

**Функционал:**
- Reverse proxy → Gunicorn (localhost:5000)
- Раздача статики напрямую (frontend/static/)
- Лимит размера загрузки: 200MB (для G-code)
- Gzip для CSS/JS
- Rate limiting для API (защита от случайного flood)

---

### ШАГ 5.3 — Защита SD-карты

**Создать:** `deploy/sd-card-optimization.sh`

**Действия:**
1. tmpfs для `/tmp` и `/var/log` (256MB и 64MB)
2. `noatime` + `commit=600` в `/etc/fstab`
3. log2ram — логи в RAM, сброс раз в час
4. Отключение swap на SD-карту

**Рекомендация:** Вынести SQLite БД на USB SSD для максимальной надёжности.

---

### ШАГ 5.4 — Скрипт развёртывания

**Создать:** `deploy/install.sh`

**Содержание:**
```bash
#!/bin/bash
# Установка printerbase на Raspberry Pi 4B
set -euo pipefail

INSTALL_DIR="/opt/printerbase"

# 1. Установка системных зависимостей
sudo apt update && sudo apt install -y python3-venv nginx

# 2. Создание виртуального окружения
python3 -m venv "$INSTALL_DIR/.venv"
source "$INSTALL_DIR/.venv/bin/activate"
pip install -r requirements.txt

# 3. Копирование systemd unit
sudo cp deploy/printerbase.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable printerbase

# 4. Копирование Nginx конфигурации
sudo cp deploy/nginx-printerbase.conf /etc/nginx/sites-available/printerbase
sudo ln -sf /etc/nginx/sites-available/printerbase /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

# 5. Запуск
sudo systemctl start printerbase
```

---

### ШАГ 5.5 — Health check endpoint

**Файл:** `backend/api/web_interface.py` (или отдельный blueprint)

**Endpoint:** `GET /health`

**Response:**
```json
{
    "status": "ok",
    "version": "1.0.0",
    "uptime_seconds": 3600,
    "printers_online": 20,
    "printers_total": 25,
    "db_size_mb": 15.2,
    "active_prints": 3
}
```

**Назначение:** Мониторинг через systemd watchdog, Nginx health check, внешний мониторинг.

---

## ПОРЯДОК ВЫПОЛНЕНИЯ (РЕКОМЕНДУЕМЫЙ)

```
Фаза 0 (инфраструктура):  0.1 → 0.2 → 0.3 → 0.4
                                ↓
Фаза 1 (критические):     1.1 → 1.2 → 1.3 → 1.4 → 1.5 → 1.6
                                ↓
Фаза 2 (архитектура):     2.1 → 2.2 → 2.3 → 2.4
                                ↓
Фаза 3 (тесты):           3.1 → 3.2 → 3.3 → 3.4 → 3.5
                                ↓
Фаза 4 (функционал):      4.1 → 4.2 → 4.3 → 4.4
                                ↓
Фаза 5 (деплой):          5.1 → 5.2 → 5.3 → 5.4 → 5.5
```

**Параллелизация:** Шаги внутри Фазы 3 (3.1, 3.2) могут выполняться параллельно. Фаза 4 может начинаться параллельно с Фазой 3 (после Фазы 2).

---

## МЕТРИКИ УСПЕХА

| Метрика | Текущее | Целевое |
|---------|---------|---------|
| Test coverage | 0% | >= 70% |
| Соответствие ТЗ | ~85% | >= 95% |
| Время опроса 25 принтеров | ~50 сек | < 3 сек |
| WSGI-сервер | Flask dev | Gunicorn gthread |
| Автоматический перезапуск | Нет | systemd on-failure |
| Логирование | print() | structured logging |
| Размер web_interface.py | 2300+ строк | < 300 строк (с blueprints) |
| Нагрузка на SD-карту | Без оптимизации | WAL + tmpfs + noatime |
