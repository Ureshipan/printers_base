"""Blueprint: API управления печатью (start, pause, resume, cancel, offline)."""
import os
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

from backend.api.state import (
    db,
    printer_states,
    printer_state_lock,
    _get_printer_lock,
    UPLOAD_DIR,
)
from backend.api.helpers import serialize_task
from backend.services.moonraker_client import (
    build_default_state,
    upload_gcode_to_printer,
    start_print_on_printer,
    pause_print_on_printer,
    resume_print_on_printer,
    cancel_print_on_printer,
    get_printer_print_status,
)

print_control_bp = Blueprint('print_control', __name__)


@print_control_bp.route('/api/tasks/<int:task_id>/print/start', methods=['POST'])
def api_task_print_start(task_id: int):
    """Запуск печати задачи на принтере."""
    task = db.get_task(task_id)
    if not task:
        return jsonify({"success": False, "message": "Задача не найдена"}), 404

    # Проверки перед запуском
    if task.status not in ('pending', 'queued'):
        return jsonify({"success": False, "message": f"Нельзя запустить задачу в статусе '{task.status}'"}), 400

    if not task.model_gcode:
        return jsonify({"success": False, "message": "G-code файл не загружен"}), 400

    if not task.printer_id:
        return jsonify({"success": False, "message": "Принтер не назначен"}), 400

    printer = db.get_printer_by_id(task.printer_id)
    if not printer:
        return jsonify({"success": False, "message": "Принтер не найден"}), 404

    if printer.is_virtual:
        return jsonify({"success": False, "message": "Нельзя печатать на виртуальном принтере"}), 400

    # Per-printer lock: защита от одновременного запуска печати на одном принтере
    printer_lock = _get_printer_lock(printer.id)
    if not printer_lock.acquire(timeout=5):
        return jsonify({"success": False, "message": "Принтер занят другой операцией"}), 409

    try:
        # Перепроверяем состояние принтера после получения lock
        with printer_state_lock:
            state = printer_states.get(printer.id, build_default_state())

        if state.get("status") == "offline":
            return jsonify({"success": False, "message": "Принтер недоступен"}), 400

        if state.get("status") == "printing":
            return jsonify({"success": False, "message": "Принтер уже печатает"}), 409

        # Путь к локальному файлу
        local_file_path = os.path.join(UPLOAD_DIR, task.model_gcode)
        if not os.path.exists(local_file_path):
            return jsonify({"success": False, "message": "Локальный файл G-code не найден"}), 404

        # Имя файла для загрузки на принтер
        upload_filename = task.gcode_original_name or os.path.basename(task.model_gcode)

        # Загружаем файл на принтер
        success, result = upload_gcode_to_printer(printer, local_file_path, upload_filename)
        if not success:
            return jsonify({"success": False, "message": f"Ошибка загрузки файла: {result}"}), 500

        moonraker_filename = result  # Имя файла на принтере

        # Запускаем печать
        success, msg = start_print_on_printer(printer, moonraker_filename)
        if not success:
            return jsonify({"success": False, "message": f"Ошибка запуска печати: {msg}"}), 500

        # Обновляем задачу
        db.update_task(
            task_id,
            status='printing',
            moonraker_filename=moonraker_filename,
            progress=0,
            time_start=datetime.now(timezone.utc).isoformat(),
        )

        updated_task = db.get_task(task_id)
        return jsonify({"success": True, "task": serialize_task(updated_task)})
    finally:
        printer_lock.release()


@print_control_bp.route('/api/tasks/<int:task_id>/print/pause', methods=['POST'])
def api_task_print_pause(task_id: int):
    """Пауза печати задачи."""
    task = db.get_task(task_id)
    if not task:
        return jsonify({"success": False, "message": "Задача не найдена"}), 404

    if task.status != 'printing':
        return jsonify({"success": False, "message": "Задача не печатается"}), 400

    printer = db.get_printer_by_id(task.printer_id)
    if not printer:
        return jsonify({"success": False, "message": "Принтер не найден"}), 404

    success, msg = pause_print_on_printer(printer)
    if not success:
        return jsonify({"success": False, "message": f"Ошибка паузы: {msg}"}), 500

    db.update_task(task_id, status='paused')
    updated_task = db.get_task(task_id)
    return jsonify({"success": True, "task": serialize_task(updated_task)})


@print_control_bp.route('/api/tasks/<int:task_id>/print/resume', methods=['POST'])
def api_task_print_resume(task_id: int):
    """Возобновление печати задачи."""
    task = db.get_task(task_id)
    if not task:
        return jsonify({"success": False, "message": "Задача не найдена"}), 404

    if task.status != 'paused':
        return jsonify({"success": False, "message": "Задача не на паузе"}), 400

    printer = db.get_printer_by_id(task.printer_id)
    if not printer:
        return jsonify({"success": False, "message": "Принтер не найден"}), 404

    success, msg = resume_print_on_printer(printer)
    if not success:
        return jsonify({"success": False, "message": f"Ошибка возобновления: {msg}"}), 500

    db.update_task(task_id, status='printing')
    updated_task = db.get_task(task_id)
    return jsonify({"success": True, "task": serialize_task(updated_task)})


