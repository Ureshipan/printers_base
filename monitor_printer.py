#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import json
import time
import argparse
import sys
from datetime import datetime, timedelta

# Цвета для вывода
GREEN = "\033[92m"
RED = "\033[91m"
BLUE = "\033[94m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"

def print_colored(color, prefix, message):
    print(f"{color}[{prefix}]{RESET} {message}")

def print_success(message):
    print_colored(GREEN, "УСПЕХ", message)

def print_error(message):
    print_colored(RED, "ОШИБКА", message)

def print_info(message):
    print_colored(BLUE, "ИНФО", message)

def print_warning(message):
    print_colored(YELLOW, "ВНИМАНИЕ", message)

def print_status(message):
    print_colored(CYAN, "СТАТУС", message)

def format_time(seconds):
    """Форматирует время в читаемом виде"""
    if seconds is None:
        return "неизвестно"
    
    seconds = int(seconds)
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    
    if h > 0:
        return f"{h}ч {m}м {s}с"
    elif m > 0:
        return f"{m}м {s}с"
    else:
        return f"{s}с"

def format_temperature(temp, target=None):
    """Форматирует температуру"""
    if target and target > 0:
        return f"{temp:.1f}°C / {target:.1f}°C"
    return f"{temp:.1f}°C"

class MoonrakerClient:
    def __init__(self, host, port=7125):
        self.base_url = f"http://{host}:{port}"
        self.session = requests.Session()
    
    def request(self, endpoint, method="GET", params=None, data=None):
        """Выполняет HTTP-запрос к API Moonraker"""
        url = f"{self.base_url}/{endpoint}"
        try:
            if method == "GET":
                response = self.session.get(url, params=params, timeout=10)
            elif method == "POST":
                response = self.session.post(url, params=params, json=data, timeout=10)
            
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print_error(f"Ошибка HTTP-запроса: {e}")
            return None
    
    def get_server_info(self):
        """Получает информацию о сервере"""
        return self.request("server/info")
    
    def get_printer_info(self):
        """Получает информацию о принтере"""
        return self.request("printer/info")
    
    def query_objects(self, objects):
        """Запрашивает объекты принтера"""
        return self.request("printer/objects/query", params=objects)
    
    def get_temperatures(self):
        """Получает текущие температуры"""
        objects = {
            "extruder": None,
            "heater_bed": None
        }
        result = self.query_objects(objects)
        if result and "result" in result and "status" in result["result"]:
            return result["result"]["status"]
        return None
    
    def get_print_status(self):
        """Получает статус печати"""
        objects = {
            "webhooks": None,
            "virtual_sdcard": None,
            "print_stats": None,
            "display_status": None
        }
        result = self.query_objects(objects)
        if result and "result" in result and "status" in result["result"]:
            return result["result"]["status"]
        return None
    
    def get_file_metadata(self, filename):
        """Получает метаданные файла"""
        return self.request(f"server/files/metadata?filename={filename}")

