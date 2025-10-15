#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import json
import time
import sys
import os
import argparse
from datetime import datetime

# Цвета для вывода
GREEN = "\033[92m"
RED = "\033[91m"
BLUE = "\033[94m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"
BOLD = "\033[1m"

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

def print_header(message):
    print(f"\n{BOLD}{CYAN}{message}{RESET}")

def print_json(data):
    """Печатает JSON-объект в отформатированном виде"""
    print(json.dumps(data, ensure_ascii=False, indent=2))

def clear_screen():
    """Очищает экран консоли"""
    os.system('cls' if os.name == 'nt' else 'clear')

class MoonrakerClient:
    def __init__(self, host, port=7125):
        self.base_url = f"http://{host}:{port}"
        self.session = requests.Session()
    
    def request(self, endpoint, method="GET", params=None, json_data=None):
        """Выполняет HTTP-запрос к API Moonraker"""
        url = f"{self.base_url}/{endpoint}"
        try:
            if method == "GET":
                response = self.session.get(url, params=params, timeout=10)
            elif method == "POST":
                response = self.session.post(url, params=params, json=json_data, timeout=10)
            
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
        if isinstance(objects, dict):
            return self.request("printer/objects/query", params=objects)
        else:
            # Если передан список объектов, создаем словарь
            query_objects = {}
            for obj in objects:
                query_objects[obj] = None
            return self.request("printer/objects/query", params=query_objects)
    
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
    
    def send_gcode(self, gcode):
        """Отправляет G-code команду"""
        return self.request("printer/gcode/script", method="POST", json_data={"script": gcode})
    
    def get_gcode_help(self):
        """Получает справку по доступным G-code командам"""
        return self.request("printer/gcode/help")
    
    def restart_firmware(self):
        """Перезагружает прошивку"""
        return self.request("printer/firmware_restart", method="POST")
    
    def restart_host(self):
        """Перезагружает хост"""
        return self.request("printer/restart", method="POST")
    
    def emergency_stop(self):
        """Аварийная остановка"""
        return self.send_gcode("M112")
    
    def get_file_list(self, root=None):
        """Получает список файлов"""
        params = {}
        if root:
            params["root"] = root
        return self.request("server/files/list", params=params)

def check_klippy_ready(client):
    """Проверяет, готов ли Klippy к приему команд"""
    server_info = client.get_server_info()
    if not server_info or "result" not in server_info:
        print_error("Не удалось получить информацию о сервере")
        return False
    
    klippy_state = server_info["result"]["klippy_state"]
    if klippy_state == "ready":
        return True
    else:
        print_warning(f"Klippy не готов: {klippy_state}")
        if "klippy_message" in server_info["result"]:
            print_warning(f"Сообщение: {server_info['result']['klippy_message']}")
        return False

def display_printer_status(client):
    """Отображает статус принтера"""
    print_header("СТАТУС ПРИНТЕРА")
    
    status = client.get_print_status()
    if not status:
        print_error("Не удалось получить статус принтера")
        return
    
    # Проверяем состояние Klipper
    if "webhooks" in status:
        webhooks_state = status["webhooks"]["state"]
        print_info(f"Состояние Klipper: {webhooks_state}")
        
        if webhooks_state != "ready":
            print_warning(f"Сообщение: {status['webhooks'].get('message', 'Неизвестно')}")
    
    # Получаем температуры
    temps = client.get_temperatures()
    if temps:
        print_header("ТЕМПЕРАТУРЫ")
        if "extruder" in temps:
            ext_temp = temps["extruder"]["temperature"]
            ext_target = temps["extruder"]["target"]
            print_info(f"Экструдер: {ext_temp:.1f}°C / {ext_target:.1f}°C")
        
        if "heater_bed" in temps:
            bed_temp = temps["heater_bed"]["temperature"]
            bed_target = temps["heater_bed"]["target"]
            print_info(f"Стол: {bed_temp:.1f}°C / {bed_target:.1f}°C")
    
    # Анализируем статус печати
    if "print_stats" in status:
        print_header("ПЕЧАТЬ")
        print_stats = status["print_stats"]
        state = print_stats["state"]
        
        print_info(f"Состояние печати: {state}")
        
        if state != "standby":
            filename = print_stats.get("filename", "Неизвестно")
            print_info(f"Файл: {filename}")
            
            # Продолжительность печати
            if "print_duration" in print_stats:
                duration = print_stats["print_duration"]
                mins, secs = divmod(int(duration), 60)
                hours, mins = divmod(mins, 60)
                print_info(f"Длительность: {hours:02d}:{mins:02d}:{secs:02d}")
            
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
                        
                        mins, secs = divmod(int(eta), 60)
                        hours, mins = divmod(mins, 60)
                        print_info(f"Осталось: {hours:02d}:{mins:02d}:{secs:02d}")
                        
                        finish_time = datetime.now().timestamp() + eta
                        finish_time_str = datetime.fromtimestamp(finish_time).strftime('%H:%M:%S')
                        print_info(f"Ожидаемое время завершения: {finish_time_str}")
            
            # Скорость печати
            if "display_status" in status:
                display = status["display_status"]
                if "speed_factor" in display:
                    speed = display["speed_factor"] * 100
                    print_info(f"Скорость: {speed:.0f}%")

