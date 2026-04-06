"""Фоновые задачи PrinterBase.

Опрос состояний принтеров, мониторинг печатающихся задач,
обработка завершения/ошибки/отмены печати.
"""
import logging
import os
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Optional

from backend.api.state import (
    db,
    printer_states,
    printer_state_lock,
    health_registry,
    DISCOVERY_ENABLED,
    DISCOVERY_INTERVAL_SECONDS,
    PRINTER_STATE_INTERVAL,
)
from backend.db.data_model import Printer, Task
from backend.services.moonraker_client import (
    fetch_printer_state,
    get_printer_print_status,
    synchronize_printers_with_db,
)

logger = logging.getLogger(__name__)

# ThreadPoolExecutor для параллельного опроса принтеров
_executor = ThreadPoolExecutor(max_workers=10)


def update_printer_states_loop():
    """Фоновый поток: параллельный опрос состояний принтеров с circuit breaker."""
    last_discovery = 0
    while True:
        now = time.time()
        if DISCOVERY_ENABLED and now - last_discovery > DISCOVERY_INTERVAL_SECONDS:
            synchronize_printers_with_db()
            last_discovery = now

        try:
            active_printers = db.get_printers(include_inactive=False)
            # Фильтруем принтеры с открытым circuit
            printers_to_poll = [
                p for p in active_printers
                if not health_registry.get(p.id).should_skip()
            ]

            if printers_to_poll:
                futures = {
                    _executor.submit(fetch_printer_state, p): p
                    for p in printers_to_poll
                }
                for future in as_completed(futures, timeout=15):
                    printer = futures[future]
                    try:
                        state = future.result()
                        with printer_state_lock:
                            printer_states[printer.id] = state
                        # Проверяем статус для circuit breaker
                        if state.get("status") == "offline":
                            health_registry.get(printer.id).record_failure()
                        else:
                            health_registry.get(printer.id).record_success()
                    except Exception:
                        logger.exception("Ошибка опроса принтера %s", printer.name)
                        health_registry.get(printer.id).record_failure()
                        with printer_state_lock:
                            printer_states[printer.id] = {
                                "status": "offline",
                                "message": "Ошибка опроса",
                            }

            # Для пропущенных принтеров — ставим offline
            for p in active_printers:
                if health_registry.get(p.id).should_skip():
                    with printer_state_lock:
                        if p.id not in printer_states:
                            printer_states[p.id] = {
                                "status": "offline",
                                "message": "Circuit breaker open",
                            }
        except Exception:
            logger.exception("Критическая ошибка в update_printer_states_loop")

        # Мониторинг печатающихся задач
        try:
            monitor_printing_tasks()
        except Exception as exc:
            logger.error("Ошибка мониторинга печатающихся задач: %s", exc)

        time.sleep(PRINTER_STATE_INTERVAL)


def monitor_printing_tasks():
    """Отслеживание прогресса печатающихся задач и обновление данных."""
    # Получаем задачи в статусе printing или paused
    printing_tasks = db.get_tasks_by_status(['printing', 'paused'])

    for task in printing_tasks:
        if not task.printer_id:
            continue

        printer = db.get_printer_by_id(task.printer_id)
        if not printer or printer.is_virtual:
            continue

        # Получаем статус печати с принтера
        print_status = get_printer_print_status(printer)
        if not print_status:
            continue

        print_stats = print_status.get('print_stats', {})
        virtual_sdcard = print_status.get('virtual_sdcard', {})

        moonraker_state = print_stats.get('state', '')
        moonraker_filename = print_stats.get('filename', '')
        progress = virtual_sdcard.get('progress', 0)
        filament_used = print_stats.get('filament_used')  # в мм
        print_duration = print_stats.get('print_duration')  # в секундах

        # Проверяем что это наша задача (по имени файла)
        if task.moonraker_filename and moonraker_filename:
            # Moonraker может возвращать полный путь или только имя файла
            task_filename = os.path.basename(task.moonraker_filename)
            current_filename = os.path.basename(moonraker_filename)
            if task_filename != current_filename:
                # Это другой файл, возможно печать была остановлена вручную
                continue

        # Обновляем прогресс задачи
        progress_percent = int(progress * 100)
        if progress_percent != task.progress:
            db.update_task(task.id, progress=progress_percent)

        # Обработка завершения печати
        if moonraker_state == 'complete':
            handle_print_complete(task, printer, filament_used, print_duration)
        elif moonraker_state == 'error':
            handle_print_error(task, printer, filament_used, print_duration)
        elif moonraker_state == 'cancelled':
            # Печать отменена напрямую через Moonraker (не через наш API)
            handle_print_cancelled(task, printer, filament_used, print_duration)
        elif moonraker_state == 'paused' and task.status == 'printing':
            # Пауза была выполнена напрямую через Moonraker
            db.update_task(task.id, status='paused')
        elif moonraker_state == 'printing' and task.status == 'paused':
            # Возобновление было выполнено напрямую через Moonraker
            db.update_task(task.id, status='printing')


