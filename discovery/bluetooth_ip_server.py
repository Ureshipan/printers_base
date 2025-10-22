#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bluetooth RFCOMM сервис для публикации IP-адреса Raspberry Pi
Устанавливается на стороне принтера (Raspberry Pi с Klipper/Moonraker)

Установка:
1. Скопировать в /home/pi/klipper_services/bluetooth_ip_server.py
2. Установить systemd сервис (см. bluetooth-ip-server.service)
3. sudo systemctl enable bluetooth-ip-server
4. sudo systemctl start bluetooth-ip-server
"""

import bluetooth
import socket
import subprocess
import logging
from datetime import datetime

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/bluetooth_ip_server.log'),
        logging.StreamHandler()
    ]
)


def get_local_ip():
    """Получение локального IP-адреса"""
    try:
        # Попытка получить IP через hostname
        result = subprocess.check_output(['hostname', '-I']).decode().strip()
        ips = result.split()

        # Приоритет wlan0/eth0 (приватные сети)
        for ip in ips:
            if ip.startswith('192.168') or ip.startswith('10.') or ip.startswith('172.'):
                return ip

        # Если не найден приватный IP, вернуть первый
        return ips[0] if ips else None

    except Exception as e:
        logging.error(f"Ошибка получения IP: {e}")
        return None


def get_moonraker_port():
    """Определение порта Moonraker"""
    try:
        # Попытка подключиться к стандартному порту
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('127.0.0.1', 7125))
        sock.close()

        if result == 0:
            return 7125
        else:
            return None
    except:
        return 7125  # По умолчанию


def start_rfcomm_server():
    """Запуск RFCOMM сервера для публикации IP"""
    try:
        server_sock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
        server_sock.bind(("", bluetooth.PORT_ANY))
        server_sock.listen(1)

        port = server_sock.getsockname()[1]

        # Регистрация SDP сервиса
        uuid = "00001101-0000-1000-8000-00805F9B34FB"  # Serial Port UUID

        bluetooth.advertise_service(
            server_sock,
            "Klipper_IP_Service",
            service_id=uuid,
            service_classes=[uuid, bluetooth.SERIAL_PORT_CLASS],
            profiles=[bluetooth.SERIAL_PORT_PROFILE]
        )

        local_ip = get_local_ip()
        moonraker_port = get_moonraker_port()

        logging.info("=" * 60)
        logging.info("Bluetooth RFCOMM сервер запущен")
        logging.info(f"Порт: {port}")
        logging.info(f"UUID: {uuid}")
        logging.info(f"Локальный IP: {local_ip}")
        logging.info(f"Moonraker порт: {moonraker_port}")
        logging.info("=" * 60)

        connection_count = 0

        while True:
            try:
                logging.info("Ожидание подключений...")
                client_sock, client_info = server_sock.accept()
                connection_count += 1

                logging.info(f"Подключение #{connection_count} от {client_info}")

                try:
                    # Установка таймаута
                    client_sock.settimeout(5.0)

                    # Получение команды
                    data = client_sock.recv(1024).decode('utf-8').strip()
                    logging.info(f"Получена команда: {data}")

                    if data == "GET_IP":
                        ip = get_local_ip()
                        if ip:
                            response = f"{ip}"
                            client_sock.send(response.encode('utf-8'))
                            logging.info(f"✓ IP отправлен: {ip}")
                        else:
                            client_sock.send(b"ERROR: IP not found")
                            logging.error("IP не найден")

                    elif data == "GET_INFO":
                        ip = get_local_ip()
                        port = get_moonraker_port()
                        info = f"{ip}:{port}"
                        client_sock.send(info.encode('utf-8'))
                        logging.info(f"✓ Информация отправлена: {info}")

                    elif data == "PING":
                        client_sock.send(b"PONG")
                        logging.info("PING/PONG")

                    else:
                        client_sock.send(b"ERROR: Unknown command")
                        logging.warning(f"Неизвестная команда: {data}")

                except socket.timeout:
                    logging.warning("Таймаут подключения")
                except Exception as e:
                    logging.error(f"Ошибка обработки запроса: {e}")
                finally:
                    client_sock.close()
                    logging.info("Соединение закрыто")

            except KeyboardInterrupt:
                logging.info("Получен сигнал прерывания")
                break
            except Exception as e:
                logging.error(f"Ошибка сервера: {e}")

    except Exception as e:
        logging.error(f"Критическая ошибка запуска сервера: {e}")
    finally:
        if 'server_sock' in locals():
            server_sock.close()
            logging.info("Сервер остановлен")


if __name__ == "__main__":
    logging.info("=" * 60)
    logging.info("=== Bluetooth IP Server для Klipper ===")
    logging.info("=" * 60)
    start_rfcomm_server()
