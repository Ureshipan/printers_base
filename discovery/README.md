# Printer Discovery Module

Автоматическое обнаружение Raspberry Pi с Klipper/Moonraker и других 3D-принтеров в локальной сети. Поддерживает multicast, broadcast и поиск через сканирование подсетей, полностью кроссплатформенен.

---

## 🎯 Особенности

- ✅ **Автоматическое обнаружение** — ищет все Raspberry Pi в локальной сети
- ✅ **Работает с любым количеством устройств**
- ✅ **Без ручных настроек DHCP/роутера**
- ✅ **Кроссплатформенность:** Windows, Linux, macOS
- ✅ **UDP Multicast/broadcast** — устойчивый и быстрый обмен
- ✅ **Сканирование подсетей** — найдет все, даже без поддержки multicast
- ✅ **Virtualenv-ready** — удобна установка всех зависимостей

---

## 📂 Структура

```
autorun/                 # (или discovery/)
├── pi_advertiser.py     # Runner для автопубликации IP (на Raspberry Pi)
├── requirements.txt     # Зависимости Python
└── README.md            # Эта документация

discovery/               # (на ПК)
├── pi_discover.py       # Сканер и auto-discovery в любой локальной сети
├── utils.py             # Служебные утилиты: сохранение, фильтрация и т.д.
```

---

## 🚀 Быстрый старт: Raspberry Pi

1. **Переместите файлы:**
   ```
   mv discovery/pi_advertiser.py /home/pi/autorun/
   mv requirements.txt /home/pi/autorun/
   cd /home/pi/autorun
   ```

2. **Создайте virtualenv и установите зависимости:**
   ```
   python3 -m venv venv
   . venv/bin/activate
   pip install -r requirements.txt
   deactivate
   ```

3. **Проверьте работу вручную:**
   ```
   . venv/bin/activate
   python pi_advertiser.py printer-01
   deactivate
   ```

4. **Добавьте автозапуск через systemd:**
   ```
   sudo nano /etc/systemd/system/pi-advertiser.service
   ```

   Вставьте:

   ```
   [Unit]
   Description=Raspberry Pi IP Advertiser (autorun, virtualenv)
   After=network.target

   [Service]
   Type=simple
   User=pi
   WorkingDirectory=/home/pi/autorun
   ExecStart=/bin/bash -c '. /home/pi/autorun/venv/bin/activate && python /home/pi/autorun/pi_advertiser.py printer-01'
   Restart=always
   RestartSec=5

   [Install]
   WantedBy=multi-user.target
   ```

   Затем перезагрузите сервис:
   ```
   sudo systemctl daemon-reload
   sudo systemctl enable pi-advertiser.service
   sudo systemctl start pi-advertiser.service
   sudo systemctl status pi-advertiser.service
   ```

---

## 🚀 Быстрый старт: ПК (поиск всех устройств)

1. **Установка зависимости:**
   ```
   pip install netifaces
   ```

2. **Поиск всех Raspberry Pi и 3d-принтеров:**
   ```
   python discovery/pi_discover.py
   # или указать подсеть:
   python discovery/pi_discover.py --subnet 172.22.112
   # или сканировать вообще все интерфейсы (по умолчанию)
   ```

---

## 🔧 Как работает

- Каждый Raspberry Pi периодически рассылает JSON-пакет с ID и своим IP.
- Любой ПК автоматически найдет все Raspberry Pi в той же L2-сети.
- При необходимости fallback к "грубому" сканированию всей подсети (например, если multicast/broadcast заблокирован).

---

## 🛠️ Советы и FAQ

- **Firewall?** На некоторых системах (особенно Windows) проверьте, чтобы Python был добавлен в исключения.
- **DHCP?** Не важно, выдаёт ли роутер динамический адрес — поиск все равно сработает.
- **Несколько сетевых интерфейсов?** pi_discover автоматически опрашивает каждый.

---

## 📖 Использование в коде

```
from discovery import listen_for_printers

printers = listen_for_printers(timeout=10)
print(printers)  # {'printer-01': '192.168.1.101', ...}

ip = printers.get('printer-01')
if ip:
    print(f"Подключаемся к {ip}")
```

---

## 📝 Примеры systemd и интеграции

Для каждого Pi можно использовать уникальный идентификатор:
```
ExecStart=... python pi_advertiser.py lab-printer
ExecStart=... python pi_advertiser.py resin-cube
```

---

## Лицензия

MIT License

---

## Автор

[@fylhtq7779](https://github.com/fylhtq7779)
```

**Комментарии и инструкции полностью адаптированы под вашу структуру, multinet, venv и systemd автозапуск!**