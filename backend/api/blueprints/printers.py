"""Blueprint: API принтеров (CRUD, виртуальные принтеры, состояние)."""
from datetime import datetime, timezone
from typing import Dict

from flask import Blueprint, jsonify, request

from backend.api.state import (
    db,
    printer_states,
    printer_state_lock,
    DEFAULT_PRINTER_PORT,
    ALLOWED_VIRTUAL_STATUSES,
    STATE_MAP,
)
from backend.services.moonraker_client import (
    build_default_state,
    probe_moonraker_host,
    upsert_printers_for_host,
)

printers_bp = Blueprint('printers', __name__)


@printers_bp.route('/api/printers', methods=['GET', 'POST'])
def api_printers():
    if request.method == 'GET':
        printers = db.get_printers(include_inactive=False)
        result = []
        with printer_state_lock:
            for printer in printers:
                state = printer_states.get(printer.id, build_default_state())
                raw_status = state["status"]
                mapped_status = STATE_MAP.get(raw_status, raw_status)

                # Логика подтверждения уборки детали (проверяем БД)
                if mapped_status == "awaiting_removal":
                    if getattr(printer, 'removal_confirmed', False):
                        # Уборка подтверждена - показываем idle
                        mapped_status = "idle"
                else:
                    # Статус изменился - сбрасываем подтверждение для следующей печати
                    if getattr(printer, 'removal_confirmed', False):
                        db.update_printer(printer.id, removal_confirmed=False)

                # Проверяем статус обслуживания
                maintenance_status = db.get_printer_maintenance_status(printer.id)
                needs_maintenance = maintenance_status.get('needs_maintenance', False)
                result.append({
                    "id": printer.id,
                    "name": printer.name or f"Принтер #{printer.id}",
                    "model": state.get("filename") or "Неизвестная модель",
                    "status": mapped_status,
                    "percent": state.get("progress", 0),
                    "lastServed": printer.last_service or (
                        printer.last_seen.strftime("%d.%m.%Y") if printer.last_seen else datetime.now().strftime("%d.%m.%Y")
                    ),
                    "material": "PLA",  # Placeholder until material tracking is implemented
                    "is_virtual": getattr(printer, "is_virtual", False),
                    "needs_maintenance": needs_maintenance,
                    "print_hours": getattr(printer, "print_hours", 0.0) or 0.0,
                    "nozzle_diameter": getattr(printer, "nozzle_diameter", 0.4) or 0.4,
                })
        return jsonify(result)

    data = request.get_json(force=True, silent=True) or {}
    host = (data.get('host') or '').strip()
    port = data.get('port', DEFAULT_PRINTER_PORT)
    if not host:
        return jsonify({"success": False, "message": "IP адрес обязателен"}), 400
    try:
        port = int(port)
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": "Порт должен быть числом"}), 400

    if not probe_moonraker_host(host, port):
        return jsonify({"success": False, "message": f"Не удалось подключиться к Moonraker на {host}:{port}"}), 400

    printers_added = upsert_printers_for_host(host, port)
    if not printers_added:
        return jsonify({"success": False, "message": "На указанном хосте не найдено ни одного принтера"}), 404

    return jsonify({
        "success": True,
        "printers": [
            {
                "id": printer.id,
                "name": printer.name,
                "host": printer.moonraker_host,
                "port": printer.moonraker_port,
                "moonraker_printer": printer.moonraker_printer,
                "is_virtual": getattr(printer, "is_virtual", False),
            }
            for printer in printers_added
        ],
    })


@printers_bp.route('/api/printers/virtual', methods=['POST'])
def api_add_virtual_printer():
    data = request.get_json(force=True, silent=True) or {}
    name = (data.get('name') or '').strip()
    status = (data.get('status') or 'idle').strip().lower()
    if not name:
        return jsonify({"success": False, "message": "Имя принтера обязательно"}), 400
    if status not in ALLOWED_VIRTUAL_STATUSES:
        return jsonify({"success": False, "message": "Недопустимый статус"}), 400

    printer = db.add_virtual_printer(name=name, status=status)
    # Записываем стартовое состояние, чтобы сразу отобразилось в UI
    with printer_state_lock:
        printer_states[printer.id] = {
            **build_default_state(),
            "status": status,
            "last_update": datetime.now(timezone.utc).isoformat(),
        }
    return jsonify({
        "success": True,
        "printer": {
            "id": printer.id,
            "name": printer.name,
            "status": status,
            "is_virtual": True,
        }
    })


@printers_bp.route('/api/printers/<int:printer_id>/confirm-removal', methods=['POST'])
def api_printer_confirm_removal(printer_id: int):
    """Подтверждение уборки детали со стола после завершения печати."""
    printer = db.get_printer_by_id(printer_id)
    if not printer:
        return jsonify({"success": False, "message": "Принтер не найден"}), 404

    # Сохраняем подтверждение в БД
    db.update_printer(printer_id, removal_confirmed=True)

    return jsonify({
        "success": True,
        "message": f"Уборка детали подтверждена для принтера {printer.name}"
    })


