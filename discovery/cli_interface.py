#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CLI интерфейс для управления обнаружением принтеров
"""

import argparse
import sys
from typing import Optional
from integration_module import PrinterDiscoveryManager


def print_menu():
    """Вывод главного меню"""
    print("\n" + "=" * 60)
    print("  🖨️  PRINTER DISCOVERY & CONFIGURATION MANAGER")
    print("=" * 60)
    print("1. 🔍 Автоматическое обнаружение (все методы)")
    print("2. 📱 Bluetooth обнаружение")
    print("3. 🌐 mDNS обнаружение")
    print("4. ✏️  Добавить принтер вручную")
    print("5. 📋 Список сохраненных принтеров")
    print("6. 🔄 Обновить IP через Bluetooth")
    print("7. 🗑️  Удалить принтер")
    print("8. 🔗 Получить параметры подключения")
    print("0. 👋 Выход")
    print("=" * 60)


def handle_auto_discovery(manager: PrinterDiscoveryManager):
    """Обработка автоматического обнаружения"""
    print("\n🔍 Запуск автоматического обнаружения...")
    results = manager.discover_all()

    all_devices = []

    # Bluetooth устройства
    if 'bluetooth' in results and results['bluetooth']:
        print(f"\n📱 Bluetooth устройства ({len(results['bluetooth'])}):")
        for i, device in enumerate(results['bluetooth'], 1):
            print(f"  {i}. {device['name']} - {device['mac']}")
            all_devices.append(('bt', device))

    # mDNS устройства
    if 'mdns' in results and results['mdns']:
        print(f"\n🌐 mDNS устройства ({len(results['mdns'])}):")
        for i, device in enumerate(results['mdns'], len(all_devices) + 1):
            print(f"  {i}. {device['name']} - {device['host']}:{device['port']}")
            all_devices.append(('mdns', device))

    # SSDP устройства
    if 'ssdp' in results and results['ssdp']:
        print(f"\n🔌 SSDP устройства ({len(results['ssdp'])}):")
        for i, device in enumerate(results['ssdp'], len(all_devices) + 1):
            print(f"  {i}. {device['host']}")
            all_devices.append(('ssdp', device))

    if not all_devices:
        print("\n❌ Устройства не найдены")
        return

    # Выбор устройства для добавления
    print("\nВведите номер устройства для добавления (или 0 для отмены):")
    try:
        choice = int(input("> ").strip())
        if choice == 0:
            return

        if 1 <= choice <= len(all_devices):
            device_type, device = all_devices[choice - 1]

            if device_type == 'bt':
                manager.add_printer_from_bluetooth(device)
            elif device_type == 'mdns':
                manager.add_printer_from_mdns(device)
            elif device_type == 'ssdp':
                # Для SSDP нужен ручной ввод имени
                name = input("Введите имя принтера: ").strip()
                if name:
                    manager.add_printer_manually(name, device['host'])
        else:
            print("❌ Неверный номер")
    except ValueError:
        print("❌ Неверный ввод")
    except KeyboardInterrupt:
        print("\n⚠ Отменено пользователем")


def handle_bluetooth_discovery(manager: PrinterDiscoveryManager):
    """Обработка Bluetooth обнаружения"""
    print("\n📱 Запуск Bluetooth сканирования...")
    devices = manager.bt_discovery.scan_devices(duration=8)

    if not devices:
        print("❌ Bluetooth устройства не найдены")
        return

    print(f"\nНайдено устройств: {len(devices)}")
    for i, device in enumerate(devices, 1):
        print(f"{i}. {device['name']} - {device['mac']}")

    print("\nВведите номер для добавления (или 0 для отмены):")
    try:
        choice = int(input("> ").strip())
        if choice == 0:
            return

        if 1 <= choice <= len(devices):
            manager.add_printer_from_bluetooth(devices[choice - 1])
        else:
            print("❌ Неверный номер")
    except ValueError:
        print("❌ Неверный ввод")
    except KeyboardInterrupt:
        print("\n⚠ Отменено пользователем")


def handle_mdns_discovery(manager: PrinterDiscoveryManager):
    """Обработка mDNS обнаружения"""
    print("\n🌐 Запуск mDNS сканирования...")
    devices = manager.mdns_discovery.start_discovery(timeout=10)

    if not devices:
        print("❌ mDNS устройства не найдены")
        return

    print(f"\nНайдено устройств: {len(devices)}")
    for i, device in enumerate(devices, 1):
        print(f"{i}. {device['name']} - {device['host']}:{device['port']}")

    print("\nВведите номер для добавления (или 0 для отмены):")
    try:
        choice = int(input("> ").strip())
        if choice == 0:
            return

        if 1 <= choice <= len(devices):
            manager.add_printer_from_mdns(devices[choice - 1])
        else:
            print("❌ Неверный номер")
    except ValueError:
        print("❌ Неверный ввод")
    except KeyboardInterrupt:
        print("\n⚠ Отменено пользователем")


def handle_manual_add(manager: PrinterDiscoveryManager):
    """Обработка ручного добавления"""
    print("\n✏️  Ручное добавление принтера")
    print("-" * 40)

    try:
        name = input("Имя принтера: ").strip()
        host = input("IP адрес: ").strip()
        port_input = input("Порт (Enter = 7125): ").strip()

        port = 7125
        if port_input:
            try:
                port = int(port_input)
            except ValueError:
                print("⚠ Неверный порт, используется 7125")

        if name and host:
            manager.add_printer_manually(name, host, port)
        else:
            print("❌ Имя и IP обязательны")
    except KeyboardInterrupt:
        print("\n⚠ Отменено пользователем")


def handle_list_printers(manager: PrinterDiscoveryManager):
    """Вывод списка принтеров"""
    printers = manager.list_configured_printers()

    if not printers:
        print("\n📋 Сохраненных принтеров нет")
        return

    print(f"\n📋 Сохраненные принтеры ({len(printers)}):")
    print("=" * 80)
    for printer in printers:
        auto = "✓" if printer.get('auto_discovered') else "✗"
        bt_mac = printer.get('bluetooth_mac', 'N/A')
        print(f"\n🖨️  ID: {printer['id']}")
        print(f"   Имя: {printer['name']}")
        print(f"   Адрес: {printer['host']}:{printer['port']}")
        print(f"   Bluetooth: {bt_mac}")
        print(f"   Авто-обнаружен: {auto}")
        print(f"   Добавлен: {printer['added_at']}")
    print("=" * 80)


def handle_update_ip(manager: PrinterDiscoveryManager):
    """Обновление IP через Bluetooth"""
    printers = manager.list_configured_printers()

    # Фильтр принтеров с Bluetooth
    bt_printers = [p for p in printers if p.get('bluetooth_mac')]

    if not bt_printers:
        print("\n❌ Нет принтеров с привязанным Bluetooth")
        return

    print(f"\n🔄 Принтеры с Bluetooth ({len(bt_printers)}):")
    for i, printer in enumerate(bt_printers, 1):
        print(f"{i}. {printer['name']} - {printer['bluetooth_mac']}")

    print("\nВведите номер принтера для обновления IP:")
    try:
        choice = int(input("> ").strip())
        if 1 <= choice <= len(bt_printers):
            printer_id = bt_printers[choice - 1]['id']
            manager.update_printer_ip_from_bluetooth(printer_id)
        else:
            print("❌ Неверный номер")
    except ValueError:
        print("❌ Неверный ввод")
    except KeyboardInterrupt:
        print("\n⚠ Отменено пользователем")


def handle_delete_printer(manager: PrinterDiscoveryManager):
    """Удаление принтера"""
    printers = manager.list_configured_printers()

    if not printers:
        print("\n❌ Нет принтеров для удаления")
        return

    print(f"\n🗑️  Удаление принтера:")
    for i, printer in enumerate(printers, 1):
        print(f"{i}. {printer['name']} - {printer['host']}")

    print("\nВведите номер для удаления:")
    try:
        choice = int(input("> ").strip())
        if 1 <= choice <= len(printers):
            printer = printers[choice - 1]
            confirm = input(f"Удалить {printer['name']}? (y/n): ").strip().lower()
            if confirm == 'y':
                manager.config.remove_printer(printer['id'])
                print(f"✓ Принтер {printer['name']} удален")
        else:
            print("❌ Неверный номер")
    except ValueError:
        print("❌ Неверный ввод")
    except KeyboardInterrupt:
        print("\n⚠ Отменено пользователем")


def handle_get_connection(manager: PrinterDiscoveryManager):
    """Получение параметров подключения"""
    printers = manager.list_configured_printers()

    if not printers:
        print("\n❌ Нет сохраненных принтеров")
        return

    print(f"\n🔗 Выберите принтер:")
    for i, printer in enumerate(printers, 1):
        print(f"{i}. {printer['name']} - {printer['host']}")

    print("\nВведите номер:")
    try:
        choice = int(input("> ").strip())
        if 1 <= choice <= len(printers):
            printer_id = printers[choice - 1]['id']
            params = manager.get_connection_params(printer_id)

            if params:
                print("\n📡 Параметры подключения:")
                print("=" * 60)
                print(f"  Host: {params['host']}")
                print(f"  Port: {params['port']}")
                print(f"  HTTP URL: {params['base_url']}")
                print(f"  WebSocket URL: {params['ws_url']}")
                print("=" * 60)
        else:
            print("❌ Неверный номер")
    except ValueError:
        print("❌ Неверный ввод")
    except KeyboardInterrupt:
        print("\n⚠ Отменено пользователем")


def interactive_mode():
    """Интерактивный режим"""
    manager = PrinterDiscoveryManager()

    while True:
        try:
            print_menu()
            choice = input("\nВыберите опцию: ").strip()

            if choice == '1':
                handle_auto_discovery(manager)
            elif choice == '2':
                handle_bluetooth_discovery(manager)
            elif choice == '3':
                handle_mdns_discovery(manager)
            elif choice == '4':
                handle_manual_add(manager)
            elif choice == '5':
                handle_list_printers(manager)
            elif choice == '6':
                handle_update_ip(manager)
            elif choice == '7':
                handle_delete_printer(manager)
            elif choice == '8':
                handle_get_connection(manager)
            elif choice == '0':
                print("\n👋 Выход")
                break
            else:
                print("\n❌ Неверная опция")

        except KeyboardInterrupt:
            print("\n\n👋 Выход")
            break
        except Exception as e:
            print(f"\n❌ Ошибка: {e}")


def main():
    """Главная функция"""
    parser = argparse.ArgumentParser(
        description='Printer Discovery & Configuration Manager',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  %(prog)s --interactive          Интерактивный режим
  %(prog)s --list                 Список принтеров
  %(prog)s --discover all         Автоматическое обнаружение
  %(prog)s --discover bluetooth   Bluetooth обнаружение
  %(prog)s --discover mdns        mDNS обнаружение
  %(prog)s --add-manual "Printer" "192.168.1.10"
        """
    )
    parser.add_argument(
        '--interactive', '-i',
        action='store_true',
        help='Интерактивный режим'
    )
    parser.add_argument(
        '--list', '-l',
        action='store_true',
        help='Список сохраненных принтеров'
    )
    parser.add_argument(
        '--discover',
        choices=['all', 'bluetooth', 'mdns'],
        help='Метод обнаружения'
    )
    parser.add_argument(
        '--add-manual',
        nargs=2,
        metavar=('NAME', 'IP'),
        help='Добавить принтер вручную'
    )

    args = parser.parse_args()
    manager = PrinterDiscoveryManager()

    if args.interactive or len(sys.argv) == 1:
        interactive_mode()
    elif args.list:
        handle_list_printers(manager)
    elif args.discover:
        if args.discover == 'all':
            handle_auto_discovery(manager)
        elif args.discover == 'bluetooth':
            handle_bluetooth_discovery(manager)
        elif args.discover == 'mdns':
            handle_mdns_discovery(manager)
    elif args.add_manual:
        name, ip = args.add_manual
        manager.add_printer_manually(name, ip)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
