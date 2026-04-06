"""Blueprint: API обслуживания принтеров."""
import logging

from flask import Blueprint, jsonify, request

from backend.api.state import db
from backend.db.data_model import MaintenanceType, MaintenanceRecord

logger = logging.getLogger(__name__)

maintenance_bp = Blueprint('maintenance', __name__)


def _serialize_maintenance_type(mt: MaintenanceType) -> dict:
    """Сериализация типа обслуживания."""
    return {
        "id": mt.id,
        "code": mt.code,
        "name": mt.name,
        "interval_hours": mt.interval_hours,
        "description": mt.description,
    }


def _serialize_maintenance_record(record: MaintenanceRecord) -> dict:
    """Сериализация записи обслуживания."""
    return {
        "id": record.id,
        "printer_id": record.printer_id,
        "printer_name": record.printer.name if record.printer else None,
        "maintenance_type_id": record.maintenance_type_id,
        "type_code": record.maintenance_type.code if record.maintenance_type else None,
        "type_name": record.maintenance_type.name if record.maintenance_type else None,
        "performed_at": record.performed_at.isoformat() if record.performed_at else None,
        "print_hours_at": record.print_hours_at,
        "notes": record.notes,
        "is_forced": record.is_forced,
    }


@maintenance_bp.route('/api/maintenance/types', methods=['GET'])
def api_maintenance_types():
    """Получить список типов обслуживания."""
    types = db.get_maintenance_types()
    return jsonify([_serialize_maintenance_type(mt) for mt in types])


@maintenance_bp.route('/api/maintenance/types/<int:type_id>', methods=['PUT'])
def api_maintenance_type_update(type_id: int):
    """Обновить интервал типа обслуживания."""
    data = request.get_json(force=True, silent=True) or {}
    interval = data.get('interval_hours')
    if interval is not None:
        try:
            interval = float(interval)
            if interval <= 0:
                return jsonify({"success": False, "message": "Интервал должен быть положительным числом"}), 400
        except (TypeError, ValueError):
            return jsonify({"success": False, "message": "Интервал должен быть числом"}), 400

    updated = db.update_maintenance_type(type_id, interval_hours=interval)
    if not updated:
        return jsonify({"success": False, "message": "Тип обслуживания не найден"}), 404
    return jsonify({"success": True, "type": _serialize_maintenance_type(updated)})


@maintenance_bp.route('/api/maintenance/status', methods=['GET'])
def api_maintenance_status_all():
    """Получить статус обслуживания всех принтеров."""
    printers = db.get_printers(include_inactive=False)
    result = []
    for printer in printers:
        status = db.get_printer_maintenance_status(printer.id)
        if status:
            result.append(status)
    return jsonify(result)


@maintenance_bp.route('/api/maintenance/status/<int:printer_id>', methods=['GET'])
def api_maintenance_status(printer_id: int):
    """Получить статус обслуживания конкретного принтера."""
    status = db.get_printer_maintenance_status(printer_id)
    if not status:
        return jsonify({"success": False, "message": "Принтер не найден"}), 404
    return jsonify(status)


@maintenance_bp.route('/api/maintenance/upcoming', methods=['GET'])
def api_maintenance_upcoming():
    """Получить список ближайших обслуживаний отсортированный по оставшимся часам."""
    printers = db.get_printers(include_inactive=False)
    upcoming = []
    for printer in printers:
        status = db.get_printer_maintenance_status(printer.id)
        if not status:
            continue
        for maint in status.get('maintenance_status', []):
            upcoming.append({
                'printer_id': status['printer_id'],
                'printer_name': status['printer_name'],
                'print_hours': status['print_hours'],
                **maint,
            })
    # Сортируем по оставшимся часам (сначала те что ближе к обслуживанию)
    upcoming.sort(key=lambda x: x['hours_remaining'])
    return jsonify(upcoming)


@maintenance_bp.route('/api/maintenance/records', methods=['GET', 'POST'])
def api_maintenance_records():
    """Получить историю обслуживания или добавить запись."""
    if request.method == 'GET':
        printer_id = request.args.get('printer_id', type=int)
        limit = request.args.get('limit', 100, type=int)
        records = db.get_maintenance_records(printer_id=printer_id, limit=limit)
        return jsonify([_serialize_maintenance_record(r) for r in records])

    # POST - добавить запись обслуживания
    data = request.get_json(force=True, silent=True) or {}
    printer_id = data.get('printer_id')
    maintenance_type_id = data.get('maintenance_type_id')
    notes = (data.get('notes') or '').strip() or None
    is_forced = data.get('is_forced', False)

    if not printer_id or not maintenance_type_id:
        return jsonify({"success": False, "message": "printer_id и maintenance_type_id обязательны"}), 400

    try:
        record = db.add_maintenance_record(
            printer_id=int(printer_id),
            maintenance_type_id=int(maintenance_type_id),
            notes=notes,
            is_forced=is_forced,
        )
        return jsonify({"success": True, "record": _serialize_maintenance_record(record)})
    except ValueError as exc:
        return jsonify({"success": False, "message": str(exc)}), 404
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("Ошибка при добавлении записи обслуживания: %s", exc)
        return jsonify({"success": False, "message": "Внутренняя ошибка сервера"}), 500


@maintenance_bp.route('/api/maintenance/records/<int:record_id>', methods=['DELETE'])
def api_maintenance_record_delete(record_id: int):
    """Удалить запись обслуживания."""
    deleted = db.delete_maintenance_record(record_id)
    if not deleted:
        return jsonify({"success": False, "message": "Запись не найдена"}), 404
    return jsonify({"success": True})


@maintenance_bp.route('/api/maintenance/force/<int:printer_id>', methods=['POST'])
def api_maintenance_force(printer_id: int):
    """Принудительно потребовать обслуживание для принтера."""
    data = request.get_json(force=True, silent=True) or {}
    maintenance_type_id = data.get('maintenance_type_id')

    if not maintenance_type_id:
        return jsonify({"success": False, "message": "maintenance_type_id обязателен"}), 400

    printer = db.get_printer_by_id(printer_id)
    if not printer:
        return jsonify({"success": False, "message": "Принтер не найден"}), 404

    try:
        # Создаём запись с отрицательным print_hours_at чтобы сразу требовалось обслуживание
        record = db.add_maintenance_record(
            printer_id=printer_id,
            maintenance_type_id=int(maintenance_type_id),
            notes="Принудительно затребовано",
            is_forced=True,
        )
        # Устанавливаем print_hours_at в значение которое сделает обслуживание просроченным
        session = db.get_session()
        try:
            rec = session.query(MaintenanceRecord).get(record.id)
            if rec:
                # Ставим такое значение, чтобы часы с момента обслуживания превысили интервал
                rec.print_hours_at = (printer.print_hours or 0.0) - 1000
                session.commit()
        finally:
            session.close()

        return jsonify({"success": True, "message": "Обслуживание затребовано"})
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("Ошибка при принудительном требовании обслуживания: %s", exc)
        return jsonify({"success": False, "message": str(exc)}), 500
