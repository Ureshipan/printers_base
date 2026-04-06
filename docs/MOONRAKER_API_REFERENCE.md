# Moonraker API Reference для мониторинга принтера

Справочник по API Moonraker с реальными примерами ответов от принтера.

**Базовый URL:** `http://<IP>:7125`

---

## 1. Информация о сервере

### GET /server/info
Состояние Moonraker и Klipper.

```bash
curl -s "http://192.168.51.106:7125/server/info"
```

**Ответ:**
```json
{
  "result": {
    "klippy_connected": true,
    "klippy_state": "ready",
    "moonraker_version": "v0.9.3-4-ga4604e3",
    "api_version": [1, 4, 0],
    "websocket_count": 6,
    "components": ["database", "file_manager", "history", "timelapse", ...],
    "warnings": [...]
  }
}
```

**Важные поля:**
| Поле | Описание |
|------|----------|
| `klippy_connected` | Подключён ли Klipper |
| `klippy_state` | `ready` / `startup` / `error` / `shutdown` / `disconnected` |
| `moonraker_version` | Версия Moonraker |

---

## 2. Информация о принтере

### GET /printer/info
Информация о Klipper.

```bash
curl -s "http://192.168.51.106:7125/printer/info"
```

**Ответ:**
```json
{
  "result": {
    "state": "ready",
    "state_message": "Printer is ready",
    "hostname": "armbian",
    "software_version": "v0.12.0-404-g80d185c94-dirty",
    "cpu_info": "4 core ARMv8 Processor rev 4 (v8l)",
    "klipper_path": "/home/pi/klipper",
    "config_file": "/home/pi/printer_data/config/printer.cfg",
    "log_file": "/home/pi/printer_data/logs/klippy.log"
  }
}
```

---

## 3. Запрос состояния объектов (ОСНОВНОЙ)

### POST /printer/objects/query
**Главный эндпоинт для мониторинга.** Возвращает текущее состояние указанных объектов.

```bash
curl -s -X POST "http://192.168.51.106:7125/printer/objects/query" \
  -H "Content-Type: application/json" \
  -d '{
    "objects": {
      "webhooks": null,
      "print_stats": null,
      "virtual_sdcard": null,
      "extruder": null,
      "heater_bed": null,
      "toolhead": null,
      "display_status": null,
      "fan": null,
      "idle_timeout": null
    }
  }'
```

**Ответ:**
```json
{
  "result": {
    "eventtime": 1501.722936132,
    "status": {
      "webhooks": {
        "state": "ready",
        "state_message": "Printer is ready"
      },
      "print_stats": {
        "filename": "",
        "total_duration": 0.0,
        "print_duration": 0.0,
        "filament_used": 0.0,
        "state": "standby",
        "message": "",
        "info": {
          "total_layer": null,
          "current_layer": null
        }
      },
      "virtual_sdcard": {
        "file_path": null,
        "progress": 0.0,
        "is_active": false,
        "file_position": 0,
        "file_size": 0
      },
      "extruder": {
        "temperature": 23.71,
        "target": 0.0,
        "power": 0.0,
        "can_extrude": true,
        "pressure_advance": 0.03
      },
      "heater_bed": {
        "temperature": 23.68,
        "target": 0.0,
        "power": 0.0
      },
      "toolhead": {
        "homed_axes": "",
        "position": [0.0, 0.0, 0.0, 0.0],
        "max_velocity": 500.0,
        "max_accel": 7000.0,
        "extruder": "extruder"
      },
      "display_status": {
        "progress": 0.0,
        "message": null
      },
      "fan": {
        "speed": 0.0,
        "rpm": null
      },
      "idle_timeout": {
        "state": "Idle",
        "printing_time": 0.0
      }
    }
  }
}
```

---

## 4. Описание объектов для мониторинга

### webhooks
Состояние Klipper.
| Поле | Тип | Описание |
|------|-----|----------|
| `state` | string | `ready` / `startup` / `error` / `shutdown` |
| `state_message` | string | Сообщение о состоянии |

