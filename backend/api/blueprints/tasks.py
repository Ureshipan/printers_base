"""Blueprint: API задач (CRUD, G-code upload/parse)."""
import os
import tempfile
from datetime import datetime, timezone
from typing import Dict

from flask import Blueprint, jsonify, request, send_file
from werkzeug.utils import secure_filename

from backend.api.state import db, UPLOAD_DIR
from backend.api.helpers import (
    allowed_gcode_file,
    serialize_task,
    remove_task_gcode,
)
from backend.services.gcode_parser import parse_gcode_file

tasks_bp = Blueprint('tasks', __name__)


@tasks_bp.route('/api/tasks', methods=['GET', 'POST'])
def api_tasks():
    if request.method == 'GET':
        tasks = db.get_tasks()
        return jsonify([serialize_task(task) for task in tasks])

    data = request.get_json(force=True, silent=True) or {}
    required_fields = ['project_id', 'printer_id']
    missing = [field for field in required_fields if data.get(field) is None]
    if missing:
        return jsonify({"success": False, "message": f"Отсутствуют поля: {', '.join(missing)}"}), 400

    task = db.add_task(
        name=data.get('name'),
        status=data.get('status', 'pending'),
        notes=data.get('notes'),
        progress=data.get('progress', 0),
        material_amount=data.get('material_amount'),
        project_id=data['project_id'],
        printer_id=data['printer_id'],
        coil_id=data.get('coil_id'),
        time_start=data.get('time_start'),
        time_end=data.get('time_end'),
    )
    task = db.get_task(task.id)
    return jsonify({"success": True, "task": serialize_task(task)})


@tasks_bp.route('/api/tasks/<int:task_id>', methods=['GET', 'PUT', 'PATCH', 'DELETE'])
def api_task_detail(task_id: int):
    task = db.get_task(task_id)
    if not task:
        return jsonify({"success": False, "message": "Задача не найдена"}), 404

    if request.method == 'GET':
        return jsonify({"success": True, "task": serialize_task(task)})

    if request.method in ('PUT', 'PATCH'):
        data = request.get_json(force=True, silent=True) or {}

        # Сохраняем старый статус для проверки автосписания
        old_status = task.status
        new_status = data.get('status', old_status)

        updated_task = db.update_task(
            task_id,
            **{
                key: data.get(key)
                for key in [
                    'name',
                    'status',
                    'notes',
                    'progress',
                    'material_amount',
                    'project_id',
                    'printer_id',
                    'coil_id',
                    'time_start',
                    'time_end',
                ]
                if key in data
            }
        )
        if not updated_task:
            return jsonify({"success": False, "message": "Не удалось обновить задачу"}), 400

        # Автосписание материала при завершении/отмене задачи
        deducted_info = None
        if (new_status in ('completed', 'cancelled') and
                old_status not in ('completed', 'cancelled')):
            # Проверяем есть ли катушка и расход материала
            if task.coil_id and task.estimated_filament and task.estimated_filament > 0:
                coil = db.get_coil(task.coil_id)
                if coil:
                    amount = task.estimated_filament
                    note = f"Автосписание: задача #{task_id} ({new_status})"
                    db.deduct_material(task.coil_id, amount, task_id=task_id, notes=note)
                    deducted_info = {
                        "coil_id": task.coil_id,
                        "amount": amount,
                        "coil_name": coil.name,
                    }

        updated_task = db.get_task(task_id)
        response = {"success": True, "task": serialize_task(updated_task)}
        if deducted_info:
            response["material_deducted"] = deducted_info
        return jsonify(response)

    # DELETE
    remove_task_gcode(task)
    deleted = db.delete_task(task_id)
    return jsonify({"success": deleted})


