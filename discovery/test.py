#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fast Port Scanner для поиска Moonraker и других сервисов
Использует многопоточность для быстрого сканирования
"""

import socket
import concurrent.futures
from typing import List, Dict
import time

# Стандартные порты для 3D принтеров
COMMON_PRINTER_PORTS = [
    7125,  # Moonraker
    80,  # HTTP
    443,  # HTTPS
    8080,  # Alternate HTTP
    9090,  # Mainsail
    4408,  # Fluidd
    5000,  # OctoPrint
]

# Расширенный список портов для полного сканирования
EXTENDED_PORTS = list(range(1, 1024)) + list(range(7000, 8000)) + list(range(9000, 10000))


def check_port(ip: str, port: int, timeout: float = 0.5) -> Dict:
    """
    Проверка одного порта

    Args:
        ip: IP адрес
        port: Порт для проверки
        timeout: Таймаут подключения в секундах

    Returns:
        Dict с результатом
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((ip, port))
        sock.close()

        if result == 0:
            return {'port': port, 'status': 'open', 'service': identify_service(port)}
        else:
            return {'port': port, 'status': 'closed'}
    except socket.error:
        return {'port': port, 'status': 'error'}


def identify_service(port: int) -> str:
    """Определение сервиса по порту"""
    services = {
        80: 'HTTP',
        443: 'HTTPS',
        7125: 'Moonraker',
        8080: 'HTTP-Alt',
        9090: 'Mainsail',
        4408: 'Fluidd',
        5000: 'OctoPrint',
        22: 'SSH',
        21: 'FTP',
        3389: 'RDP',
    }
    return services.get(port, f'Unknown-{port}')


def fast_port_scan(ip: str, ports: List[int] = None,
                   max_workers: int = 100, timeout: float = 0.3) -> List[Dict]:
    """
    Быстрое многопоточное сканирование портов

    Args:
        ip: IP адрес для сканирования
        ports: Список портов (по умолчанию COMMON_PRINTER_PORTS)
        max_workers: Количество потоков
        timeout: Таймаут на порт (секунды)

    Returns:
        Список открытых портов с информацией
    """
    if ports is None:
        ports = COMMON_PRINTER_PORTS

    print(f"Сканирование {ip}")
    print(f"Портов для проверки: {len(ports)}")
    print(f"Потоков: {max_workers}, Таймаут: {timeout}s")
    print("-" * 60)

    open_ports = []
    start_time = time.time()

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_port = {
            executor.submit(check_port, ip, port, timeout): port
            for port in ports
        }

        completed = 0
        for future in concurrent.futures.as_completed(future_to_port):
            completed += 1
            result = future.result()

            if result['status'] == 'open':
                open_ports.append(result)
                print(f"✓ Порт {result['port']:5d} открыт - {result['service']}")

            # Прогресс
            if completed % 100 == 0:
                print(f"  Проверено: {completed}/{len(ports)}")

    elapsed = time.time() - start_time
    print(f"\nСканирование завершено за {elapsed:.2f}s")
    print(f"Найдено открытых портов: {len(open_ports)}")

    return open_ports


def scan_subnet_for_printers(subnet: str = "172.22.112",
                             start_host: int = 1,
                             end_host: int = 254) -> List[Dict]:
    """
    Сканирование подсети на наличие принтеров (порт 7125 Moonraker)

    Args:
        subnet: Подсеть (например "192.168.1")
        start_host: Начальный хост
        end_host: Конечный хост

    Returns:
        Список найденных устройств с Moonraker
    """
    print(f"Сканирование подсети {subnet}.{start_host}-{end_host} на порт 7125 (Moonraker)")
    print("-" * 60)

    found_printers = []

    def check_host(host_num):
        ip = f"{subnet}.{host_num}"
        result = check_port(ip, 7125, timeout=0.2)
        if result['status'] == 'open':
            return {'ip': ip, 'port': 7125, 'service': 'Moonraker'}
        return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        futures = [executor.submit(check_host, i) for i in range(start_host, end_host + 1)]

        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if result:
                found_printers.append(result)
                print(f"✓ Найден принтер: {result['ip']}")

    print(f"\nНайдено принтеров: {len(found_printers)}")
    return found_printers


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Быстрый сканер портов для принтеров')
    parser.add_argument('-i', '--ip', required=True, help='IP адрес для сканирования')
    parser.add_argument('-m', '--mode', choices=['fast', 'full', 'subnet'],
                        default='fast', help='Режим сканирования')
    parser.add_argument('--subnet', default='172.22.112',
                        help='Подсеть для режима subnet (default: 172.22.112)')
    parser.add_argument('-w', '--workers', type=int, default=100,
                        help='Количество потоков (default: 100)')

    args = parser.parse_args()

    print("=" * 60)
    print("FAST PORT SCANNER")
    print("=" * 60)

    if args.mode == 'subnet':
        # Сканирование подсети на Moonraker
        printers = scan_subnet_for_printers(args.subnet)

        if printers:
            print("\n" + "=" * 60)
            print("НАЙДЕННЫЕ ПРИНТЕРЫ:")
            for p in printers:
                print(f"  {p['ip']}:{p['port']} - {p['service']}")
    else:
        # Сканирование конкретного IP
        if args.mode == 'fast':
            ports = COMMON_PRINTER_PORTS
            print("Режим: Быстрое сканирование (стандартные порты)")
        else:
            ports = EXTENDED_PORTS
            print("Режим: Полное сканирование (1-10000)")

        open_ports = fast_port_scan(args.ip, ports, max_workers=args.workers)

        if open_ports:
            print("\n" + "=" * 60)
            print("ОТКРЫТЫЕ ПОРТЫ:")
            for p in open_ports:
                print(f"  {p['port']:5d} - {p['service']}")
        else:
            print("\n✗ Открытые порты не найдены")

    print("=" * 60)