def monitor_printer(host, port, interval, count=None):
    """Мониторит состояние принтера"""
    client = MoonrakerClient(host, port)
    
    # Проверяем соединение
    server_info = client.get_server_info()
    if not server_info or "result" not in server_info:
        print_error("Не удалось подключиться к серверу Moonraker")
        sys.exit(1)
    
    klippy_state = server_info["result"]["klippy_state"]
    print_info(f"Подключено к серверу Moonraker, Klippy: {klippy_state}")
    
    if klippy_state != "ready":
        print_warning(f"Klippy не готов: {klippy_state}")
        if "klippy_message" in server_info["result"]:
            print_warning(f"Сообщение: {server_info['result']['klippy_message']}")
        sys.exit(1)
    
    # Получаем информацию о принтере
    printer_info = client.get_printer_info()
    if printer_info and "result" in printer_info:
        print_info(f"Принтер: {printer_info['result'].get('hostname', 'Неизвестно')}")
    
    # Основной цикл мониторинга
    iteration = 0
    try:
        while True:
            iteration += 1
            if count and iteration > count:
                break
            
            print("\n" + "=" * 50)
            print_status(f"Проверка #{iteration} - {datetime.now().strftime('%H:%M:%S')}")
            
            # Получаем статус печати
            print_info("Получение статуса печати...")
            status = client.get_print_status()
            
            if not status:
                print_error("Не удалось получить статус печати")
                time.sleep(interval)
                continue
            
            # Проверяем состояние Klipper
            if "webhooks" in status:
                webhooks_state = status["webhooks"]["state"]
                print_info(f"Состояние Klipper: {webhooks_state}")
                
                if webhooks_state != "ready":
                    print_warning(f"Klipper не готов: {webhooks_state}")
                    print_warning(f"Сообщение: {status['webhooks'].get('message', 'Неизвестно')}")
                    time.sleep(interval)
                    continue
            
            # Получаем температуры
            temps = client.get_temperatures()
            if temps:
                if "extruder" in temps:
                    ext_temp = temps["extruder"]["temperature"]
                    ext_target = temps["extruder"]["target"]
                    print_info(f"Экструдер: {format_temperature(ext_temp, ext_target)}")
                
                if "heater_bed" in temps:
                    bed_temp = temps["heater_bed"]["temperature"]
                    bed_target = temps["heater_bed"]["target"]
                    print_info(f"Стол: {format_temperature(bed_temp, bed_target)}")
            
            # Анализируем статус печати
            if "print_stats" in status:
                print_stats = status["print_stats"]
                state = print_stats["state"]
                
                # Выводим состояние печати
                print_info(f"Состояние печати: {state}")
                
                if state != "standby":
                    filename = print_stats.get("filename", "Неизвестно")
                    print_info(f"Файл: {filename}")
                    
                    # Продолжительность печати
                    if "print_duration" in print_stats:
                        duration = print_stats["print_duration"]
                        print_info(f"Длительность: {format_time(duration)}")
                    
                    # Получаем прогресс
                    if "virtual_sdcard" in status:
                        vsd = status["virtual_sdcard"]
                        if "progress" in vsd and vsd["progress"] > 0:
                            progress = vsd["progress"] * 100
                            print_info(f"Прогресс: {progress:.1f}%")
                            
                            # Расчёт ETA
                            if "print_duration" in print_stats and vsd["progress"] > 0:
                                duration = print_stats["print_duration"]
                                elapsed = duration
                                total_time = elapsed / vsd["progress"]
                                eta = total_time - elapsed
                                
                                print_info(f"Осталось: {format_time(eta)}")
                                
                                # Расчёт ожидаемого времени завершения
                                finish_time = datetime.now() + timedelta(seconds=eta)
                                print_info(f"Ожидаемое время завершения: {finish_time.strftime('%H:%M:%S')}")
                    
                    # Скорость печати
                    if "display_status" in status:
                        display = status["display_status"]
                        if "speed_factor" in display:
                            speed = display["speed_factor"] * 100
                            print_info(f"Скорость: {speed:.0f}%")
            
            time.sleep(interval)
    
    except KeyboardInterrupt:
        print_info("\nМониторинг остановлен")

def main():
    parser = argparse.ArgumentParser(description="Мониторинг статуса 3D-принтера через Moonraker API")
    parser.add_argument("--host", default="192.168.10.14", help="Хост Moonraker (по умолчанию: 192.168.10.14)")
    parser.add_argument("--port", type=int, default=7125, help="Порт Moonraker (по умолчанию: 7125)")
    parser.add_argument("--interval", type=int, default=5, help="Интервал проверки в секундах (по умолчанию: 5)")
    parser.add_argument("--count", type=int, help="Количество проверок (по умолчанию: бесконечно)")
    
    args = parser.parse_args()
    
    print_info(f"Мониторинг принтера на {args.host}:{args.port}")
    print_info(f"Интервал проверки: {args.interval} секунд")
    if args.count:
        print_info(f"Количество проверок: {args.count}")
    
    monitor_printer(args.host, args.port, args.interval, args.count)

if __name__ == "__main__":
    main() 