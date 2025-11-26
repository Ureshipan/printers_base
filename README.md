# Панель управления 3D‑принтерами (Moonraker + Flask)

Веб-панель на Flask с фронтендом (HTML/JS/CSS) для работы с принтерами на Klipper/Moonraker: мониторинг, управление, загрузка G-code, планирование задач и управление проектами. Все данные хранятся в SQLite (`backend/db/database.db`) и берутся из API, без захардкоженных принтеров или задач.

## Быстрый старт
```bash
python -m venv .venv && source .venv/bin/activate  # опционально
pip install -r requirements.txt

# Запуск веб-интерфейса
python backend/api/web_interface.py
# или через стартовые скрипты:
#   ./start_tools.sh
#   start_tools.bat
```
Приложение по умолчанию доступно на `http://localhost:5000`.

## Основные страницы
- `/` — дашборд: реальные принтеры, статистика по статусам, материалы (катушки), очередь задач. Добавление физических и виртуальных принтеров из интерфейса.
- `/planning` — проекты и задачи: создание/редактирование задач, привязка к проекту/принтеру, загрузка G-code.
- `/printer-control` — управление выбранным принтером: состояние, температуры, оси, отправка G-code. Все команды идут на выбранный `printer_id`.

## Ключевые API
- Принтеры:  
  - `GET /api/printers` — список активных принтеров.  
  - `POST /api/printers` — добавить принтер по IP/порту Moonraker.  
  - `POST /api/printers/virtual` — создать виртуальный принтер (демо) со статусом (`idle|work|error|service|offline|printing|ready`).  
  - `DELETE /api/printers/<id>` — удалить принтер.  
- Состояние/команды:  
  - `GET /api/state?printer_id=<id>` — текущее состояние.  
  - `POST /api/command|home|temperature` — команды с `printer_id` в теле.  
- Задачи/проекты/катушки: `GET/POST/PATCH/DELETE /api/tasks`, `/api/projects`, `/api/coils`.  
- G-code: `POST/GET/DELETE /api/tasks/<id>/gcode`.

## Переменные окружения
- `MOONRAKER_PORT` — порт Moonraker (по умолчанию `7125`).  
- `MOONRAKER_DEFAULT_HOST` — fallback-хост, если автопоиск отключён.  
- `PRINTER_DISCOVERY_ENABLED` — `0` по умолчанию (автопоиск по сети выключен); включить `1`, чтобы сканировать сеть (`discovery/pi_discover.py`).  
- `PRINTER_DISCOVERY_INTERVAL` — период автопоиска в секундах (если включён).  
- `PRINTER_STATE_INTERVAL` — период опроса состояния принтеров (секунды).

## База данных
- SQLite файл: `backend/db/database.db` создаётся автоматически.  
- Таблица `printers` поддерживает физические и виртуальные устройства (`is_virtual`, `virtual_status`).  
- Таблицы задач/проектов/катушек/материалов создаются и мигрируются автоматически при старте.

## Добавление виртуального принтера (пример)
Через дашборд кнопкой «Виртуальный» или API:
```bash
curl -X POST http://localhost:5000/api/printers/virtual \
  -H "Content-Type: application/json" \
  -d '{"name":"Demo Printer","status":"work"}'
```

## Примечания
- Автосканирование сети отключено по умолчанию, чтобы не отправлять broadcast-запросы без явного согласия.  
- Фронтенд полностью читает данные из API/БД; фиктивных принтеров, задач или очередей нет.  
- Для смены адреса по умолчанию используйте переменные окружения или добавьте реальные/виртуальные принтеры через UI/API. 
