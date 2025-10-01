#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import websocket
import json
import threading
import time
import argparse
import sys
from datetime import datetime

# Цвета для вывода
GREEN = "\033[92m"
RED = "\033[91m"
BLUE = "\033[94m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
MAGENTA = "\033[95m"
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

def print_event(message):
    print_colored(MAGENTA, "СОБЫТИЕ", message)

class MoonrakerWebsocket:
    def __init__(self, host, port=7125):
        self.ws_url = f"ws://{host}:{port}/websocket"
        self.ws = None
        self.connected = False
        self.request_id = 0
        
        # События для контроля подключения и инициализации
        self.connection_event = threading.Event()
        self.klippy_ready_event = threading.Event()
        
        # Флаг для остановки потоков
        self.running = True
        
        # Состояние принтера
        self.printer_state = {"klippy_state": "disconnected"}
        
        # Список объектов для подписки
        self.subscribe_objects = {
            "toolhead": None,
            "extruder": None,
            "heater_bed": None,
            "print_stats": None,
            "virtual_sdcard": None,
            "display_status": None,
            "gcode_move": None
        }
        
    def connect(self):
        """Устанавливает соединение с сервером"""
        print_info(f"Подключение к {self.ws_url}...")
        
        try:
            # Настройка обработчиков WebSocket
            websocket.enableTrace(False)
            self.ws = websocket.WebSocketApp(
                self.ws_url,
                on_open=self.on_open,
                on_message=self.on_message,
                on_error=self.on_error,
                on_close=self.on_close
            )
            
            # Запуск соединения в отдельном потоке
            self.wst = threading.Thread(target=self.ws.run_forever)
            self.wst.daemon = True
            self.wst.start()
            
            # Ожидаем установки соединения
            if not self.connection_event.wait(timeout=10):
                print_error("Таймаут подключения к WebSocket")
                return False
                
            return True
        except Exception as e:
            print_error(f"Ошибка подключения: {e}")
            return False
    
    def wait_for_klippy_ready(self, timeout=30):
        """Ожидает, пока Klippy не будет готов"""
        print_info(f"Ожидание готовности Klippy (таймаут: {timeout} сек)...")
        
        # Запрашиваем информацию о сервере
        self.get_server_info()
        
        # Ожидаем, пока Klippy не будет готов
        if not self.klippy_ready_event.wait(timeout=timeout):
            print_error("Таймаут ожидания готовности Klippy")
            return False
        
        return True
    
    def subscribe_objects_status(self):
        """Подписка на обновления объектов принтера"""
        if not self.connected or not self.klippy_ready_event.is_set():
            print_error("Невозможно подписаться: соединение не установлено или Klippy не готов")
            return False
        
        print_info("Подписка на обновления объектов принтера...")
        
        request = {
            "jsonrpc": "2.0",
            "method": "printer.objects.subscribe",
            "params": {
                "objects": self.subscribe_objects
            },
            "id": self.get_next_id()
        }
        
        self.ws.send(json.dumps(request))
        return True
    
    def get_next_id(self):
        """Возвращает уникальный ID для запроса"""
        self.request_id += 1
        return self.request_id
    
    def on_open(self, ws):
        """Обработчик открытия соединения"""
        print_success("WebSocket соединение установлено")
        self.connected = True
        self.connection_event.set()
    
    def on_message(self, ws, message):
        """Обработчик полученных сообщений"""
        try:
            data = json.loads(message)
            
            # Обрабатываем ответы на запросы
            if "id" in data:
                self.handle_response(data)
            # Обрабатываем уведомления
            elif "method" in data and data["method"] == "notify_status_update":
                self.handle_status_update(data["params"][0])
            # Обрабатываем события Klippy
            elif "method" in data and data["method"].startswith("notify_"):
                self.handle_notification(data)
        except json.JSONDecodeError:
            print_error(f"Ошибка декодирования JSON: {message}")
        except Exception as e:
            print_error(f"Ошибка обработки сообщения: {e}")
    
    def on_error(self, ws, error):
        """Обработчик ошибок соединения"""
        print_error(f"WebSocket ошибка: {error}")
    
    def on_close(self, ws, close_status_code, close_msg):
        """Обработчик закрытия соединения"""
        print_info(f"WebSocket соединение закрыто: {close_status_code} - {close_msg}")
        self.connected = False
    
    def handle_response(self, data):
        """Обрабатывает ответы на запросы"""
        if "error" in data:
            print_error(f"Ошибка запроса #{data['id']}: {data['error']['message']}")
            return
        
        # Обработка ответа на запрос информации о сервере
        if data.get("id") in [1, 2] and "result" in data:
            if "klippy_state" in data["result"]:
                klippy_state = data["result"]["klippy_state"]
                print_info(f"Состояние Klippy: {klippy_state}")
                
                self.printer_state["klippy_state"] = klippy_state
                
                if klippy_state == "ready":
                    self.klippy_ready_event.set()
                    
                    # Как только Klippy готов, подписываемся на обновления
                    self.subscribe_objects_status()
    
    def handle_status_update(self, status_data):
        """Обрабатывает обновления статуса объектов"""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        print_event(f"[{timestamp}] Получено обновление статуса:")
        
        # Проверяем основные компоненты
        if "print_stats" in status_data:
            state = status_data["print_stats"].get("state")
            if state:
                print_status(f"Состояние печати: {state}")
        
        if "extruder" in status_data:
            ext_data = status_data["extruder"]
            if "temperature" in ext_data:
                temp = ext_data["temperature"]
                target = ext_data.get("target", 0)
                print_status(f"Экструдер: {temp:.1f}°C / {target:.1f}°C")
        
        if "heater_bed" in status_data:
            bed_data = status_data["heater_bed"]
            if "temperature" in bed_data:
                temp = bed_data["temperature"]
                target = bed_data.get("target", 0)
                print_status(f"Стол: {temp:.1f}°C / {target:.1f}°C")
        
        if "virtual_sdcard" in status_data:
            vsd = status_data["virtual_sdcard"]
            if "progress" in vsd:
                progress = vsd["progress"] * 100
                print_status(f"Прогресс: {progress:.1f}%")
        
        if "toolhead" in status_data:
            th = status_data["toolhead"]
            if "position" in th:
                pos = th["position"]
                print_status(f"Позиция: X={pos[0]:.2f} Y={pos[1]:.2f} Z={pos[2]:.2f}")
        
        if "gcode_move" in status_data:
            gm = status_data["gcode_move"]
            if "speed_factor" in gm:
                speed = gm["speed_factor"] * 60 * 100
                print_status(f"Скорость: {speed:.0f}%")
    
    def handle_notification(self, data):
        """Обрабатывает уведомления от сервера"""
        method = data["method"]
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        
        if method == "notify_klippy_disconnected":
            print_event(f"[{timestamp}] KLIPPY ОТКЛЮЧЕН")
            self.printer_state["klippy_state"] = "disconnected"
            self.klippy_ready_event.clear()
        
        elif method == "notify_klippy_ready":
            print_event(f"[{timestamp}] KLIPPY ГОТОВ")
            self.printer_state["klippy_state"] = "ready"
            self.klippy_ready_event.set()
            
            # Подписываемся на обновления объектов
            self.subscribe_objects_status()
        
        elif method == "notify_gcode_response":
            message = data["params"][0]
            print_event(f"[{timestamp}] G-CODE: {message}")
        
        else:
            print_event(f"[{timestamp}] {method}")
    
    def get_server_info(self):
        """Запрашивает информацию о сервере"""
        if not self.connected:
            print_error("Невозможно запросить: WebSocket соединение не установлено")
            return
        
        print_info("Запрос информации о сервере...")
        
        request = {
            "jsonrpc": "2.0",
            "method": "server.info",
            "id": self.get_next_id()
        }
        
        self.ws.send(json.dumps(request))
    
    def close(self):
        """Закрывает соединение с сервером"""
        self.running = False
        if self.connected and self.ws:
            self.ws.close()