def menu_send_gcode(client):
    """Меню отправки G-code команд"""
    print_header("ОТПРАВКА G-CODE КОМАНД")
    
    common_commands = {
        "1": "G28 ; Home all axes",
        "2": "M104 S0 ; Turn off hotend",
        "3": "M140 S0 ; Turn off bed",
        "4": "M106 S0 ; Turn off fan",
        "5": "M84 ; Disable motors",
        "6": "G1 X10 Y10 F3000 ; Move to X10 Y10",
        "7": "G1 Z10 F600 ; Move Z up 10mm",
        "8": "M106 S255 ; Fan full speed",
        "9": "M105 ; Report temperatures",
        "10": "STATUS ; Report printer status (Klipper specific)"
    }
    
    while True:
        print("\n" + "-" * 50)
        print_info("Распространенные команды:")
        
        for key, cmd in common_commands.items():
            print(f"{key}: {cmd}")
        
        print("\n0: Ввести произвольную команду")
        print("r: Вернуться в главное меню")
        
        choice = input("\nВыберите опцию: ").strip()
        
        if choice.lower() == 'r':
            break
            
        if choice == '0':
            # Ручной ввод команды
            gcode = input("Введите G-code команду: ").strip()
            if gcode:
                result = client.send_gcode(gcode)
                if result and "result" in result and result["result"] == "ok":
                    print_success("Команда успешно отправлена")
                else:
                    print_error("Ошибка отправки команды")
        elif choice in common_commands:
            # Выбор из предопределенных команд
            cmd = common_commands[choice].split(';')[0].strip()
            result = client.send_gcode(cmd)
            if result and "result" in result and result["result"] == "ok":
                print_success(f"Команда '{cmd}' успешно отправлена")
            else:
                print_error(f"Ошибка отправки команды '{cmd}'")
        else:
            print_warning("Неверный выбор")

def menu_printer_control(client):
    """Меню управления принтером"""
    while True:
        clear_screen()
        print_header("УПРАВЛЕНИЕ ПРИНТЕРОМ")
        print("1: Показать статус принтера")
        print("2: Отправить G-code команду")
        print("3: Включить подогрев стола (50°C)")
        print("4: Выключить подогрев стола")
        print("5: Включить подогрев экструдера (200°C)")
        print("6: Выключить подогрев экструдера")
        print("7: Установить все оси в домашнее положение (Home)")
        print("8: Выключить моторы")
        print("9: Перезагрузить хост Klipper")
        print("10: Перезагрузить прошивку")
        print("11: АВАРИЙНАЯ ОСТАНОВКА (M112)")
        print("r: Вернуться в главное меню")
        
        choice = input("\nВыберите опцию: ").strip()
        
        if choice == 'r':
            break
        
        if choice == '1':
            display_printer_status(client)
            input("\nНажмите Enter для продолжения...")
        elif choice == '2':
            menu_send_gcode(client)
        elif choice == '3':
            result = client.send_gcode("M140 S50")
            if result and "result" in result and result["result"] == "ok":
                print_success("Подогрев стола включен (50°C)")
            input("\nНажмите Enter для продолжения...")
        elif choice == '4':
            result = client.send_gcode("M140 S0")
            if result and "result" in result and result["result"] == "ok":
                print_success("Подогрев стола выключен")
            input("\nНажмите Enter для продолжения...")
        elif choice == '5':
            result = client.send_gcode("M104 S200")
            if result and "result" in result and result["result"] == "ok":
                print_success("Подогрев экструдера включен (200°C)")
            input("\nНажмите Enter для продолжения...")
        elif choice == '6':
            result = client.send_gcode("M104 S0")
            if result and "result" in result and result["result"] == "ok":
                print_success("Подогрев экструдера выключен")
            input("\nНажмите Enter для продолжения...")
        elif choice == '7':
            result = client.send_gcode("G28")
            if result and "result" in result and result["result"] == "ok":
                print_success("Команда Home отправлена")
            input("\nНажмите Enter для продолжения...")
        elif choice == '8':
            result = client.send_gcode("M84")
            if result and "result" in result and result["result"] == "ok":
                print_success("Моторы выключены")
            input("\nНажмите Enter для продолжения...")
        elif choice == '9':
            confirm = input("Вы уверены, что хотите перезагрузить хост Klipper? (y/n): ").strip().lower()
            if confirm == 'y':
                result = client.restart_host()
                if result and result == "ok":
                    print_success("Команда перезагрузки хоста отправлена")
            input("\nНажмите Enter для продолжения...")
        elif choice == '10':
            confirm = input("Вы уверены, что хотите перезагрузить прошивку? (y/n): ").strip().lower()
            if confirm == 'y':
                result = client.restart_firmware()
                if result and result == "ok":
                    print_success("Команда перезагрузки прошивки отправлена")
            input("\nНажмите Enter для продолжения...")
        elif choice == '11':
            confirm = input("ВНИМАНИЕ: Вы уверены, что хотите выполнить АВАРИЙНУЮ ОСТАНОВКУ? (y/n): ").strip().lower()
            if confirm == 'y':
                result = client.emergency_stop()
                if result and "result" in result and result["result"] == "ok":
                    print_success("Команда аварийной остановки отправлена")
            input("\nНажмите Enter для продолжения...")
        else:
            print_warning("Неверный выбор")
            input("\nНажмите Enter для продолжения...")