### print_stats
Статус печати.
| Поле | Тип | Описание |
|------|-----|----------|
| `state` | string | `standby` / `printing` / `paused` / `complete` / `error` / `cancelled` |
| `filename` | string | Имя файла (пустое если не печатает) |
| `print_duration` | float | Время печати в секундах (без пауз) |
| `total_duration` | float | Общее время задания в секундах |
| `filament_used` | float | Использовано филамента в мм |
| `message` | string | Сообщение об ошибке |
| `info.total_layer` | int? | Всего слоёв (если задано слайсером) |
| `info.current_layer` | int? | Текущий слой |

### virtual_sdcard
Прогресс файла.
| Поле | Тип | Описание |
|------|-----|----------|
| `progress` | float | Прогресс 0.0-1.0 |
| `is_active` | bool | Активно ли чтение файла |
| `file_path` | string? | Полный путь к файлу |
| `file_position` | int | Позиция в файле (байты) |
| `file_size` | int | Размер файла (байты) |

### extruder
Температура и состояние экструдера.
| Поле | Тип | Описание |
|------|-----|----------|
| `temperature` | float | Текущая температура °C |
| `target` | float | Целевая температура °C |
| `power` | float | Мощность нагревателя 0.0-1.0 |
| `can_extrude` | bool | Можно ли экструдировать |
| `pressure_advance` | float | Значение PA |

### heater_bed
Температура стола.
| Поле | Тип | Описание |
|------|-----|----------|
| `temperature` | float | Текущая температура °C |
| `target` | float | Целевая температура °C |
| `power` | float | Мощность нагревателя 0.0-1.0 |

### toolhead
Позиция и параметры головы.
| Поле | Тип | Описание |
|------|-----|----------|
| `position` | [float] | Позиция [X, Y, Z, E] |
| `homed_axes` | string | Отхомленные оси, например `"xyz"` или `""` |
| `max_velocity` | float | Макс. скорость мм/с |
| `max_accel` | float | Макс. ускорение мм/с² |
| `extruder` | string | Имя активного экструдера |

### fan
Вентилятор охлаждения.
| Поле | Тип | Описание |
|------|-----|----------|
| `speed` | float | Скорость 0.0-1.0 |
| `rpm` | int? | RPM (если есть тахометр) |

### idle_timeout
Таймаут простоя.
| Поле | Тип | Описание |
|------|-----|----------|
| `state` | string | `Idle` / `Ready` / `Printing` |
| `printing_time` | float | Время в состоянии Printing |

---

## 5. Отправка G-code команд

### POST /printer/gcode/script

```bash
curl -s -X POST "http://192.168.51.106:7125/printer/gcode/script" \
  -H "Content-Type: application/json" \
  -d '{"script": "G28"}'
```

**Ответ:** `{"result": "ok"}`

**Примеры команд:**
```bash
# Home все оси
{"script": "G28"}

# Home только X и Y
{"script": "G28 X Y"}

# Установить температуру экструдера
{"script": "M104 S200"}

# Установить температуру стола
{"script": "M140 S60"}

# Выключить нагреватели
{"script": "TURN_OFF_HEATERS"}

# Аварийная остановка (лучше использовать /printer/emergency_stop)
{"script": "M112"}

# Несколько команд через \n
{"script": "G28\nG1 X100 Y100 F3000"}
```

---

## 6. Управление печатью

### Запуск печати
```bash
curl -s -X POST "http://192.168.51.106:7125/printer/print/start?filename=3DBenchy_PETG_34m31s.gcode"
```

### Пауза
```bash
curl -s -X POST "http://192.168.51.106:7125/printer/print/pause"
```

### Возобновление
```bash
curl -s -X POST "http://192.168.51.106:7125/printer/print/resume"
```

### Отмена
```bash
curl -s -X POST "http://192.168.51.106:7125/printer/print/cancel"
```

---

## 7. Аварийная остановка

### POST /printer/emergency_stop
**Немедленная остановка!** Переводит принтер в shutdown.

```bash
curl -s -X POST "http://192.168.51.106:7125/printer/emergency_stop"
```

---

## 8. Файлы G-code

