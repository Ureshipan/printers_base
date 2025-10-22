# Printer Discovery Subsystem

Автоматическая система обнаружения и управления 3D‑принтерами (Klipper/Moonraker) через Bluetooth, mDNS и SSDP.

## Обзор

Этот модуль автоматизирует поиск 3D-принтеров в локальной сети и через Bluetooth, упрощая подключение и управление:

- Автоматическое сканирование Bluetooth устройств и получение IP с Raspberry Pi,
- Обнаружение Moonraker сервисов через mDNS/Zeroconf,
- Расширенное обнаружение через SSDP/UPnP,
- Хранение информации о принтерах в JSON конфигурации,
- Консольный интерфейс и API для управления.

## Особенности

- Многоуровневое обнаружение с fallback,
- Динамическое обновление IP,
- Поддержка нескольких принтеров,
- Интеграция с вашим backend проектом,
- CLI для удобного взаимодействия.

## Установка

Установите зависимости:

```
pip install -r discovery/requirements_discovery.txt
```

Для Bluetooth (опционально):

```
sudo apt-get install python3-dev libbluetooth-dev
pip install pybluez
```

## Использование

### CLI

```
python discovery/cli_interface.py
python discovery/cli_interface.py --interactive
```

### Интеграция в код

```
from discovery.integration_module import PrinterDiscoveryManager

manager = PrinterDiscoveryManager()
params = manager.get_connection_params('printer_id')

if params:
from backend.services.moonraker_tool import MoonrakerClient
client = MoonrakerClient(params['host'], params['port'])

text
```

## Структура каталогов

```
discovery/
├── init.py
├── config_manager.py
├── bluetooth_discovery.py
├── mdns_discovery.py
├── integration_module.py
├── cli_interface.py
├── bluetooth_ip_server.py
├── bluetooth-ip-server.service
├── requirements_discovery.txt
└── printer_config.json (создается автоматически)
```

## Bluetooth IP сервер (для Raspberry Pi)

На Raspberry Pi с Klipper запустите сервис bluetooth_ip_server.py для публикации IP по RFCOMM Bluetooth.

Сервис запускается системой через bluetooth-ip-server.service.

Этот сервис обрабатывает команды GET_IP, GET_INFO и PING для обмена с клиентами.

## Лицензия

MIT License — свободное использование и модификация.

---
