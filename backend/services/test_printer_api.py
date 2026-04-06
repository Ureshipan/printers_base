#!/usr/bin/env python3
"""
Тестовый скрипт для проверки Moonraker API.
Использование: python test_printer_api.py --host 192.168.51.106
"""

import argparse
import json
import sys
from datetime import datetime

import requests


def print_header(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)


def print_json(data: dict, indent: int = 2):
    print(json.dumps(data, indent=indent, ensure_ascii=False))


def test_server_info(base_url: str) -> dict | None:
    """Проверка /server/info"""
    print_header("1. Server Info")
    try:
        resp = requests.get(f"{base_url}/server/info", timeout=5)
        data = resp.json().get("result", {})
        print(f"  Moonraker: {data.get('moonraker_version', 'N/A')}")
        print(f"  Klippy state: {data.get('klippy_state', 'N/A')}")
        print(f"  Klippy connected: {data.get('klippy_connected', False)}")
        print(f"  WebSocket clients: {data.get('websocket_count', 0)}")
        return data
    except Exception as e:
        print(f"  ОШИБКА: {e}")
        return None


def test_printer_info(base_url: str) -> dict | None:
    """Проверка /printer/info"""
    print_header("2. Printer Info")
    try:
        resp = requests.get(f"{base_url}/printer/info", timeout=5)
        data = resp.json().get("result", {})
        print(f"  Hostname: {data.get('hostname', 'N/A')}")
        print(f"  Klipper: {data.get('software_version', 'N/A')}")
        print(f"  State: {data.get('state', 'N/A')}")
        print(f"  Message: {data.get('state_message', 'N/A')}")
        return data
    except Exception as e:
        print(f"  ОШИБКА: {e}")
        return None


def test_objects_query(base_url: str) -> dict | None:
    """Проверка /printer/objects/query - основной мониторинг"""
    print_header("3. Objects Query (мониторинг)")
    try:
        resp = requests.post(
            f"{base_url}/printer/objects/query",
            json={
                "objects": {
                    "webhooks": None,
                    "print_stats": None,
                    "virtual_sdcard": None,
                    "extruder": None,
                    "heater_bed": None,
                    "toolhead": None,
                    "fan": None,
                    "idle_timeout": None,
                }
            },
            timeout=5,
        )
        data = resp.json().get("result", {}).get("status", {})

        # Webhooks
        wh = data.get("webhooks", {})
        print(f"\n  [webhooks]")
        print(f"    state: {wh.get('state', 'N/A')}")

        # Print stats
        ps = data.get("print_stats", {})
        print(f"\n  [print_stats]")
        print(f"    state: {ps.get('state', 'N/A')}")
        print(f"    filename: {ps.get('filename', '') or '(none)'}")
        if ps.get("filename"):
            print(f"    duration: {ps.get('print_duration', 0):.1f}s")
            print(f"    filament: {ps.get('filament_used', 0):.1f}mm")

        # Virtual SD
        vsd = data.get("virtual_sdcard", {})
        print(f"\n  [virtual_sdcard]")
        print(f"    progress: {vsd.get('progress', 0)*100:.1f}%")
        print(f"    is_active: {vsd.get('is_active', False)}")

        # Temperatures
        ext = data.get("extruder", {})
        bed = data.get("heater_bed", {})
        print(f"\n  [temperatures]")
        print(f"    extruder: {ext.get('temperature', 0):.1f}°C / {ext.get('target', 0):.0f}°C")
        print(f"    bed: {bed.get('temperature', 0):.1f}°C / {bed.get('target', 0):.0f}°C")

        # Toolhead
        th = data.get("toolhead", {})
        pos = th.get("position", [0, 0, 0, 0])
        print(f"\n  [toolhead]")
        print(f"    position: X={pos[0]:.1f} Y={pos[1]:.1f} Z={pos[2]:.1f}")
        print(f"    homed: {th.get('homed_axes', '') or '(none)'}")

        # Fan
        fan = data.get("fan", {})
        print(f"\n  [fan]")
        print(f"    speed: {fan.get('speed', 0)*100:.0f}%")

        # Idle timeout
        it = data.get("idle_timeout", {})
        print(f"\n  [idle_timeout]")
        print(f"    state: {it.get('state', 'N/A')}")

        return data
    except Exception as e:
        print(f"  ОШИБКА: {e}")
        return None


def test_file_list(base_url: str) -> list | None:
    """Проверка списка файлов"""
    print_header("4. G-code Files")
    try:
        resp = requests.get(f"{base_url}/server/files/list?root=gcodes", timeout=5)
        files = resp.json().get("result", [])
        print(f"  Всего файлов: {len(files)}")
        if files:
            # Показать последние 5 по дате модификации
            sorted_files = sorted(files, key=lambda x: x.get("modified", 0), reverse=True)
            print(f"\n  Последние 5 файлов:")
            for f in sorted_files[:5]:
                mod_time = datetime.fromtimestamp(f.get("modified", 0)).strftime("%Y-%m-%d %H:%M")
                size_mb = f.get("size", 0) / 1024 / 1024
                print(f"    - {f.get('path', 'N/A')} ({size_mb:.1f} MB, {mod_time})")
        return files
    except Exception as e:
        print(f"  ОШИБКА: {e}")
        return None


def test_temperature_store(base_url: str) -> dict | None:
    """Проверка истории температур"""
    print_header("5. Temperature Store")
    try:
        resp = requests.get(f"{base_url}/server/temperature_store", timeout=5)
        data = resp.json().get("result", {})
        for sensor, values in data.items():
            temps = values.get("temperatures", [])
            if temps:
                print(f"  {sensor}: {len(temps)} записей, последняя: {temps[-1]:.1f}°C")
        return data
    except Exception as e:
        print(f"  ОШИБКА: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Тест Moonraker API")
    parser.add_argument("--host", default="192.168.51.106", help="IP принтера")
    parser.add_argument("--port", type=int, default=7125, help="Порт Moonraker")
    args = parser.parse_args()

    base_url = f"http://{args.host}:{args.port}"
    print(f"\n  Тестирование: {base_url}")
    print(f"  Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Запуск тестов
    server = test_server_info(base_url)
    if not server or not server.get("klippy_connected"):
        print("\n  ⚠️  Klipper не подключён, некоторые тесты пропущены")
        sys.exit(1)

    test_printer_info(base_url)
    test_objects_query(base_url)
    test_file_list(base_url)
    test_temperature_store(base_url)

    print_header("Готово!")
    print("  Все тесты выполнены успешно.\n")


if __name__ == "__main__":
    main()
