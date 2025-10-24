# Printer Discovery Module

Автоматическое обнаружение Raspberry Pi (3D-принтеров с Klipper/Moonraker) в локальной сети через UDP multicast без настройки роутера.

## 🎯 Особенности

- ✅ **Автоматическое обнаружение** — находит все Raspberry Pi в локальной сети
- ✅ **Множественная поддержка** — работает с любым количеством принтеров
- ✅ **Без настройки роутера** — не требует DHCP reservations или статических IP
- ✅ **Кроссплатформенность** — Windows, Linux, macOS
- ✅ **Нулевая конфигурация** — запустил и работает
- ✅ **UDP Multicast** — надежный и быстрый протокол обнаружения

## 📂 Структура

```
discovery/
├── __init__.py           # Инициализация модуля
├── pi_advertiser.py      # Сервис рассылки IP (запускается на Raspberry Pi)
├── pi_discover.py        # Клиент обнаружения (запускается на ПК)
├── utils.py              # Утилиты (получение IP, сохранение конфигураций)
└── README.md             # Документация
```

## 🚀 Быстрый старт

### На Raspberry Pi (каждый принтер)

1. **Установка зависимостей:**
   ```
   sudo apt update
   sudo apt install python3-pip python3-netifaces
   pip3 install netifaces
   ```

2. **Запуск сервиса рассылки IP:**
   ```
   python3 discovery/pi_advertiser.py printer-01
   ```
   
   Где `printer-01` — уникальный идентификатор принтера.  
   Для разных принтеров используйте разные ID: `printer-02`, `fdm-lab`, `resin-studio` и т.д.

3. **Автозапуск при старте системы (опционально):**
   Создайте systemd service:
   ```
   sudo nano /etc/systemd/system/pi-advertiser.service
   ```
   
   Содержимое файла:
   ```
   [Unit]
   Description=Raspberry Pi IP Advertiser
   After=network.target
   
   [Service]
   Type=simple
   User=pi
   WorkingDirectory=/home/pi/printers_base
   ExecStart=/usr/bin/python3 /home/pi/printers_base/discovery/pi_advertiser.py printer-01
   Restart=always
   
   [Install]
   WantedBy=multi-user.target
   ```
   
   Активация:
   ```
   sudo systemctl enable pi-advertiser.service
   sudo systemctl start pi-advertiser.service
   sudo systemctl status pi-advertiser.service
   ```

### На ПК (Windows/Linux/macOS)

1. **Установка зависимостей:**
   ```
   pip install netifaces
   ```
   
   (или из корневого `requirements.txt` проекта)

2. **Запуск обнаружения принтеров:**
   ```
   python discovery/pi_discover.py
   ```

3. **Опции командной строки:**
   ```
   # Стандартный режим (10 секунд обнаружения)
   python discovery/pi_discover.py
   
   # Указать таймаут
   python discovery/pi_discover.py --timeout 20
   
   # Непрерывный режим (Ctrl+C для остановки)
   python discovery/pi_discover.py --continuous
   
   # Сохранить результаты в JSON
   python discovery/pi_discover.py --save
   python discovery/pi_discover.py --save --output my_printers.json
   ```

## 📖 Использование в коде

### Простое обнаружение

```
from discovery import listen_for_printers

# Найти все принтеры за 10 секунд
printers = listen_for_printers(timeout=10)

print(printers)
# {'printer-01': '192.168.1.101', 'printer-02': '192.168.1.102'}

# Подключиться к конкретному принтеру
ip = printers.get('printer-01')
if ip:
    print(f"Подключаюсь к {ip}")
```

### Расширенное использование

```
from discovery import PrinterListener, save_discovered_printers

listener = PrinterListener()

# Непрерывное прослушивание
printers = listener.listen(timeout=15)

# Получить детальную информацию
detailed = listener.get_detailed_info()
for printer_id, info in detailed.items():
    print(f"{printer_id}: {info['ip']} (last seen: {info['timestamp']})")

# Сохранить результаты
save_discovered_printers(printers, 'discovered.json')
```