@tasks_bp.route('/api/tasks/<int:task_id>/gcode', methods=['POST', 'GET', 'DELETE'])
def api_task_gcode(task_id: int):
    task = db.get_task(task_id)
    if not task:
        return jsonify({"success": False, "message": "Задача не найдена"}), 404

    if request.method == 'GET':
        if not task.model_gcode:
            return jsonify({"success": False, "message": "G-code для задачи не загружен"}), 404
        file_path = os.path.join(UPLOAD_DIR, task.model_gcode)
        if not os.path.exists(file_path):
            return jsonify({"success": False, "message": "Файл не найден"}), 404
        download_name = task.gcode_original_name or os.path.basename(file_path)
        return send_file(file_path, as_attachment=True, download_name=download_name)

    if request.method == 'DELETE':
        remove_task_gcode(task)
        return jsonify({"success": True})

    # POST - upload
    if 'file' not in request.files:
        return jsonify({"success": False, "message": "Файл не найден в запросе"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"success": False, "message": "Имя файла пустое"}), 400
    if not allowed_gcode_file(file.filename):
        return jsonify({"success": False, "message": "Неподдерживаемый формат файла"}), 400

    # remove old file first
    remove_task_gcode(task)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    safe_name = secure_filename(file.filename)
    stored_name = f"task_{task.id}_{timestamp}_{safe_name}"
    stored_path = os.path.join(UPLOAD_DIR, stored_name)
    file.save(stored_path)

    # Парсим метаданные G-code
    metadata = parse_gcode_file(stored_path)

    # Fallback на размер файла если парсинг не дал результатов
    estimated_filament = metadata.filament_weight_grams
    estimated_time = metadata.estimated_time_minutes
    if estimated_filament is None or estimated_time is None:
        size_kb = os.path.getsize(stored_path) / 1024
        if estimated_filament is None:
            estimated_filament = round(5.0 + size_kb * 0.05, 2)
        if estimated_time is None:
            estimated_time = round(30.0 + size_kb * 0.2, 1)

    # Формируем строку слайсера
    slicer_str = None
    if metadata.slicer_name:
        slicer_str = metadata.slicer_name
        if metadata.slicer_version:
            slicer_str += f" {metadata.slicer_version}"

    updated_task = db.update_task(
        task.id,
        model_gcode=stored_name,
        gcode_original_name=file.filename,
        gcode_uploaded_at=datetime.now(timezone.utc),
        estimated_filament=estimated_filament,
        estimated_time_minutes=estimated_time,
        material_amount=estimated_filament,
        # Метаданные G-code
        gcode_layer_count=metadata.layer_count,
        gcode_layer_height=metadata.layer_height,
        gcode_nozzle_temp=metadata.nozzle_temp,
        gcode_bed_temp=metadata.bed_temp,
        gcode_slicer=slicer_str,
    )
    if not updated_task:
        return jsonify({"success": False, "message": "Не удалось сохранить данные файла"}), 500
    updated_task = db.get_task(task.id)
    return jsonify({"success": True, "task": serialize_task(updated_task)})


@tasks_bp.route('/api/gcode/parse', methods=['POST'])
def api_gcode_parse():
    """
    Парсит G-code файл и возвращает метаданные без сохранения.
    Используется для предзаполнения полей при создании задачи.
    """
    if 'file' not in request.files:
        return jsonify({"success": False, "message": "Файл не найден в запросе"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"success": False, "message": "Имя файла пустое"}), 400
    if not allowed_gcode_file(file.filename):
        return jsonify({"success": False, "message": "Неподдерживаемый формат файла"}), 400

    # Сохраняем временный файл для парсинга
    with tempfile.NamedTemporaryFile(delete=False, suffix='.gcode') as tmp:
        file.save(tmp.name)
        tmp_path = tmp.name

    try:
        metadata = parse_gcode_file(tmp_path)

        # Fallback на размер файла если парсинг не дал результатов
        estimated_filament = metadata.filament_weight_grams
        estimated_time = metadata.estimated_time_minutes
        if estimated_filament is None or estimated_time is None:
            size_kb = os.path.getsize(tmp_path) / 1024
            if estimated_filament is None:
                estimated_filament = round(5.0 + size_kb * 0.05, 2)
            if estimated_time is None:
                estimated_time = round(30.0 + size_kb * 0.2, 1)

        # Формируем строку слайсера
        slicer_str = None
        if metadata.slicer_name:
            slicer_str = metadata.slicer_name
            if metadata.slicer_version:
                slicer_str += f" {metadata.slicer_version}"

        # Извлекаем имя из файла (без расширения) для названия задачи
        base_name = os.path.splitext(file.filename)[0]

        return jsonify({
            "success": True,
            "filename": file.filename,
            "suggested_name": base_name,
            "estimated_filament": estimated_filament,
            "estimated_time_minutes": estimated_time,
            "layer_count": metadata.layer_count,
            "layer_height": metadata.layer_height,
            "nozzle_temp": metadata.nozzle_temp,
            "bed_temp": metadata.bed_temp,
            "slicer": slicer_str,
        })
    finally:
        # Удаляем временный файл
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
