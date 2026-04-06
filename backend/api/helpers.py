"""Общие helper-функции для blueprints.

Вынесены из web_interface.py, используются несколькими blueprints.
"""
import logging
import os
from typing import Dict, Optional

from flask import url_for

from backend.api.state import (
    db,
    ALLOWED_GCODE_EXTENSIONS,
    UPLOAD_DIR,
)
from backend.db.data_model import Printer, Task

logger = logging.getLogger(__name__)


def allowed_gcode_file(filename: str) -> bool:
    """Проверка допустимого расширения G-code файла."""
    return (
        bool(filename)
        and '.' in filename
        and filename.rsplit('.', 1)[1].lower() in ALLOWED_GCODE_EXTENSIONS
    )


def get_printer_or_default(printer_id: Optional[int]) -> Optional[Printer]:
    """Получить принтер по ID или первый активный."""
    if printer_id:
        printer = db.get_printer_by_id(printer_id)
        if printer and printer.is_active:
            return printer
    printers = db.get_printers(include_inactive=False)
    return printers[0] if printers else None


def serialize_task(task: Task) -> Dict:
    """Сериализация задачи в словарь для JSON-ответа."""
    return {
        "id": task.id,
        "name": task.name,
        "status": task.status,
        "notes": task.notes,
        "progress": task.progress,
        "material_amount": task.material_amount,
        "estimated_filament": task.estimated_filament,
        "estimated_time_minutes": task.estimated_time_minutes,
        "time_start": task.time_start,
        "time_end": task.time_end,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
        "project": {
            "id": task.project.id,
            "name": task.project.name,
            "color": task.project.color,
        } if task.project else None,
        "printer": {
            "id": task.printer.id,
            "name": task.printer.name,
        } if task.printer else None,
        "coil": {
            "id": task.coil.id,
            "name": task.coil.name,
            "material": task.coil.material.name if task.coil and task.coil.material else None,
        } if task.coil else None,
        "gcode": {
            "has_file": bool(task.model_gcode),
            "original_name": task.gcode_original_name,
            "uploaded_at": task.gcode_uploaded_at.isoformat() if task.gcode_uploaded_at else None,
            "download_url": url_for('tasks.api_task_gcode', task_id=task.id) if task.model_gcode else None,
            # Метаданные G-code
            "layer_count": task.gcode_layer_count,
            "layer_height": task.gcode_layer_height,
            "nozzle_temp": task.gcode_nozzle_temp,
            "bed_temp": task.gcode_bed_temp,
            "slicer": task.gcode_slicer,
        },
        # Данные печати
        "moonraker_filename": task.moonraker_filename,
        "actual_filament_used": task.actual_filament_used,
        "actual_print_time": task.actual_print_time,
    }


def remove_task_gcode(task: Task):
    """Удаление G-code файла задачи с диска и из БД."""
    if not task.model_gcode:
        return
    file_path = os.path.join(UPLOAD_DIR, task.model_gcode)
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except OSError as exc:
            logger.warning("Не удалось удалить файл G-code %s: %s", file_path, exc)
    db.update_task(
        task.id,
        model_gcode=None,
        gcode_original_name=None,
        gcode_uploaded_at=None,
        estimated_filament=None,
        estimated_time_minutes=None,
    )
