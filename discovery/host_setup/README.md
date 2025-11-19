
# IP Advertiser для Orange Pi

Этот скрипт `pi_adv.sh` предназначен для периодической рассылки IP-адреса Orange Pi по локальной сети. Используется для обнаружения устройства в сети.

---

## Перенос на Orange Pi

1. Скопируйте скрипт `pi_adv.sh` на Orange Pi в удобную папку, например, `/home/orangepi/autorun/`.
2. Убедитесь, что у скрипта есть права на исполнение:

   ```
   chmod +x /home/orangepi/autorun/pi_adv.sh
   ```

---

## Использование

Запуск скрипта требует указания обязательного параметра — уникального идентификатора принтера (или устройства).

### Параметры скрипта

```
./pi_adv.sh <printer_id> [interface] [interval]
```

- `printer_id` — уникальный идентификатор вашего устройства (обязательно).
- `interface` — сетевой интерфейс (по умолчанию `wlan0`).
- `interval` — интервал в секундах для рассылки пакетов (по умолчанию 3 секунды).

### Примеры запуска

```
./pi_adv.sh my_printer_01
./pi_adv.sh my_printer_01 eth0 5
```

---

## Настройка автозапуска (systemd сервис)

Для автоматического запуска скрипта при загрузке системы рекомендуется создать systemd сервис.

1. Создайте папку `autorun` в домашнем каталоге Orange Pi (если ещё не создана):

   ```
   mkdir -p /home/orangepi/autorun
   ```

2. Поместите скрипт туда:

   ```
   mv pi_adv.sh /home/orangepi/autorun/
   chmod +x /home/orangepi/autorun/pi_adv.sh
   ```

3. Создайте systemd сервис файл `/etc/systemd/system/pi-advertiser.service` со следующим содержимым:

   ```
   [Unit]
   Description=Orange Pi IP Advertiser Service
   After=network.target

   [Service]
   Type=simple
   User=orangepi
   WorkingDirectory=/home/orangepi/autorun
   ExecStart=/home/orangepi/autorun/pi_adv.sh my_printer_01 wlan0 3
   Restart=always
   RestartSec=5

   [Install]
   WantedBy=multi-user.target
   ```

   Обратите внимание: замените `User=orangepi` на имя пользователя вашего Orange Pi, а `my_printer_01` — на ваш уникальный идентификатор.

4. Перезагрузите конфигурацию systemd и запустите сервис:

   ```
   sudo systemctl daemon-reload
   sudo systemctl enable pi-advertiser.service
   sudo systemctl start pi-advertiser.service
   sudo systemctl status pi-advertiser.service
   ```

---

## Пояснения

- Скрипт будет каждые несколько секунд (интервал задаётся параметром) отправлять UDP broadcast с JSON-пакетом, содержащим ID устройства и его IP-адрес.
- Интерфейс по умолчанию `wlan0`, можно указать любой другой сетевой интерфейс, например `eth0`.
- Для корректной работы в сети необходимо, чтобы UDP пакеты на порт 50000 не блокировались сетевым оборудованием или фаерволлом.

---

## Пример вывода скрипта

```
Starting IP Advertiser for printer: my_printer_01
Interface: wlan0
Broadcast IP: 255.255.255.255
Port: 50000
Interval: 3s
----------------------------------------
 Broadcasted: my_printer_01 -> 192.168.1.100[1]
 IP unchanged: 192.168.1.100 (skipping broadcast)[2]
...
```

---

Этот README помогает перенести и настроить `pi_adv.sh` на Orange Pi с автозапуском через systemd и использованием папки `autorun` для хранения скрипта и связанных файлов.