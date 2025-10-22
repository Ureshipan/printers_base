#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bluetooth Discovery модуль для обнаружения принтеров
Использует PyBluez для сканирования устройств
"""

import json
from typing import Optional, List, Dict
import time

try:
    import bluetooth

    BLUETOOTH_AVAILABLE = True
except ImportError:
    BLUETOOTH_AVAILABLE = False
    print("⚠ PyBluez не установлен. Установите: pip install pybluez")


class BluetoothPrinterDiscovery:
    """Класс для обнаружения принтеров через Bluetooth"""

    def __init__(self):
        self.discovered_devices = []

    def scan_devices(self, duration: int = 8) -> List[Dict]:
        """
        Сканирование Bluetooth устройств

        Args:
            duration: длительность сканирования в секундах

        Returns:
            Список обнаруженных устройств
        """
        if not BLUETOOTH_AVAILABLE:
            print("❌ Bluetooth недоступен")
            return []

        print(f"🔍 Сканирование Bluetooth устройств ({duration} сек)...")
        self.discovered_devices = []

        try:
            nearby_devices = bluetooth.discover_devices(
                duration=duration,
                lookup_names=True,
                lookup_class=True
            )

            for addr, name, device_class in nearby_devices:
                device_info = {
                    'mac': addr,
                    'name': name,
                    'class': device_class,
                    'discovered_at': time.time()
                }
                self.discovered_devices.append(device_info)
                print(f"  ✓ {name} ({addr})")

            print(f"\n✓ Найдено устройств: {len(self.discovered_devices)}")
            return self.discovered_devices

        except Exception as e:
            print(f"❌ Ошибка сканирования: {e}")
            return []

    def find_printer_by_name(self, printer_name: str) -> Optional[Dict]:
        """Поиск принтера по имени"""
        for device in self.discovered_devices:
            if printer_name.lower() in device['name'].lower():
                return device
        return None

    def request_ip_from_device(self, mac_address: str) -> Optional[str]:
        """
        Запрос IP-адреса от Bluetooth устройства
        Предполагается, что устройство транслирует IP через RFCOMM

        Args:
            mac_address: MAC-адрес устройства

        Returns:
            IP-адрес или None
        """
        if not BLUETOOTH_AVAILABLE:
            print("❌ Bluetooth недоступен")
            return None

        try:
            print(f"🔗 Поиск сервисов на {mac_address}...")
            # Поиск доступных сервисов на устройстве
            services = bluetooth.find_service(address=mac_address)

            if not services:
                print(f"❌ Сервисы не найдены на {mac_address}")
                return None

            # Ищем сервис для передачи IP (обычно RFCOMM)
            for service in services:
                service_name = service.get("name", "")
                if "Serial" in service_name or "IP" in service_name or "Klipper" in service_name:
                    host = service.get("host")
                    port = service.get("port")

                    print(f"  ✓ Найден сервис: {service_name} на порту {port}")

                    # Подключение к сервису
                    sock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
                    sock.connect((host, port))
                    sock.settimeout(5.0)

                    # Отправка запроса IP
                    sock.send(b"GET_IP\n")

                    # Получение ответа
                    response = sock.recv(1024).decode('utf-8').strip()
                    sock.close()

                    # Валидация IP
                    if self._is_valid_ip(response):
                        print(f"✓ Получен IP: {response}")
                        return response
                    else:
                        print(f"⚠ Получен некорректный ответ: {response}")

        except Exception as e:
            print(f"❌ Ошибка получения IP от {mac_address}: {e}")

        return None

    @staticmethod
    def _is_valid_ip(ip_string: str) -> bool:
        """Проверка валидности IP-адреса"""
        parts = ip_string.split('.')
        if len(parts) != 4:
            return False
        try:
            return all(0 <= int(part) <= 255 for part in parts)
        except ValueError:
            return False


class MockBluetoothDiscovery:
    """Mock-класс для тестирования без Bluetooth"""

    def scan_devices(self, duration: int = 8) -> List[Dict]:
        """Имитация сканирования"""
        print(f"🔍 [MOCK] Имитация Bluetooth сканирования ({duration} сек)...")
        time.sleep(1)  # Имитация задержки

        devices = [
            {
                'mac': '00:11:22:33:44:55',
                'name': 'Klipper_Printer_001',
                'class': 0x1F00,
                'discovered_at': time.time()
            },
            {
                'mac': '00:11:22:33:44:66',
                'name': 'Klipper_Printer_002',
                'class': 0x1F00,
                'discovered_at': time.time()
            }
        ]

        for dev in devices:
            print(f"  ✓ [MOCK] {dev['name']} ({dev['mac']})")

        print(f"\n✓ [MOCK] Найдено устройств: {len(devices)}")
        return devices

    def request_ip_from_device(self, mac_address: str) -> Optional[str]:
        """Имитация получения IP"""
        print(f"🔗 [MOCK] Запрос IP от {mac_address}...")
        time.sleep(0.5)

        mock_ips = {
            '00:11:22:33:44:55': '192.168.10.14',
            '00:11:22:33:44:66': '192.168.10.15'
        }

        ip = mock_ips.get(mac_address)
        if ip:
            print(f"✓ [MOCK] Получен IP: {ip}")
        else:
            print(f"❌ [MOCK] IP не найден для {mac_address}")

        return ip


if __name__ == '__main__':
    # Тест модуля
    if BLUETOOTH_AVAILABLE:
        discovery = BluetoothPrinterDiscovery()
    else:
        discovery = MockBluetoothDiscovery()

    devices = discovery.scan_devices(duration=3)

    if devices:
        print("\n" + "=" * 50)
        print("Попытка получить IP от первого устройства...")
        ip = discovery.request_ip_from_device(devices[0]['mac'])
        if ip:
            print(f"IP-адрес: {ip}")
