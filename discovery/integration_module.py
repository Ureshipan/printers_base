#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Интеграционный модуль для обнаружения и подключения к принтерам
Комбинирует все методы обнаружения
"""

from typing import Optional, List, Dict
from config_manager import PrinterConfig
from bluetooth_discovery import BluetoothPrinterDiscovery, MockBluetoothDiscovery, BLUETOOTH_AVAILABLE
from mdns_discovery import MDNSPrinterDiscovery, SSDPPrinterDiscovery


class PrinterDiscoveryManager:
    """Менеджер для обнаружения и управления принтерами"""

    def __init__(self, config_path: str = "printer_config.json"):
        self.config = PrinterConfig(config_path)

        # Инициализация методов обнаружения
        if BLUETOOTH_AVAILABLE:
            self.bt_discovery = BluetoothPrinterDiscovery()
        else:
            self.bt_discovery = MockBluetoothDiscovery()

        self.mdns_discovery = MDNSPrinterDiscovery()
        self.ssdp_discovery = SSDPPrinterDiscovery()

    def discover_all(self, methods: List[str] = None) -> Dict[str, List[Dict]]:
        """
        Обнаружение принтеров всеми доступными методами

        Args:
            methods: список методов ['bluetooth', 'mdns', 'ssdp'] или None для всех

        Returns:
            Словарь с результатами по каждому методу
        """
        if methods is None:
            methods = ['bluetooth', 'mdns', 'ssdp']

        results = {}

        if 'bluetooth' in methods:
            print("\n" + "=" * 60)
            print("📱 BLUETOOTH ОБНАРУЖЕНИЕ")
            print("=" * 60)
            results['bluetooth'] = self.bt_discovery.scan_devices(duration=8)

        if 'mdns' in methods:
            print("\n" + "=" * 60)
            print("🌐 mDNS ОБНАРУЖЕНИЕ")
            print("=" * 60)
            results['mdns'] = self.mdns_discovery.start_discovery(timeout=10)

        if 'ssdp' in methods:
            print("\n" + "=" * 60)
            print("🔌 SSDP ОБНАРУЖЕНИЕ")
            print("=" * 60)
            results['ssdp'] = self.ssdp_discovery.discover_upnp_printers(timeout=5)

        return results

    def add_printer_from_bluetooth(self, bt_device: Dict, fetch_ip: bool = True) -> Optional[str]:
        """
        Добавление принтера, обнаруженного через Bluetooth

        Args:
            bt_device: информация о Bluetooth устройстве
            fetch_ip: пытаться получить IP от устройства

        Returns:
            ID добавленного принтера или None
        """
        mac = bt_device['mac']
        name = bt_device['name']

        # Попытка получить IP от устройства
        host = None
        if fetch_ip:
            print(f"\n🔗 Запрос IP от {name} ({mac})...")
            host = self.bt_discovery.request_ip_from_device(mac)

        # Если IP не получен, запросить вручную
        if not host:
            print(f"\n⚠ Не удалось получить IP автоматически от {name}")
            host = input(f"Введите IP-адрес для {name}: ").strip()

            if not host:
                print("❌ IP не указан, принтер не добавлен")
                return None

        # Добавление в конфигурацию
        printer_id = self.config.add_printer(
            name=name,
            host=host,
            port=7125,
            bluetooth_mac=mac,
            auto_discovered=True
        )

        print(f"✓ Принтер {name} добавлен с IP {host}")
        return printer_id

    def add_printer_from_mdns(self, mdns_device: Dict) -> Optional[str]:
        """Добавление принтера из mDNS обнаружения"""
        name = mdns_device['name']
        host = mdns_device['host']
        port = mdns_device['port']

        if not host:
            print(f"❌ IP адрес не найден для {name}")
            return None

        printer_id = self.config.add_printer(
            name=name,
            host=host,
            port=port,
            auto_discovered=True
        )

        print(f"✓ Принтер {name} добавлен с IP {host}:{port}")
        return printer_id

    def add_printer_manually(self, name: str, host: str, port: int = 7125) -> Optional[str]:
        """Ручное добавление принтера"""
        printer_id = self.config.add_printer(
            name=name,
            host=host,
            port=port,
            auto_discovered=False
        )

        print(f"✓ Принтер {name} добавлен вручную: {host}:{port}")
        return printer_id

    def update_printer_ip_from_bluetooth(self, printer_id: str) -> bool:
        """Обновление IP принтера через Bluetooth"""
        printer = self.config.get_printer(printer_id)

        if not printer:
            print(f"❌ Принтер {printer_id} не найден")
            return False

        mac = printer.get('bluetooth_mac')
        if not mac:
            print(f"❌ У принтера {printer_id} нет привязанного Bluetooth MAC")
            return False

        print(f"🔗 Запрос обновленного IP от {printer['name']} ({mac})...")
        new_ip = self.bt_discovery.request_ip_from_device(mac)

        if new_ip:
            self.config.update_printer_ip(printer_id, new_ip)
            print(f"✓ IP обновлен: {new_ip}")
            return True
        else:
            print("❌ Не удалось получить IP")
            return False

    def list_configured_printers(self) -> List[Dict]:
        """Список сохраненных принтеров"""
        return self.config.list_printers()

    def get_connection_params(self, printer_id: str) -> Optional[Dict]:
        """Получение параметров подключения для принтера"""
        printer = self.config.get_printer(printer_id)

        if not printer:
            return None

        return {
            'host': printer['host'],
            'port': printer['port'],
            'base_url': f"http://{printer['host']}:{printer['port']}",
            'ws_url': f"ws://{printer['host']}:{printer['port']}/websocket"
        }


if __name__ == '__main__':
    # Тест модуля
    print("=" * 60)
    print("PRINTER DISCOVERY MANAGER - TEST")
    print("=" * 60)

    manager = PrinterDiscoveryManager()

    # Список сохраненных принтеров
    print("\n📋 Сохраненные принтеры:")
    printers = manager.list_configured_printers()
    if printers:
        for p in printers:
            print(f"  - {p['name']} ({p['host']}:{p['port']})")
    else:
        print("  (нет сохраненных принтеров)")

    # Тестовое обнаружение
    print("\n🔍 Запуск тестового обнаружения...")
    results = manager.discover_all(methods=['bluetooth'])

    print("\n" + "=" * 60)
    print("ТЕСТ ЗАВЕРШЕН")
    print("=" * 60)
