#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import json
import time
import argparse
import sys

# Цвета для вывода
GREEN = "\033[92m"
RED = "\033[91m"
BLUE = "\033[94m"
YELLOW = "\033[93m"
RESET = "\033[0m"

def print_success(message):
    print(f"{GREEN}[УСПЕХ]{RESET} {message}")

def print_error(message):
    print(f"{RED}[ОШИБКА]{RESET} {message}")

def print_info(message):
    print(f"{BLUE}[ИНФО]{RESET} {message}")

def print_warning(message):
    print(f"{YELLOW}[ВНИМАНИЕ]{RESET} {message}")

def print_json(data):
    """Печатает JSON-объект в отформатированном виде"""
    print(json.dumps(data, ensure_ascii=False, indent=2))

def send_gcode(host, port, gcode, method="http"):
    """Отправляет G-code команду на принтер"""
    
    base_url = f"http://{host}:{port}"
    
    print_info(f"Отправка G-code через {method.upper()}: {gcode}")
    
    try:
        if method == "http":
            # Отправка через HTTP API
            url = f"{base_url}/printer/gcode/script"
            response = requests.post(url, json={"script": gcode}, timeout=10)
            response.raise_for_status()
            result = response.json()
            
            if "result" in result and result["result"] == "ok":
                print_success("G-code команда успешно отправлена")
                return True
            else:
                print_error(f"Ошибка отправки G-code: {result}")
                return False
            
        elif method == "jsonrpc":
            # Отправка через JSON-RPC over HTTP
            url = f"{base_url}/printer/gcode/script"
            headers = {"Content-Type": "application/json"}
            payload = {
                "jsonrpc": "2.0",
                "method": "printer.gcode.script",
                "params": {"script": gcode},
                "id": int(time.time() * 1000)
            }
            
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            response.raise_for_status()
            result = response.json()
            
            if "result" in result and result["result"] == "ok":
                print_success("G-code команда успешно отправлена (JSON-RPC)")
                return True
            elif "error" in result:
                print_error(f"Ошибка отправки G-code: {result['error']}")
                return False
            else:
                print_error(f"Неожиданный ответ: {result}")
                return False
                
        else:
            print_error(f"Неподдерживаемый метод: {method}")
            return False
            
    except requests.exceptions.RequestException as e:
        print_error(f"Ошибка HTTP-запроса: {e}")
        return False
    except Exception as e:
        print_error(f"Неожиданная ошибка: {e}")
        return False

def check_klippy_ready(host, port):
    """Проверяет, готов ли Klippy к приему команд"""
    try:
        # Получаем информацию о сервере
        url = f"http://{host}:{port}/server/info"
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        result = response.json()
        
        if "result" in result and "klippy_state" in result["result"]:
            klippy_state = result["result"]["klippy_state"]
            
            if klippy_state == "ready":
                print_info("Klippy готов к приему команд")
                return True
            else:
                print_warning(f"Klippy не готов: {klippy_state}")
                if "klippy_message" in result["result"]:
                    print_warning(f"Сообщение: {result['result']['klippy_message']}")
                return False
        else:
            print_error("Неожиданный ответ от сервера")
            return False
            
    except requests.exceptions.RequestException as e:
        print_error(f"Ошибка HTTP-запроса: {e}")
        return False

def get_common_gcode_commands():
    """Возвращает список распространенных G-code команд"""
    return {
        "1": "G28 ; Home all axes",
        "2": "M104 S0 ; Turn off hotend",
        "3": "M140 S0 ; Turn off bed",
        "4": "M106 S0 ; Turn off fan",
        "5": "M84 ; Disable motors",
        "6": "G1 X10 Y10 F3000 ; Move to X10 Y10",
        "7": "G1 Z10 F600 ; Move Z up 10mm",
        "8": "M106 S255 ; Fan full speed",
        "9": "M106 S128 ; Fan half speed",
        "10": "G29 ; Auto bed leveling (if available)",
        "11": "M105 ; Report temperatures",
        "12": "G90 ; Set absolute positioning",
        "13": "G91 ; Set relative positioning",
        "14": "STATUS ; Report printer status (Klipper specific)"
    }

def interactive_mode(host, port):
    """Интерактивный режим для отправки G-code команд"""
    print_info("\n=== Интерактивный режим ===")
    print_info("Введите G-code команду или выберите из списка")
    print_info("Для выхода введите 'q' или 'exit'")
    
    common_commands = get_common_gcode_commands()
    
    while True:
        print("\n" + "=" * 50)
        print_info("Распространенные команды:")
        
        for key, cmd in common_commands.items():
            print(f"{key}: {cmd}")
        
        print("\n0: Ввести произвольную команду")
        print("q: Выход")
        
        choice = input("\nВыберите опцию: ").strip()
        
        if choice.lower() in ['q', 'exit', 'quit']:
            break
            
        if choice == '0':
            # Ручной ввод команды
            gcode = input("Введите G-code команду: ").strip()
            if gcode:
                send_gcode(host, port, gcode)
        elif choice in common_commands:
            # Выбор из предопределенных команд
            cmd = common_commands[choice].split(';')[0].strip()
            send_gcode(host, port, cmd)
        else:
            print_warning("Неверный выбор")

def main():
    parser = argparse.ArgumentParser(description="Отправка G-code команд на принтер через Moonraker API")
    parser.add_argument("--host", default="192.168.10.14", help="Хост Moonraker (по умолчанию: 192.168.10.14)")
    parser.add_argument("--port", type=int, default=7125, help="Порт Moonraker (по умолчанию: 7125)")
    parser.add_argument("--gcode", help="G-code команда для отправки (если не указана, запускается интерактивный режим)")
    parser.add_argument("--method", choices=["http", "jsonrpc"], default="http", help="Метод API (по умолчанию: http)")
    
    args = parser.parse_args()
    
    print_info("=========================================")
    print_info("  ОТПРАВКА G-CODE КОМАНД ЧЕРЕЗ MOONRAKER  ")
    print_info("=========================================")
    print_info(f"Хост: {args.host}")
    print_info(f"Порт: {args.port}")
    print_info(f"Метод API: {args.method}")
    
    # Проверяем готовность Klippy
    if not check_klippy_ready(args.host, args.port):
        print_error("Klippy не готов. Завершение работы.")
        sys.exit(1)
    
    if args.gcode:
        # Однократная отправка команды
        send_gcode(args.host, args.port, args.gcode, args.method)
    else:
        # Интерактивный режим
        interactive_mode(args.host, args.port)
    
    print_info("Завершение работы.")

if __name__ == "__main__":
    main() 