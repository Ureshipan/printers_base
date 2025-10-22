#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mDNS Discovery модуль для автоматического обнаружения принтеров в сети
Использует Zeroconf для поиска Moonraker сервисов
"""

from typing import List, Dict, Optional
import socket
import time

try:
    from zeroconf import Zeroconf, ServiceBrowser, ServiceStateChange, ServiceListener

    ZEROCONF_AVAILABLE = True
except ImportError:
    ZEROCONF_AVAILABLE = False
    print("⚠ Zeroconf не установлен. Установите: pip install zeroconf")


class MoonrakerServiceListener(ServiceListener):
    """Слушатель mDNS сервисов Moonraker"""

    def __init__(self):
        self.discovered_printers: Dict[str, Dict] = {}

    def add_service(self, zc: Zeroconf, service_type: str, name: str):
        """Callback при обнаружении сервиса"""
        info = zc.get_service_info(service_type, name)
        if info:
            addresses = [socket.inet_ntoa(addr) for addr in info.addresses]
            printer_info = {
                'name': name,
                'addresses': addresses,
                'port': info.port,
                'server': info.server,
                'discovered_at': time.time()
            }
            self.discovered_printers[name] = printer_info
            print(f"  ✓ Обнаружен: {name} - {addresses[0]}:{info.port}")

    def remove_service(self, zc: Zeroconf, service_type: str, name: str):
        """Callback при удалении сервиса"""
        if name in self.discovered_printers:
            del self.discovered_printers[name]
            print(f"  ⚠ Отключен: {name}")

    def update_service(self, zc: Zeroconf, service_type: str, name: str):
        """Callback при обновлении сервиса"""
        self.add_service(zc, service_type, name)


class MDNSPrinterDiscovery:
    """Класс для обнаружения принтеров через mDNS/Zeroconf"""

    def __init__(self):
        self.zeroconf = None
        self.listener = None
        self.browser = None

    def start_discovery(self, timeout: int = 10) -> List[Dict]:
        """
        Запуск обнаружения принтеров

        Args:
            timeout: время сканирования в секундах

        Returns:
            Список обнаруженных принтеров
        """
        if not ZEROCONF_AVAILABLE:
            print("❌ Zeroconf недоступен")
            return []

        print(f"🔍 Запуск mDNS обнаружения ({timeout} сек)...")

        try:
            self.zeroconf = Zeroconf()
            self.listener = MoonrakerServiceListener()

            # Moonraker обычно публикуется как _http._tcp
            # но также может быть _moonraker._tcp или _octoprint._tcp
            service_types = [
                "_http._tcp.local.",
                "_moonraker._tcp.local.",
                "_octoprint._tcp.local.",
                "_printer._tcp.local."
            ]

            browsers = []
            for service_type in service_types:
                browser = ServiceBrowser(self.zeroconf, service_type, self.listener)
                browsers.append(browser)

            # Ожидание обнаружения
            time.sleep(timeout)

            # Фильтрация результатов - только Moonraker
            printers = []
            for name, info in self.listener.discovered_printers.items():
                # Проверка, что это Moonraker (по порту 7125)
                if info['port'] == 7125 or 'moonraker' in name.lower() or 'klipper' in name.lower():
                    printers.append({
                        'name': info['server'],
                        'host': info['addresses'][0] if info['addresses'] else None,
                        'port': info['port'],
                        'discovered_via': 'mDNS'
                    })

            print(f"\n✓ Обнаружено Moonraker принтеров: {len(printers)}")
            return printers

        except Exception as e:
            print(f"❌ Ошибка mDNS обнаружения: {e}")
            return []
        finally:
            if self.zeroconf:
                self.zeroconf.close()

    def stop_discovery(self):
        """Остановка обнаружения"""
        if self.zeroconf:
            self.zeroconf.close()
            self.zeroconf = None


class SSDPPrinterDiscovery:
    """Альтернативный метод через SSDP/UPnP"""

    SSDP_ADDR = "239.255.255.250"
    SSDP_PORT = 1900

    def discover_upnp_printers(self, timeout: int = 5) -> List[Dict]:
        """
        Обнаружение принтеров через SSDP

        Args:
            timeout: таймаут поиска

        Returns:
            Список обнаруженных устройств
        """
        print(f"🔍 Запуск SSDP обнаружения ({timeout} сек)...")

        msg = (
            'M-SEARCH * HTTP/1.1\r\n'
            f'HOST: {self.SSDP_ADDR}:{self.SSDP_PORT}\r\n'
            'MAN: "ssdp:discover"\r\n'
            'MX: 2\r\n'
            'ST: ssdp:all\r\n'
            '\r\n'
        )

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.settimeout(timeout)

        printers = []

        try:
            sock.sendto(msg.encode('utf-8'), (self.SSDP_ADDR, self.SSDP_PORT))

            while True:
                try:
                    data, addr = sock.recvfrom(65507)
                    response = data.decode('utf-8', errors='ignore')

                    # Парсинг ответа
                    if 'printer' in response.lower() or '7125' in response:
                        printers.append({
                            'host': addr[0],
                            'response': response,
                            'discovered_via': 'SSDP'
                        })
                        print(f"  ✓ Обнаружен: {addr[0]}")
                except socket.timeout:
                    break

            print(f"\n✓ Обнаружено SSDP устройств: {len(printers)}")

        except Exception as e:
            print(f"❌ Ошибка SSDP: {e}")
        finally:
            sock.close()

        return printers


if __name__ == '__main__':
    # Тест модуля
    print("=== Тест mDNS Discovery ===\n")

    if ZEROCONF_AVAILABLE:
        mdns = MDNSPrinterDiscovery()
        printers = mdns.start_discovery(timeout=5)

        if printers:
            print("\nНайденные принтеры:")
            for p in printers:
                print(f"  - {p['name']} ({p['host']}:{p['port']})")
    else:
        print("mDNS недоступен\n")

    print("\n=== Тест SSDP Discovery ===\n")
    ssdp = SSDPPrinterDiscovery()
    devices = ssdp.discover_upnp_printers(timeout=3)

    if devices:
        print("\nНайденные устройства:")
        for d in devices:
            print(f"  - {d['host']}")