### Список файлов
```bash
curl -s "http://192.168.51.106:7125/server/files/list?root=gcodes"
```

**Ответ:**
```json
{
  "result": [
    {
      "path": "3DBenchy_PETG_34m31s.gcode",
      "modified": 1738941046.998,
      "size": 3289104,
      "permissions": "rw"
    }
  ]
}
```

### Метаданные файла
```bash
curl -s "http://192.168.51.106:7125/server/files/metadata?filename=3DBenchy_PETG_34m31s.gcode"
```

**Ответ:**
```json
{
  "result": {
    "filename": "3DBenchy_PETG_34m31s.gcode",
    "size": 3289104,
    "slicer": "OrcaSlicer",
    "slicer_version": "2.2.0",
    "layer_count": 200,
    "object_height": 5.0,
    "estimated_time": 2071,
    "nozzle_diameter": 0.4,
    "layer_height": 0.24,
    "first_layer_height": 0.24,
    "first_layer_extr_temp": 235.0,
    "first_layer_bed_temp": 75.0,
    "filament_name": "Petg_НИТ",
    "filament_type": "PETG",
    "filament_total": 4088.16,
    "filament_weight_total": 12.68,
    "thumbnails": [
      {"width": 300, "height": 300, "relative_path": ".thumbs/3DBenchy_PETG_34m31s-300x300.png"}
    ]
  }
}
```

---

## 9. История температур

### GET /server/temperature_store

```bash
curl -s "http://192.168.51.106:7125/server/temperature_store"
```

**Ответ:** Массивы температур за последние N секунд (по умолчанию 1200).
```json
{
  "result": {
    "extruder": {
      "temperatures": [23.5, 23.6, ...],
      "targets": [0, 0, ...],
      "powers": [0, 0, ...]
    },
    "heater_bed": {
      "temperatures": [23.46, 23.51, ...],
      "targets": [0, 0, ...],
      "powers": [0, 0, ...]
    }
  }
}
```

---

## 10. Рестарт

### Soft restart Klipper
```bash
curl -s -X POST "http://192.168.51.106:7125/printer/restart"
```

### Firmware restart (перезагрузка MCU)
```bash
curl -s -X POST "http://192.168.51.106:7125/printer/firmware_restart"
```

### Restart Moonraker
```bash
curl -s -X POST "http://192.168.51.106:7125/server/restart"
```

---

## 11. Маппинг статусов для UI

```python
# Из Klipper в UI
KLIPPER_TO_UI = {
    "printing": "work",
    "paused": "idle",
    "standby": "idle",
    "complete": "idle",
    "error": "error",
    "cancelled": "idle",
}

# Общий статус принтера
def get_printer_status(webhooks_state, print_stats_state):
    if webhooks_state != "ready":
        return "offline" if webhooks_state == "shutdown" else "error"
    return KLIPPER_TO_UI.get(print_stats_state, "idle")
```

---

## 12. Расчёт ETA

```python
def calculate_eta(print_stats, virtual_sdcard, metadata=None):
    progress = virtual_sdcard["progress"]
    if progress <= 0:
        return None

    # Способ 1: Из метаданных
    if metadata and "estimated_time" in metadata:
        return metadata["estimated_time"] - print_stats["print_duration"]

    # Способ 2: По текущему прогрессу
    if progress > 0:
        total_time = print_stats["print_duration"] / progress
        return total_time - print_stats["print_duration"]

    return None
```

---

## 13. Минимальный набор для мониторинга

Для базового мониторинга достаточно запрашивать:

```json
{
  "objects": {
    "webhooks": null,
    "print_stats": null,
    "virtual_sdcard": ["progress"],
    "extruder": ["temperature", "target"],
    "heater_bed": ["temperature", "target"],
    "toolhead": ["position", "homed_axes"]
  }
}
```

**Интервал опроса:** 1-2 секунды для активной печати, 5-10 секунд для простоя.

---

## 14. Полезные ссылки

- [Полная документация Moonraker API](./external_api/introduction.md)
- [Printer Objects Reference](./printer_objects.md)
- [Klipper Status Reference](https://www.klipper3d.org/Status_Reference.html)