@print_control_bp.route('/api/tasks/<int:task_id>/print/cancel', methods=['POST'])
def api_task_print_cancel(task_id: int):
    """Отмена печати задачи."""
    task = db.get_task(task_id)
    if not task:
        return jsonify({"success": False, "message": "Задача не найдена"}), 404

    if task.status not in ('printing', 'paused'):
        return jsonify({"success": False, "message": "Задача не печатается и не на паузе"}), 400

    printer = db.get_printer_by_id(task.printer_id)
    if not printer:
        return jsonify({"success": False, "message": "Принтер не найден"}), 404

    # Отменяем печать на принтере
    success, msg = cancel_print_on_printer(printer)
    if not success:
        return jsonify({"success": False, "message": f"Ошибка отмены: {msg}"}), 500

    # Получаем фактические данные печати перед отменой
    print_status = get_printer_print_status(printer)
    actual_filament = None
    actual_time = None
    if print_status:
        print_stats = print_status.get('print_stats', {})
        actual_filament = print_stats.get('filament_used')  # в мм
        print_duration = print_stats.get('print_duration')  # в секундах
        if print_duration:
            actual_time = print_duration / 60  # конвертируем в минуты

    # Обновляем время работы принтера
    if actual_time and actual_time > 0:
        current_hours = printer.print_hours or 0
        db.update_printer(printer.id, print_hours=current_hours + (actual_time / 60))

    # Обновляем задачу (статус cancelled вызовет автосписание материала)
    db.update_task(
        task_id,
        status='cancelled',
        actual_filament_used=actual_filament,
        actual_print_time=actual_time,
        time_end=datetime.now(timezone.utc).isoformat(),
    )

    # Автосписание материала при отмене
    if task.coil_id and task.estimated_filament and task.estimated_filament > 0:
        coil = db.get_coil(task.coil_id)
        if coil:
            # Используем фактический расход если есть, иначе расчётный
            amount = task.estimated_filament
            if actual_filament and actual_filament > 0:
                # Конвертируем мм в граммы (примерно)
                # Для PLA: ~2.98г на метр при диаметре 1.75мм
                amount = min(amount, actual_filament / 1000 * 2.98)
            note = f"Автосписание при отмене: задача #{task_id}"
            db.deduct_material(task.coil_id, amount, task_id=task_id, notes=note)

    updated_task = db.get_task(task_id)
    return jsonify({"success": True, "task": serialize_task(updated_task)})


# ---------------------------------------------------------------------------
# Offline Task API (для оффлайн-принтеров)
# ---------------------------------------------------------------------------

# Допустимые переходы статусов для оффлайн-задач
OFFLINE_TASK_TRANSITIONS = {
    'pending': ['queued', 'printing', 'cancelled'],
    'queued': ['printing', 'cancelled'],
    'printing': ['paused', 'completed', 'cancelled'],
    'paused': ['printing', 'cancelled', 'completed'],
}


@print_control_bp.route('/api/tasks/<int:task_id>/offline/update', methods=['POST'])
def api_task_offline_update(task_id: int):
    """Ручное обновление статуса и прогресса задачи для оффлайн-принтеров."""
    task = db.get_task(task_id)
    if not task:
        return jsonify({"success": False, "message": "Задача не найдена"}), 404

    printer = db.get_printer_by_id(task.printer_id) if task.printer_id else None
    if not printer or not getattr(printer, 'is_virtual', False):
        return jsonify({"success": False, "message": "Задача не привязана к оффлайн-принтеру"}), 400

    data = request.get_json(force=True, silent=True) or {}
    updates = {}

    # Изменение статуса с валидацией переходов
    if 'status' in data:
        old_status = task.status or 'pending'
        new_status = data['status']
        allowed = OFFLINE_TASK_TRANSITIONS.get(old_status, [])
        if new_status not in allowed:
            return jsonify({
                "success": False,
                "message": f"Переход {old_status} → {new_status} недопустим. Допустимые: {', '.join(allowed)}"
            }), 400

        updates['status'] = new_status

        # При начале печати сохраняем время
        if new_status == 'printing' and old_status in ('pending', 'queued'):
            updates['time_start'] = datetime.now(timezone.utc).isoformat()
            # Обновляем данные принтера
            db.update_printer(printer.id, virtual_status='work', manual_print_start=datetime.now(timezone.utc))
            with printer_state_lock:
                if printer.id in printer_states:
                    printer_states[printer.id]['status'] = 'work'

        # При завершении/отмене
        if new_status in ('completed', 'cancelled'):
            updates['time_end'] = datetime.now(timezone.utc).isoformat()
            # Сбрасываем статус принтера
            db.update_printer(printer.id, virtual_status='idle', manual_progress=0, manual_filename=None, manual_print_start=None)
            with printer_state_lock:
                if printer.id in printer_states:
                    printer_states[printer.id]['status'] = 'idle'
                    printer_states[printer.id]['progress'] = 0
                    printer_states[printer.id]['filename'] = None

        # При паузе
        if new_status == 'paused':
            db.update_printer(printer.id, virtual_status='paused')
            with printer_state_lock:
                if printer.id in printer_states:
                    printer_states[printer.id]['status'] = 'paused'

    # Обновление прогресса
    if 'progress' in data:
        try:
            progress = int(data['progress'])
            updates['progress'] = max(0, min(100, progress))
            # Синхронизируем прогресс с принтером
            db.update_printer(printer.id, manual_progress=updates['progress'])
            with printer_state_lock:
                if printer.id in printer_states:
                    printer_states[printer.id]['progress'] = updates['progress']
        except (TypeError, ValueError):
            pass

    if not updates:
        return jsonify({"success": False, "message": "Нет данных для обновления"}), 400

    db.update_task(task_id, **updates)
    updated_task = db.get_task(task_id)
    return jsonify({"success": True, "task": serialize_task(updated_task)})


