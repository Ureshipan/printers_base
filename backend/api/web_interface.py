from flask import Flask, render_template, jsonify, request
import requests
import json
from datetime import datetime
import threading
import time
import os
import sys

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

app = Flask(__name__, 
            template_folder='../../frontend/templates',
            static_folder='../../frontend/static')

# Конфигурация
PRINTER_HOST = "192.168.10.14"
PRINTER_PORT = "7125"
BASE_URL = f"http://{PRINTER_HOST}:{PRINTER_PORT}"

# Глобальные переменные для хранения состояния
printer_state = {
    "status": "Неизвестно",
    "temperature": {"extruder": 0, "bed": 0},
    "position": {"x": 0, "y": 0, "z": 0},
    "last_update": None
}

def update_printer_state():
    """Фоновая задача для обновления состояния принтера"""
    while True:
        try:
            # Получаем информацию о состоянии принтера
            response = requests.get(f"{BASE_URL}/printer/objects/query?print_stats&extruder&heater_bed&toolhead")
            if response.status_code == 200:
                data = response.json()["result"]["status"]
                
                printer_state["status"] = data["print_stats"]["state"]
                printer_state["temperature"]["extruder"] = data["extruder"]["temperature"]
                printer_state["temperature"]["bed"] = data["heater_bed"]["temperature"]
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
        command = f"M104 S{temperature}" if target == 'extruder' else f"M140 S{temperature}"
        response = requests.post(f"{BASE_URL}/printer/gcode/script", json={"script": command})
        return jsonify({"success": True, "message": "Температура установлена"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

if __name__ == '__main__':
    # Запускаем фоновую задачу обновления состояния
    update_thread = threading.Thread(target=update_printer_state, daemon=True)
    update_thread.start()
    
    app.run(host='0.0.0.0', port=5000, debug=True) 