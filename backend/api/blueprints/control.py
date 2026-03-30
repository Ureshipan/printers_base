"""Blueprint: команды управления принтером и health endpoint."""
from flask import Blueprint, jsonify, request

from backend.api.state import (
    db,
    printer_states,
    health_registry,
)
from backend.api.helpers import get_printer_or_default
from backend.services.moonraker_client import moonraker_post

control_bp = Blueprint('control', __name__)


@control_bp.route('/api/command', methods=['POST'])
def api_send_command():
    data = request.get_json(force=True, silent=True) or {}
    command = data.get('command')
    printer_id = data.get('printer_id')
    printer = get_printer_or_default(printer_id)
    if not printer:
        return jsonify({"success": False, "message": "Нет доступных принтеров"}), 404
    try:
        # Увеличенный таймаут для G-code команд (G28 может занимать 10-15 сек)
        response = moonraker_post(printer, "printer/gcode/script", {"script": command}, timeout=30)
        if response is None:
            raise RuntimeError("Moonraker не ответил")
        return jsonify({"success": True, "message": "Команда отправлена"})
    except Exception as exc:  # pylint: disable=broad-except
        return jsonify({"success": False, "message": str(exc)})


@control_bp.route('/api/home', methods=['POST'])
def api_home_axis():
    data = request.get_json(force=True, silent=True) or {}
    axis = data.get('axis', 'all')
    printer_id = data.get('printer_id')
    printer = get_printer_or_default(printer_id)
    if not printer:
        return jsonify({"success": False, "message": "Нет доступных принтеров"}), 404
    command = f"G28 {axis.upper()}" if axis != 'all' else "G28"
    try:
        # Увеличенный таймаут для home команд (до 30 сек)
        response = moonraker_post(printer, "printer/gcode/script", {"script": command}, timeout=30)
        if response is None:
            raise RuntimeError("Moonraker не ответил")
        return jsonify({"success": True, "message": "Команда отправлена"})
    except Exception as exc:  # pylint: disable=broad-except
        return jsonify({"success": False, "message": str(exc)})


@control_bp.route('/api/temperature', methods=['POST'])
def api_set_temperature():
    data = request.get_json(force=True, silent=True) or {}
    target = data.get('target')
    temperature = data.get('temperature')
    printer_id = data.get('printer_id')
    printer = get_printer_or_default(printer_id)
    if not printer:
        return jsonify({"success": False, "message": "Нет доступных принтеров"}), 404

    try:
        if target == 'extruder':
            command = f"M104 S{temperature}"
        elif target == 'bed':
            command = f"M140 S{temperature}"
        else:
            return jsonify({"success": False, "message": "Неверный параметр target"}), 400

        response = moonraker_post(printer, "printer/gcode/script", {"script": command})
        if response is None:
            raise RuntimeError("Moonraker не ответил")
        return jsonify({"success": True, "message": "Температура установлена"})
    except Exception as exc:  # pylint: disable=broad-except
        return jsonify({"success": False, "message": str(exc)})


@control_bp.route('/api/health')
def api_health():
    """Health check + статусы circuit breaker."""
    states = health_registry.get_all_states()
    health_info = {}
    for pid, hs in states.items():
        health_info[pid] = {
            "state": hs.state,
            "consecutive_failures": hs.consecutive_failures,
            "circuit_open": hs.circuit_open,
        }
    return jsonify({
        "status": "ok",
        "printers_total": len(printer_states),
        "health": health_info,
    })