@print_control_bp.route('/api/tasks/<int:task_id>/offline/deduct-material', methods=['POST'])
def api_task_offline_deduct(task_id: int):
    """Ручное списание материала для оффлайн-задачи."""
    task = db.get_task(task_id)
    if not task:
        return jsonify({"success": False, "message": "Задача не найдена"}), 404

    if not task.coil_id:
        return jsonify({"success": False, "message": "Катушка не назначена для задачи"}), 400

    data = request.get_json(force=True, silent=True) or {}
    amount = data.get('amount')

    # Если количество не указано, используем estimated_filament
    if amount is None:
        amount = task.estimated_filament

    if not amount or amount <= 0:
        return jsonify({"success": False, "message": "Укажите количество материала для списания"}), 400

    try:
        amount = float(amount)
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": "Некорректное количество материала"}), 400

    coil = db.get_coil(task.coil_id)
    if not coil:
        return jsonify({"success": False, "message": "Катушка не найдена"}), 404

    # Проверка достаточности материала
    if coil.remains is not None and coil.remains < amount:
        return jsonify({
            "success": False,
            "message": f"Недостаточно материала. Доступно: {coil.remains:.1f}г, требуется: {amount:.1f}г",
            "warning_type": "insufficient_material"
        }), 400

    notes = data.get('notes') or f"Ручное списание: задача #{task_id}"
    updated_coil = db.deduct_material(task.coil_id, amount, task_id=task_id, notes=notes)

    return jsonify({
        "success": True,
        "deducted_amount": amount,
        "coil": {
            "id": updated_coil.id,
            "name": updated_coil.name,
            "remains": updated_coil.remains,
            "remains_percent": updated_coil.remains_percent,
        }
    })


@print_control_bp.route('/api/tasks/<int:task_id>/offline/complete', methods=['POST'])
def api_task_offline_complete(task_id: int):
    """Завершение оффлайн-задачи с опциональным списанием материала."""
    task = db.get_task(task_id)
    if not task:
        return jsonify({"success": False, "message": "Задача не найдена"}), 404

    printer = db.get_printer_by_id(task.printer_id) if task.printer_id else None
    if not printer or not getattr(printer, 'is_virtual', False):
        return jsonify({"success": False, "message": "Задача не привязана к оффлайн-принтеру"}), 400

    if task.status not in ('printing', 'paused'):
        return jsonify({"success": False, "message": "Задача должна быть в статусе печати или паузы"}), 400

    data = request.get_json(force=True, silent=True) or {}
    deduct_material = data.get('deduct_material', True)
    amount = data.get('amount')

    # Обновляем задачу
    db.update_task(
        task_id,
        status='completed',
        progress=100,
        time_end=datetime.now(timezone.utc).isoformat(),
    )

    # Сбрасываем статус принтера
    db.update_printer(printer.id, virtual_status='idle', manual_progress=0, manual_filename=None, manual_print_start=None)
    with printer_state_lock:
        if printer.id in printer_states:
            printer_states[printer.id]['status'] = 'idle'
            printer_states[printer.id]['progress'] = 0
            printer_states[printer.id]['filename'] = None

    # Списание материала
    deducted = None
    if deduct_material and task.coil_id:
        deduct_amount = amount if amount else task.estimated_filament
        if deduct_amount and deduct_amount > 0:
            coil = db.get_coil(task.coil_id)
            if coil and (coil.remains is None or coil.remains >= deduct_amount):
                notes = f"Автосписание при завершении: задача #{task_id}"
                db.deduct_material(task.coil_id, deduct_amount, task_id=task_id, notes=notes)
                deducted = deduct_amount

    updated_task = db.get_task(task_id)
    return jsonify({
        "success": True,
        "task": serialize_task(updated_task),
        "material_deducted": deducted,
    })