def handle_print_complete(
    task: Task, printer: Printer,
    filament_used: Optional[float], print_duration: Optional[float]
):
    """Обработка успешного завершения печати."""
    actual_time_minutes = print_duration / 60 if print_duration else None

    # Обновляем время работы принтера
    if actual_time_minutes and actual_time_minutes > 0:
        current_hours = printer.print_hours or 0
        db.update_printer(printer.id, print_hours=current_hours + (actual_time_minutes / 60))

    # Обновляем задачу
    db.update_task(
        task.id,
        status='completed',
        progress=100,
        actual_filament_used=filament_used,
        actual_print_time=actual_time_minutes,
        time_end=datetime.now(timezone.utc).isoformat(),
    )

    # Автосписание материала
    if task.coil_id and task.estimated_filament and task.estimated_filament > 0:
        coil = db.get_coil(task.coil_id)
        if coil:
            amount = task.estimated_filament
            note = f"Автосписание: задача #{task.id} (completed)"
            db.deduct_material(task.coil_id, amount, task_id=task.id, notes=note)

    logger.info("Печать задачи #%s завершена успешно", task.id)


def handle_print_error(
    task: Task, printer: Printer,
    filament_used: Optional[float], print_duration: Optional[float]
):
    """Обработка ошибки печати."""
    actual_time_minutes = print_duration / 60 if print_duration else None

    # Обновляем время работы принтера
    if actual_time_minutes and actual_time_minutes > 0:
        current_hours = printer.print_hours or 0
        db.update_printer(printer.id, print_hours=current_hours + (actual_time_minutes / 60))

    db.update_task(
        task.id,
        status='cancelled',
        actual_filament_used=filament_used,
        actual_print_time=actual_time_minutes,
        time_end=datetime.now(timezone.utc).isoformat(),
        notes=(task.notes or '') + '\n[Ошибка печати]',
    )

    logger.warning("Печать задачи #%s завершилась с ошибкой", task.id)


def handle_print_cancelled(
    task: Task, printer: Printer,
    filament_used: Optional[float], print_duration: Optional[float]
):
    """Обработка отмены печати (напрямую через Moonraker)."""
    actual_time_minutes = print_duration / 60 if print_duration else None

    # Обновляем время работы принтера
    if actual_time_minutes and actual_time_minutes > 0:
        current_hours = printer.print_hours or 0
        db.update_printer(printer.id, print_hours=current_hours + (actual_time_minutes / 60))

    db.update_task(
        task.id,
        status='cancelled',
        actual_filament_used=filament_used,
        actual_print_time=actual_time_minutes,
        time_end=datetime.now(timezone.utc).isoformat(),
    )

    # Частичное списание материала при отмене
    if task.coil_id and filament_used and filament_used > 0:
        coil = db.get_coil(task.coil_id)
        if coil:
            # Конвертируем мм в граммы (примерно для PLA 1.75мм)
            amount_grams = filament_used / 1000 * 2.98
            note = f"Частичное списание при отмене: задача #{task.id}"
            db.deduct_material(task.coil_id, amount_grams, task_id=task.id, notes=note)

    logger.info("Печать задачи #%s отменена", task.id)


def start_background_threads(app):
    """Запуск фоновых потоков приложения.

    Args:
        app: Flask application instance (для config и начальной синхронизации).
    """
    if app.config.get("BACKGROUND_THREADS_STARTED"):
        return
    app.config["BACKGROUND_THREADS_STARTED"] = True
    synchronize_printers_with_db()
    # Инициализация типов обслуживания
    db.init_maintenance_types()
    # Создание записей обслуживания для существующих принтеров
    db.ensure_all_printers_maintenance()
    # Начальная синхронизация состояний чтобы кэш был заполнен сразу
    active_printers = db.get_printers(include_inactive=False)
    for printer in active_printers:
        state = fetch_printer_state(printer)
        with printer_state_lock:
            printer_states[printer.id] = state
    update_thread = threading.Thread(target=update_printer_states_loop, daemon=True)
    update_thread.start()
