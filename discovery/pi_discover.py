#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Автоматический поиск Raspberry Pi с Moonraker по всем локальным подсетям
"""

import socket
import concurrent.futures
import argparse
from typing import List, Dict
import netifaces


def get_all_local_subnets():
    """Получить все локальные подсети на устройстве"""
    subnets = []
    try:
        interfaces = netifaces.interfaces()
        for iface in interfaces:
            addrs = netifaces.ifaddresses(iface)
            if netifaces.AF_INET in addrs:
                for addr_info in addrs[netifaces.AF_INET]:
                    ip = addr_info.get('addr')
                    if ip and not ip.startswith('127.'):
                        subnet = '.'.join(ip.split('.')[:3])
                        subnets.append((subnet, ip, iface))
    except Exception as e:
        print(f"⚠ Ошибка определения подсетей: {e}")
    return subnets


def check_moonraker(ip, port=7125, timeout=0.3):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((ip, port))
        sock.close()
        return ip if result == 0 else None
    except:
        return None


def scan_subnet_for_printers(subnet=None, start=1, end=254, max_workers=50):
    if subnet is None:
        print("✗ Нет подсети для сканирования")
        return []

    print(f"Сканируем подсеть {subnet}.{start}-{end} на порт 7125 (Moonraker)")
    found_printers = []

    def check_host(host_num):
        ip = f"{subnet}.{host_num}"
        if check_moonraker(ip):
            return ip
        return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(check_host, i) for i in range(start, end + 1)]
        for future in concurrent.futures.as_completed(futures):
            ip = future.result()
            if ip:
                found_printers.append(ip)
                print(f"✓ Найден принтер на {ip}")

    print(f"Всего найдено: {len(found_printers)}")
    return found_printers


def main():
    parser = argparse.ArgumentParser(
        description='Автоматический поиск Raspberry Pi принтеров во всех локальных подсетях'
    )
    parser.add_argument(
        '--start', type=int, default=1,
        help='Начальный хост для сканирования (default: 1)'
    )
    parser.add_argument(
        '--end', type=int, default=254,
        help='Конечный хост для сканирования (default: 254)'
    )
    parser.add_argument(
        '-w', '--workers', type=int, default=50,
        help='Число потоков (default: 50)'
    )

    args = parser.parse_args()

    subnets = get_all_local_subnets()
    if not subnets:
        print("✗ Не найдены сетевые интерфейсы с IPv4 адресами")
        return

    all_found = []
    for subnet, ip, iface in subnets:
        print(f"\nСканируем подсеть {subnet}.x через интерфейс {iface} (IP {ip})")
        found = scan_subnet_for_printers(subnet, args.start, args.end, args.workers)
        all_found.extend(found)

    if all_found:
        print("\nОбнаружены Raspberry Pi принтеры по адресам:")
        for i, ip in enumerate(all_found, 1):
            print(f"  [{i}] {ip}")
    else:
        print("\nНе найдено ни одного принтера во всех локальных подсетях.")


if __name__ == '__main__':
    main()
