#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Configuration Manager для управления настройками принтеров
Поддерживает сохранение и загрузку IP-адресов через Bluetooth и ручной ввод
"""

import json
import os
from typing import Optional, Dict, List
from datetime import datetime


class PrinterConfig:
    """Класс для работы с конфигурацией принтеров"""

    def __init__(self, config_path: str = "printer_config.json"):
        self.config_path = config_path
        self.printers: Dict[str, Dict] = {}
        self.load_config()

    def load_config(self):
        """Загрузка конфигурации из файла"""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.printers = data.get('printers', {})
                print(f"✓ Загружено {len(self.printers)} принтеров из конфигурации")
            except Exception as e:
                print(f"⚠ Ошибка загрузки конфигурации: {e}")
                self.printers = {}
        else:
            print("ℹ Файл конфигурации не найден, будет создан новый")
            self.printers = {}

    def save_config(self):
        """Сохранение конфигурации в файл"""
        try:
            data = {
                'printers': self.printers,
                'last_updated': datetime.now().isoformat()
            }
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"⚠ Ошибка сохранения конфигурации: {e}")
            return False

    def add_printer(self, name: str, host: str, port: int = 7125,
                    bluetooth_mac: Optional[str] = None, auto_discovered: bool = False):
        """Добавление принтера в конфигурацию"""
        printer_id = name.lower().replace(' ', '_').replace('-', '_')
        self.printers[printer_id] = {
            'name': name,
            'host': host,
            'port': port,
            'bluetooth_mac': bluetooth_mac,
            'auto_discovered': auto_discovered,
            'added_at': datetime.now().isoformat(),
            'last_seen': datetime.now().isoformat()
        }
        self.save_config()
        return printer_id

    def update_printer_ip(self, printer_id: str, new_host: str):
        """Обновление IP-адреса принтера"""
        if printer_id in self.printers:
            self.printers[printer_id]['host'] = new_host
            self.printers[printer_id]['last_seen'] = datetime.now().isoformat()
            self.save_config()
            return True
        return False

    def get_printer(self, printer_id: str) -> Optional[Dict]:
        """Получение конфигурации принтера"""
        return self.printers.get(printer_id)

    def list_printers(self) -> List[Dict]:
        """Список всех принтеров"""
        return [
            {'id': pid, **data}
            for pid, data in self.printers.items()
        ]

    def remove_printer(self, printer_id: str) -> bool:
        """Удаление принтера"""
        if printer_id in self.printers:
            del self.printers[printer_id]
            self.save_config()
            return True
        return False


if __name__ == '__main__':
    # Тест модуля
    config = PrinterConfig()

    # Добавление тестового принтера
    printer_id = config.add_printer(
        name="Test Printer",
        host="192.168.1.100",
        port=7125,
        bluetooth_mac="00:11:22:33:44:55",
        auto_discovered=True
    )

    print(f"\nДобавлен принтер: {printer_id}")
    print("\nСписок принтеров:")
    for p in config.list_printers():
        print(f"  - {p['name']} ({p['host']}:{p['port']})")