def main():
    parser = argparse.ArgumentParser(description="WebSocket слушатель для Moonraker API")
    parser.add_argument("--host", default="192.168.10.14", help="Хост Moonraker (по умолчанию: 192.168.10.14)")
    parser.add_argument("--port", type=int, default=7125, help="Порт Moonraker (по умолчанию: 7125)")
    parser.add_argument("--timeout", type=int, default=30, help="Таймаут ожидания готовности Klippy (по умолчанию: 30 сек)")
    
    args = parser.parse_args()
    
    print_info("=====================================")
    print_info("    MOONRAKER WEBSOCKET СЛУШАТЕЛЬ    ")
    print_info("=====================================")
    print_info(f"Хост: {args.host}")
    print_info(f"Порт: {args.port}")
    
    # Создаем WebSocket клиент
    client = MoonrakerWebsocket(args.host, args.port)
    
    try:
        # Подключаемся к серверу
        if not client.connect():
            sys.exit(1)
        
        # Ожидаем готовности Klippy
        if not client.wait_for_klippy_ready(args.timeout):
            print_warning("Klippy не готов, но продолжаем слушать...")
        
        print_info("\nСлушаем события принтера... (Нажмите Ctrl+C для выхода)")
        print_info("---------------------------------------")
        
        # Просто держим основной поток запущенным
        while client.running:
            time.sleep(1)
    
    except KeyboardInterrupt:
        print_info("\nПрерывание пользователем")
    except Exception as e:
        print_error(f"Неожиданная ошибка: {e}")
    finally:
        # Закрываем соединение
        client.close()
        print_info("Соединение закрыто")

if __name__ == "__main__":
    main() 