@printers_bp.route('/api/printers/<int:printer_id>', methods=['GET', 'PUT', 'DELETE'])
def api_printer_detail(printer_id: int):
    printer = db.get_printer_by_id(printer_id)
    if not printer:
        return jsonify({"success": False, "message": "Принтер не найден"}), 404

    if request.method == 'GET':
        return jsonify({
            "success": True,
            "printer": {
                "id": printer.id,
                "name": printer.name,
                "host": printer.moonraker_host,
                "port": printer.moonraker_port or DEFAULT_PRINTER_PORT,
                "moonraker_printer": printer.moonraker_printer,
                "is_virtual": getattr(printer, "is_virtual", False),
                "status": getattr(printer, "virtual_status", None),
                "nozzle_diameter": getattr(printer, "nozzle_diameter", 0.4) or 0.4,
            }
        })

    if request.method == 'PUT':
        data = request.get_json(force=True, silent=True) or {}
        updates = {}

        if 'name' in data:
            name = (data.get('name') or '').strip()
            if not name:
                return jsonify({"success": False, "message": "Название принтера обязательно"}), 400
            updates['name'] = name

        # Для виртуальных принтеров можно менять статус и ручные данные
        if getattr(printer, "is_virtual", False):
            if 'status' in data:
                status = (data.get('status') or '').strip().lower()
                if status and status in ALLOWED_VIRTUAL_STATUSES:
                    updates['virtual_status'] = status

            # Ручные данные для оффлайн-принтеров
            if 'manual_progress' in data:
                try:
                    progress = int(data.get('manual_progress', 0))
                    updates['manual_progress'] = max(0, min(100, progress))
                except (TypeError, ValueError):
                    pass

            if 'manual_filename' in data:
                filename = data.get('manual_filename')
                updates['manual_filename'] = (filename or '').strip() or None

            if 'manual_print_start' in data:
                start_str = data.get('manual_print_start')
                if start_str:
                    try:
                        from datetime import datetime as dt
                        updates['manual_print_start'] = dt.fromisoformat(start_str.replace('Z', '+00:00'))
                    except (ValueError, TypeError):
                        pass
                else:
                    updates['manual_print_start'] = None

            # Обновляем кэш состояния для виртуальных принтеров
            with printer_state_lock:
                if printer_id in printer_states:
                    if 'virtual_status' in updates:
                        printer_states[printer_id]['status'] = updates['virtual_status']
                    if 'manual_progress' in updates:
                        printer_states[printer_id]['progress'] = updates['manual_progress']
                    if 'manual_filename' in updates:
                        printer_states[printer_id]['filename'] = updates['manual_filename']

        # Для реальных принтеров можно менять host/port
        if not getattr(printer, "is_virtual", False):
            if 'host' in data:
                updates['moonraker_host'] = (data.get('host') or '').strip()
            if 'port' in data:
                try:
                    updates['moonraker_port'] = int(data.get('port'))
                except (TypeError, ValueError):
                    pass

        # Диаметр сопла можно менять для любого принтера
        if 'nozzle_diameter' in data:
            try:
                nozzle = float(data.get('nozzle_diameter'))
                if 0.1 <= nozzle <= 2.0:  # Разумный диапазон
                    updates['nozzle_diameter'] = nozzle
            except (TypeError, ValueError):
                pass

        if not updates:
            return jsonify({"success": False, "message": "Нет данных для обновления"}), 400

        updated_printer = db.update_printer(printer_id, **updates)
        if not updated_printer:
            return jsonify({"success": False, "message": "Не удалось обновить принтер"}), 500

        return jsonify({
            "success": True,
            "printer": {
                "id": updated_printer.id,
                "name": updated_printer.name,
                "host": updated_printer.moonraker_host,
                "port": updated_printer.moonraker_port or DEFAULT_PRINTER_PORT,
                "is_virtual": getattr(updated_printer, "is_virtual", False),
            }
        })

    # DELETE
    deleted = db.delete_printer(printer_id)
    if deleted:
        with printer_state_lock:
            printer_states.pop(printer_id, None)
        return jsonify({"success": True})
    return jsonify({"success": False, "message": "Не удалось удалить принтер"}), 500


@printers_bp.route('/api/state')
def api_get_state():
    printer_id = request.args.get('printer_id', type=int)
    with printer_state_lock:
        if printer_id:
            state = printer_states.get(printer_id)
        else:
            state = next(iter(printer_states.values()), None)
    if not state:
        state = build_default_state()
    return jsonify(state)