### Получение локального IP

```
from discovery.utils import get_local_ip

# Автоматическое определение IP
my_ip = get_local_ip()
print(f"Мой IP: {my_ip}")

# Указать конкретный интерфейс (Linux)
wlan_ip = get_local_ip('wlan0')
eth_ip = get_local_ip('eth0')
```

## 🔧 Конфигурация

### Настройка multicast параметров

В файлах `pi_advertiser.py` и `pi_discover.py`:

```
MULTICAST_GROUP = '239.255.255.250'  # Multicast адрес
MULTICAST_PORT = 50000               # Порт
BROADCAST_INTERVAL = 3               # Интервал рассылки (секунды)
```

### Выбор сетевого интерфейса (Raspberry Pi)

По умолчанию используется `wlan0` (Wi-Fi). Для Ethernet:

```
python3 pi_advertiser.py printer-01 --interface eth0
```

## 🛠️ Устранение проблем

### Принтеры не обнаруживаются

1. **Проверьте, что Pi и ПК в одной сети:**
   ```
   # На Pi
   ip addr show wlan0
   
   # На ПК
   ipconfig    # Windows
   ifconfig    # Linux/macOS
   ```

2. **Проверьте брандмауэр:**
   - Windows: разрешите Python через брандмауэр
   - Linux: проверьте `iptables` или `ufw`

3. **Проверьте работу сервиса на Pi:**
   ```
   python3 pi_advertiser.py printer-01
   # Должны появляться сообщения "Advertised: printer-01 -> 192.168.x.x"
   ```

4. **Проверьте порт на ПК:**
   ```
   # Windows
   netstat -an | findstr :50000
   
   # Linux/macOS
   netstat -an | grep 50000
   ```

### Ошибка "Address already in use"

Другой экземпляр `pi_discover.py` уже запущен. Завершите предыдущий процесс.

### Не удается получить IP на Raspberry Pi

Установите `netifaces`:
```
sudo apt install python3-netifaces
pip3 install netifaces
```

## 🔬 Принцип работы

1. **Raspberry Pi** периодически (каждые 3 секунды) рассылает UDP multicast пакет:
   ```
   {
     "id": "printer-01",
     "ip": "192.168.1.101",
     "timestamp": 1698765432.123
   }
   ```

2. **ПК-клиент** слушает multicast группу `239.255.255.250:50000` и собирает информацию от всех принтеров.

3. **Результат** — динамическая таблица `printer_id → ip_address`, всегда актуальная.

## 📝 Интеграция с проектом

### Backend интеграция

```
# В вашем backend/moonraker_client.py
from discovery import listen_for_printers

def get_printer_ip(printer_id):
    printers = listen_for_printers(timeout=5)
    return printers.get(printer_id)

# Использование
ip = get_printer_ip('printer-01')
client = MoonrakerClient(ip, 7125)
```

### CLI интеграция

Добавьте в `start_tools.bat` / `start_tools.sh`:

```
echo "Discovering printers..."
python discovery/pi_discover.py --timeout 5
```

## 🎯 Примеры использования

### SSH подключение

```
# Найти и подключиться
python discovery/pi_discover.py --save
# Результат сохранен в discovered_printers.json

# Прочитать IP и подключиться
ssh pi@192.168.1.101
```

### Автоматический выбор принтера

```
printers = listen_for_printers()

if len(printers) == 1:
    # Только один принтер — подключаемся автоматически
    printer_id, ip = list(printers.items())
    print(f"Auto-connecting to {printer_id} at {ip}")
else:
    # Несколько принтеров — показываем выбор
    print("Available printers:")
    for i, (pid, ip) in enumerate(printers.items(), 1):
        print(f"{i}. {pid} ({ip})")
```
