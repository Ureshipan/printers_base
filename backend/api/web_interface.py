from flask import Flask, render_template, jsonify, request
import requests
import json
from datetime import datetime
import threading
import time
import os
import sys
from discovery.pi_discover import scan_no_cli

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

app = Flask(__name__, 
            template_folder='../../frontend/templates',
            static_folder='../../frontend/static')

# Конфигурация
aviable_printers = scan_no_cli()
if len(aviable_printers) > 0:
    PRINTER_HOST = aviable_printers[0]
else:
    PRINTER_HOST = "172.22.112.68"
PRINTER_PORT = "7125"
BASE_URL = f"http://{PRINTER_HOST}:{PRINTER_PORT}"

# Глобальные переменные для хранения состояния
printer_state = {
    "status": "Неизвестно",
    "temperature": {"extruder": 0, "bed": 0},
    "target_temperature": {"extruder": 0, "bed": 0},
    "position": {"x": 0, "y": 0, "z": 0},
    "last_update": None
}

def get_printer_info():
    """Получает информацию о принтере через Moonraker API"""
    try:
        response = requests.get(f"{BASE_URL}/printer/info", timeout=5)
        if response.status_code == 200:
            return response.json()["result"]
    except Exception as e:
        print(f"Ошибка при получении информации о принтере: {e}")
    return None

def get_server_info():
    """Получает информацию о сервере через Moonraker API"""
    try:
        response = requests.get(f"{BASE_URL}/server/info", timeout=5)
        if response.status_code == 200:
            return response.json()["result"]
    except Exception as e:
        print(f"Ошибка при получении информации о сервере: {e}")
    return None

def update_printer_state():
    """Фоновая задача для обновления состояния принтера"""
    while True:
        try:
            # Получаем информацию о состоянии принтера
            response = requests.get(f"{BASE_URL}/printer/objects/query?print_stats&extruder&heater_bed&toolhead", timeout=5)
            if response.status_code == 200:
                data = response.json()["result"]["status"]
                
                printer_state["status"] = data["print_stats"]["state"]
                printer_state["temperature"]["extruder"] = data["extruder"]["temperature"]
                printer_state["temperature"]["bed"] = data["heater_bed"]["temperature"]
                printer_state["target_temperature"]["extruder"] = data["extruder"]["target"]
                printer_state["target_temperature"]["bed"] = data["heater_bed"]["target"]
                printer_state["position"] = {
                    "x": data["toolhead"]["position"][0],
                    "y": data["toolhead"]["position"][1],
                    "z": data["toolhead"]["position"][2]
                }
                printer_state["last_update"] = datetime.now().strftime("%H:%M:%S")
        except Exception as e:
            print(f"Ошибка при обновлении состояния: {e}")
        
        time.sleep(1)

@app.route('/')
def index():
    return render_template('dashboard.html')

@app.route('/printer-control')
def printer_control():
    return render_template('printer-control.html')

@app.route('/api/printers')
def get_printers():
    """API endpoint to get list of printers (for now just one)"""
    try:
        printer_info = get_printer_info()
        server_info = get_server_info()
        
        if printer_info and server_info:
            printer = {
                "id": 1,
                "name": printer_info.get("hostname", "Принтер"),
                "model": printer_info.get("model", "Неизвестная модель"),
                "status": "work" if server_info.get("klippy_state") == "ready" else "error",
                "percent": 0,  # Will be updated with real data
                "lastServed": datetime.now().strftime("%d.%m.%Y"),
                "material": "PLA"  # Default material
            }
            
            # Try to get print progress if printing
            try:
                response = requests.get(f"{BASE_URL}/printer/objects/query?virtual_sdcard&print_stats", timeout=5)
                if response.status_code == 200:
                    data = response.json()["result"]["status"]
                    if "virtual_sdcard" in data and data["virtual_sdcard"]["progress"] > 0:
                        printer["percent"] = int(data["virtual_sdcard"]["progress"] * 100)
                        printer["status"] = "work"
            except:
                pass
                
            return jsonify([printer])
    except Exception as e:
        print(f"Ошибка при получении списка принтеров: {e}")
    
    # Return default printer if API fails
    return jsonify([{
        "id": 1,
        "name": "Принтер 1",
        "model": "ENDER-3 PRO",
        "status": "work",
        "percent": 67,
        "lastServed": datetime.now().strftime("%d.%m.%Y"),
        "material": "PLA"
    }])

@app.route('/api/state')
def get_state():
    return jsonify(printer_state)

@app.route('/api/command', methods=['POST'])
def send_command():
    command = request.json.get('command')
    try:
        response = requests.post(f"{BASE_URL}/printer/gcode/script", json={"script": command})
        return jsonify({"success": True, "message": "Команда отправлена"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/api/home', methods=['POST'])
def home_axis():
    axis = request.json.get('axis', 'all')
    try:
        command = f"G28 {axis.upper()}" if axis != 'all' else "G28"
        response = requests.post(f"{BASE_URL}/printer/gcode/script", json={"script": command})
        return jsonify({"success": True, "message": "Команда отправлена"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/api/temperature', methods=['POST'])
def set_temperature():
    data = request.json
    target = data.get('target')
    temperature = data.get('temperature')
    
    try:
        command = ""
        if target == 'extruder':
            command = f"M104 S{temperature}"
        elif target == 'bed':
            command = f"M140 S{temperature}"
        else:
            return jsonify({"success": False, "message": "Неверный параметр target"})
            
        response = requests.post(f"{BASE_URL}/printer/gcode/script", json={"script": command})
        return jsonify({"success": True, "message": "Температура установлена"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

if __name__ == '__main__':
    # Запускаем фоновую задачу обновления состояния
    update_thread = threading.Thread(target=update_printer_state, daemon=True)
    update_thread.start()
    
    app.run(host='0.0.0.0', port=5000, debug=True)