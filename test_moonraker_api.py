#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import json
import time
import websocket
import threading
import sys

# Конфигурация
MOONRAKER_URL = "http://192.168.10.14:7125"
WEBSOCKET_URL = "ws://192.168.10.14:7125/websocket"

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
    print(f"{YELLOW}[ПРЕДУПРЕЖДЕНИЕ]{RESET} {message}")

def print_json(data):
    """Печатает JSON-объект в отформатированном виде"""
    print(json.dumps(data, ensure_ascii=False, indent=2))

def http_request(endpoint, method="GET", params=None, data=None):
    """Выполняет HTTP-запрос к API Moonraker"""
    url = f"{MOONRAKER_URL}/{endpoint}"
    try:
        if method == "GET":
            response = requests.get(url, params=params, timeout=10)
        elif method == "POST":
            response = requests.post(url, params=params, json=data, timeout=10)
        
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print_error(f"Ошибка HTTP-запроса: {e}")
        return None

def jsonrpc_request(method, params=None):
    """Формирует JSON-RPC запрос"""
    request_id = int(time.time() * 1000)
    request = {
        "jsonrpc": "2.0",
        "method": method,
        "id": request_id
    }
    
    if params is not None:
        request["params"] = params
        
    return request

def test_server_info():
    """Проверяет информацию о сервере"""
    print_info("Проверка информации о сервере...")
    
    # HTTP API
    result = http_request("server/info")
    if result and "result" in result:
        print_success("HTTP API: Информация о сервере получена")
        klippy_state = result["result"]["klippy_state"]
        print_info(f"Состояние Klippy: {klippy_state}")
        
        if klippy_state != "ready":
            print_warning("Klippy не в состоянии готовности")
        
        return True
    else:
        print_error("Не удалось получить информацию о сервере")
        return False

def test_printer_info():
    """Проверяет информацию о принтере"""
    print_info("Проверка информации о принтере...")
    
    # HTTP API
    result = http_request("printer/info")
    if result and "result" in result:
        print_success("HTTP API: Информация о принтере получена")
        print_json(result["result"])
        return True
    else:
        print_error("Не удалось получить информацию о принтере")
        return False

def test_printer_objects():
    """Проверяет объекты принтера"""
    print_info("Проверка объектов принтера...")
    
    # Формируем запрос на получение объектов
    params = {
        "webhooks": None,
        "virtual_sdcard": None,
        "print_stats": None
    }
    
    # HTTP API
    result = http_request("printer/objects/query", params=params)
    if result and "result" in result and "status" in result["result"]:
        print_success("HTTP API: Объекты принтера получены")
        
        status = result["result"]["status"]
        
        # Проверяем наличие ожидаемых объектов
        if "webhooks" in status:
            print_info(f"Webhooks state: {status['webhooks']['state']}")
            
            if "print_stats" in status:
                print_info(f"Print state: {status['print_stats']['state']}")
                
                if status['print_stats']['state'] != "standby":
                    print_info(f"Текущий файл: {status['print_stats']['filename']}")
            
            if "virtual_sdcard" in status and status["virtual_sdcard"]["progress"] > 0:
                print_info(f"Прогресс печати: {status['virtual_sdcard']['progress'] * 100:.1f}%")
        
        print_json(status)
        return True
    else:
        print_error("Не удалось получить объекты принтера")
        return False

def test_websocket():
    """Тестирует WebSocket-соединение"""
    print_info("Проверка WebSocket-соединения...")
    
    ws_connected = threading.Event()
    ws_message_received = threading.Event()
    
    def on_message(ws, message):
        print_info(f"WebSocket сообщение получено: {message[:100]}...")
        ws_message_received.set()
    
    def on_error(ws, error):
        print_error(f"WebSocket ошибка: {error}")
    
    def on_close(ws, close_status_code, close_msg):
        print_info("WebSocket соединение закрыто")
    
    def on_open(ws):
        print_success("WebSocket соединение установлено")
        ws_connected.set()
        
        # Запрашиваем статус принтера через websocket
        request = jsonrpc_request("printer.objects.query", 
                                 {"objects": {"webhooks": None, "print_stats": None}})
        ws.send(json.dumps(request))
    
    # Создаем WebSocket-соединение
    ws = websocket.WebSocketApp(WEBSOCKET_URL,
                              on_open=on_open,
                              on_message=on_message,
                              on_error=on_error,
                              on_close=on_close)
    
    # Запускаем WebSocket в отдельном потоке
    wst = threading.Thread(target=ws.run_forever)
    wst.daemon = True
    wst.start()
    
    # Ждем установки соединения
    if not ws_connected.wait(timeout=5):
        print_error("Не удалось установить WebSocket-соединение")
        return False
    
    # Ждем получения сообщения
    if not ws_message_received.wait(timeout=5):
        print_error("Не получено сообщение через WebSocket")
        ws.close()
        return False
    
    # Закрываем соединение
    ws.close()
    return True

def main():
    print_info("Начало тестирования Moonraker API")
    print_info(f"URL: {MOONRAKER_URL}")
    
    tests = [
        ("Информация о сервере", test_server_info),
        ("Информация о принтере", test_printer_info),
        ("Объекты принтера", test_printer_objects),
        ("WebSocket", test_websocket)
    ]
    
    results = []
    
    for name, test_func in tests:
        print("\n" + "=" * 50)
        print_info(f"Тест: {name}")
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print_error(f"Неожиданная ошибка: {e}")
            results.append((name, False))
    
    # Выводим сводку результатов
    print("\n" + "=" * 50)
    print_info("Результаты тестирования:")
    
    all_passed = True
    for name, result in results:
        if result:
            print_success(f"{name}: Успешно")
        else:
            print_error(f"{name}: Ошибка")
            all_passed = False
    
    if all_passed:
        print_success("\nВсе тесты пройдены успешно!")
    else:
        print_error("\nНе все тесты пройдены успешно.")

if __name__ == "__main__":
    main() 