def menu_file_manager(client):
    """Меню управления файлами"""
    current_path = "gcodes"
    while True:
        clear_screen()
        print_header(f"ФАЙЛОВЫЙ МЕНЕДЖЕР ({current_path})")
        print("1: Просмотреть файлы")
        print("2: Изменить текущую директорию")
        print("r: Вернуться в главное меню")
        
        choice = input("\nВыберите опцию: ").strip()
        
        if choice == 'r':
            break
        
        if choice == '1':
            result = client.get_file_list(current_path)
            if result and "result" in result:
                files = result["result"]
                print_header("СПИСОК ФАЙЛОВ")
                print("Директории:")
                for item in files.get("dirs", []):
                    print(f" - {item['dirname']}")
                print("\nФайлы:")
                for item in files.get("files", []):
                    size_mb = item.get("size", 0) / (1024 * 1024)
                    print(f" - {item['filename']} ({size_mb:.2f} MB)")
            else:
                print_error("Не удалось получить список файлов")
            input("\nНажмите Enter для продолжения...")
        elif choice == '2':
            new_path = input("Введите путь (например, 'gcodes' или 'gcodes/subfolder'): ").strip()
            if new_path:
                current_path = new_path
        else:
            print_warning("Неверный выбор")
            input("\nНажмите Enter для продолжения...")

def main_menu(client):
    """Главное меню приложения"""
    while True:
        clear_screen()
        print_header("MOONRAKER API TOOL")
        print("1: Управление принтером")
        print("2: Файловый менеджер")
        print("3: Проверить состояние сервера")
        print("q: Выход")
        
        choice = input("\nВыберите опцию: ").strip().lower()
        
        if choice == 'q':
            break
        
        if choice == '1':
            if check_klippy_ready(client):
                menu_printer_control(client)
            else:
                print_error("Klippy не готов к приему команд")
                input("\nНажмите Enter для продолжения...")
        elif choice == '2':
            menu_file_manager(client)
        elif choice == '3':
            server_info = client.get_server_info()
            if server_info and "result" in server_info:
                print_header("ИНФОРМАЦИЯ О СЕРВЕРЕ")
                info = server_info["result"]
                print_info(f"Klippy состояние: {info.get('klippy_state', 'Неизвестно')}")
                print_info(f"Klippy сообщение: {info.get('klippy_message', '')}")
                print_info(f"Компоненты:")
                for component in info.get("components", []):
                    print(f" - {component}")
            else:
                print_error("Не удалось получить информацию о сервере")
            input("\nНажмите Enter для продолжения...")
        else:
            print_warning("Неверный выбор")

def main():
    parser = argparse.ArgumentParser(description="Moonraker API Tool - интерактивный интерфейс для работы с API Moonraker")
    parser.add_argument("--host", default="192.168.10.14", help="Хост Moonraker (по умолчанию: 192.168.10.14)")
    parser.add_argument("--port", type=int, default=7125, help="Порт Moonraker (по умолчанию: 7125)")
    
    args = parser.parse_args()
    
    print_info("=========================================")
    print_info("         MOONRAKER API TOOL              ")
    print_info("=========================================")
    print_info(f"Хост: {args.host}")
    print_info(f"Порт: {args.port}")
    print_info("Подключение к серверу...")
    
    # Создаем клиент Moonraker
    client = MoonrakerClient(args.host, args.port)
    
    # Проверяем подключение
    server_info = client.get_server_info()
    if not server_info:
        print_error("Не удалось подключиться к серверу Moonraker")
        sys.exit(1)
    
    print_success("Соединение с сервером установлено")
    time.sleep(1)
    
    # Запускаем главное меню
    try:
        main_menu(client)
    except KeyboardInterrupt:
        print_info("\nПрограмма завершена пользователем")
    except Exception as e:
        print_error(f"Неожиданная ошибка: {e}")
    
    print_info("Программа завершена")

if __name__ == "__main__":
    main() 