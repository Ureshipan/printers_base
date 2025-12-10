import os
import sys
import threading
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import requests
from flask import (
    Flask,
    jsonify,
    render_template,
    request,
    send_file,
    url_for,
)
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

# Add the project root to the Python path
PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
sys.path.append(PROJECT_ROOT)

if os.path.exists(os.path.join(PROJECT_ROOT, ".env")):
    load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

from backend.db.data_model import DBModel, Coil, Printer, Project, Task, MaintenanceType, MaintenanceRecord, Vendor, SpoolHistory  # noqa: E402
from backend.services.gcode_parser import parse_gcode_file  # noqa: E402


app = Flask(
    __name__,
    template_folder='../../frontend/templates',
    static_folder='../../frontend/static',
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DEFAULT_PRINTER_PORT = int(os.environ.get("MOONRAKER_PORT", "7125"))
DEFAULT_FALLBACK_HOST = os.environ.get("MOONRAKER_DEFAULT_HOST", "172.22.112.68")
DISCOVERY_ENABLED = os.environ.get("PRINTER_DISCOVERY_ENABLED", "0") == "1"
DISCOVERY_INTERVAL_SECONDS = int(os.environ.get("PRINTER_DISCOVERY_INTERVAL", "60"))
PRINTER_STATE_INTERVAL = float(os.environ.get("PRINTER_STATE_INTERVAL", "1.0"))
ALLOWED_GCODE_EXTENSIONS = {"gcode", "gco", "gc", "g"}
ALLOWED_VIRTUAL_STATUSES = {"idle", "work", "error", "service", "offline", "printing", "ready"}

DATABASE_PATH = os.path.join(PROJECT_ROOT, 'backend', 'db', 'database.db')
UPLOAD_DIR = os.path.join(PROJECT_ROOT, 'backend', 'uploads', 'gcode')
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_DIR
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024  # 200MB

db = DBModel(db_path=DATABASE_PATH)
http = requests.Session()

printer_states: Dict[int, Dict] = {}
printer_state_lock = threading.Lock()

STATE_MAP = {
    "printing": "work",
    "paused": "idle",
    "standby": "idle",
    "complete": "idle",
    "error": "error",
    "offline": "offline",
    "ready": "idle",
}


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------
def allowed_gcode_file(filename: str) -> bool:
    return (
        bool(filename)
        and '.' in filename
        and filename.rsplit('.', 1)[1].lower() in ALLOWED_GCODE_EXTENSIONS
    )


def build_printer_key(printer: Printer) -> Tuple[str, int, str]:
    return (
        printer.moonraker_host or '',
        printer.moonraker_port or DEFAULT_PRINTER_PORT,
        printer.moonraker_printer or '',
    )


def build_base_url(printer: Printer) -> str:
    host = printer.moonraker_host or DEFAULT_FALLBACK_HOST
    port = printer.moonraker_port or DEFAULT_PRINTER_PORT
    return f"http://{host}:{port}"


def enrich_params_with_printer(printer: Printer, params: Optional[List[Tuple[str, str]]] = None) -> List[Tuple[str, str]]:
    params_list = list(params or [])
    if printer.moonraker_printer:
        params_list.append(('printer', printer.moonraker_printer))
    return params_list


def _perform_moonraker_request(
    base_url: str,
    endpoint: str,
    method: str,
    params: Optional[List[Tuple[str, str]]] = None,
    payload: Optional[dict] = None,
    timeout: int = 5,
):
    if method == "GET":
        return http.get(f"{base_url}/{endpoint}", params=params, timeout=timeout)
    if method == "POST":
        query_params = dict(params) if params else None
        return http.post(f"{base_url}/{endpoint}", params=query_params, json=payload, timeout=timeout)
    raise ValueError(f"Unsupported method {method}")


def _request_with_fallback(
    printer: Printer,
    endpoint: str,
    method: str,
    params: Optional[List[Tuple[str, str]]] = None,
    payload: Optional[dict] = None,
    timeout: int = 5,
):
    params_list = enrich_params_with_printer(printer, params)
    base_url = build_base_url(printer)
    try:
        response = _perform_moonraker_request(base_url, endpoint, method, params_list, payload, timeout)
        response.raise_for_status()
        return response
    except requests.RequestException as exc:
        app.logger.warning("Moonraker %s %s failed for %s:%s (%s)", method, endpoint, printer.moonraker_host, printer.moonraker_port, exc)
        # Try fallback host if configured
        if printer.moonraker_host and printer.moonraker_host != DEFAULT_FALLBACK_HOST:
            fallback_base_url = f"http://{DEFAULT_FALLBACK_HOST}:{DEFAULT_PRINTER_PORT}"
            try:
                fallback_response = _perform_moonraker_request(
                    fallback_base_url, endpoint, method, params_list, payload, timeout
                )
                fallback_response.raise_for_status()
                app.logger.info("Использован резервный Moonraker-хост %s для принтера %s", DEFAULT_FALLBACK_HOST, printer.id)
                return fallback_response
            except requests.RequestException as fallback_exc:
                app.logger.warning("Fallback Moonraker %s %s failed for %s:%s (%s)", method, endpoint, DEFAULT_FALLBACK_HOST, DEFAULT_PRINTER_PORT, fallback_exc)
        return None


def moonraker_get(printer: Printer, endpoint: str, params=None, timeout: int = 5):
    response = _request_with_fallback(printer, endpoint, "GET", params=params, timeout=timeout)
    if response is None:
        return None
    return response.json()


def moonraker_post(printer: Printer, endpoint: str, payload: dict, timeout: int = 5):
    response = _request_with_fallback(printer, endpoint, "POST", payload=payload, timeout=timeout)
    if response is None:
        return None
    return response.json()


def fetch_printers_for_host(host: str, port: int) -> List[Dict[str, Optional[str]]]:
    base_url = f"http://{host}:{port}"
    try:
        response = http.get(f"{base_url}/server/printers/list", timeout=5)
        if response.status_code == 200:
            result = response.json().get("result", {})
            printers = result.get("printers", [])
            if printers:
                return [
                    {
                        "moonraker_printer": printer.get("name"),
                        "display_name": printer.get("description") or printer.get("name"),
                    }
                    for printer in printers
                ]
    except requests.RequestException:
        pass
    # Fallback single printer configuration
    return [{"moonraker_printer": None, "display_name": None}]


def fetch_printer_display_name(host: str, port: int, printer_name: Optional[str]) -> Optional[str]:
    base_url = f"http://{host}:{port}"
    params = []
    if printer_name:
        params.append(('printer', printer_name))
    try:
        response = http.get(f"{base_url}/printer/info", params=params, timeout=5)
        if response.status_code == 200:
            data = response.json().get("result", {})
            return (
                data.get("display_name")
                or data.get("printer_name")
                or data.get("hostname")
                or printer_name
                or host
            )
    except requests.RequestException:
        pass
    return printer_name or host


def probe_moonraker_host(host: str, port: int, timeout: int = 3) -> bool:
    """Проверить, отвечает ли Moonraker по указанному адресу."""
    base_url = f"http://{host}:{port}"
    try:
        response = http.get(f"{base_url}/server/info", timeout=timeout)
        response.raise_for_status()
        return True
    except requests.RequestException:
        return False


def upsert_printers_for_host(host: str, port: int) -> List[Printer]:
    """Создать или обновить записи принтеров для указанного Moonraker-хоста."""
    printers_on_host = fetch_printers_for_host(host, port)
    added = []
    for printer_entry in printers_on_host:
        moonraker_printer = printer_entry.get("moonraker_printer")
        display_name = printer_entry.get("display_name") or fetch_printer_display_name(
            host, port, moonraker_printer
        )
        printer = db.upsert_printer(
            name=display_name or host,
            moonraker_host=host,
            moonraker_port=port,
            moonraker_printer=moonraker_printer,
            is_active=True,
        )
        added.append(printer)
    return added


def synchronize_printers_with_db():
    # Network discovery is disabled by default to avoid broadcast scans.
    # Set PRINTER_DISCOVERY_ENABLED=1 to re-enable auto-discovery.
    if not DISCOVERY_ENABLED:
        return

    discovered_hosts = []
    try:
        from discovery.pi_discover import scan_no_cli
        discovered_hosts = scan_no_cli()
    except Exception as exc:  # pylint: disable=broad-except
        app.logger.warning("Не удалось выполнить поиск принтеров: %s", exc)

    if not discovered_hosts and DEFAULT_FALLBACK_HOST:
        discovered_hosts = [DEFAULT_FALLBACK_HOST]

    discovered_keys = set()
    for host in discovered_hosts:
        printers_on_host = fetch_printers_for_host(host, DEFAULT_PRINTER_PORT)
        for printer_entry in printers_on_host:
            moonraker_printer = printer_entry.get("moonraker_printer")
            name = fetch_printer_display_name(host, DEFAULT_PRINTER_PORT, moonraker_printer)
            printer = db.upsert_printer(
                name=name,
                moonraker_host=host,
                moonraker_port=DEFAULT_PRINTER_PORT,
                moonraker_printer=moonraker_printer,
                is_active=True,
            )
            discovered_keys.add(build_printer_key(printer))

    # Mark printers not discovered as inactive
    for printer in db.get_printers(include_inactive=True):
        key = build_printer_key(printer)
        if key not in discovered_keys and printer.is_active:
            db.set_printer_active(printer.id, False)


def build_default_state() -> Dict:
    return {
        "status": "offline",
        "temperature": {"extruder": 0.0, "bed": 0.0},
        "target_temperature": {"extruder": 0.0, "bed": 0.0},
        "position": {"x": 0.0, "y": 0.0, "z": 0.0},
        "progress": 0,
        "filename": None,
        "last_update": datetime.now(timezone.utc).isoformat(),
    }


def fetch_printer_state(printer: Printer) -> Dict:
    if getattr(printer, "is_virtual", False):
        state = build_default_state()
        state["status"] = getattr(printer, "virtual_status", "idle") or "idle"
        return state

    state = build_default_state()
    base_url = build_base_url(printer)
    # Используем POST с JSON-телом согласно документации Moonraker API
    query_payload = {
        "objects": {
            "webhooks": None,
            "print_stats": None,
            "extruder": None,
            "heater_bed": None,
            "toolhead": None,
            "virtual_sdcard": None,
        }
    }
    params = enrich_params_with_printer(printer, [])
    try:
        # Короткий timeout чтобы офлайн принтеры не блокировали обновление других
        response = http.post(
            f"{base_url}/printer/objects/query",
            params=params,
            json=query_payload,
            timeout=2
        )
        response.raise_for_status()
        payload = response.json().get("result", {}).get("status", {})
    except requests.RequestException as exc:
        app.logger.debug("Не удалось обновить состояние принтера %s: %s", printer.id, exc)
        state["status"] = "offline"
        return state

    try:
        webhooks = payload.get("webhooks", {})
        print_stats = payload.get("print_stats", {})
        extruder = payload.get("extruder", {})
        heater_bed = payload.get("heater_bed", {})
        toolhead = payload.get("toolhead", {})
        virtual_sdcard = payload.get("virtual_sdcard", {})

        # Проверяем состояние Klipper через webhooks
        klipper_state = webhooks.get("state", "unknown")
        if klipper_state != "ready":
            # Klipper не готов (startup, shutdown, error)
            state["status"] = "offline" if klipper_state == "shutdown" else "error"
            state["status_message"] = webhooks.get("state_message", "")
            return state

        state["status"] = print_stats.get("state", "standby")
        state["temperature"]["extruder"] = extruder.get("temperature", 0.0)
        state["temperature"]["bed"] = heater_bed.get("temperature", 0.0)
        state["target_temperature"]["extruder"] = extruder.get("target", 0.0)
        state["target_temperature"]["bed"] = heater_bed.get("target", 0.0)
        position = toolhead.get("position", [0.0, 0.0, 0.0])
        state["position"] = {
            "x": position[0] if len(position) > 0 else 0.0,
            "y": position[1] if len(position) > 1 else 0.0,
            "z": position[2] if len(position) > 2 else 0.0,
        }
        progress = virtual_sdcard.get("progress")
        if progress is not None:
            state["progress"] = int(progress * 100)
        state["filename"] = print_stats.get("filename")
        state["last_update"] = datetime.now(timezone.utc).isoformat()
    except Exception as exc:  # pylint: disable=broad-except
        app.logger.warning("Ошибка обработки состояния принтера %s: %s", printer.id, exc)

    return state


def update_printer_states_loop():
    last_discovery = 0
    while True:
        now = time.time()
        if DISCOVERY_ENABLED and now - last_discovery > DISCOVERY_INTERVAL_SECONDS:
            synchronize_printers_with_db()
            last_discovery = now

        active_printers = db.get_printers(include_inactive=False)
        for printer in active_printers:
            state = fetch_printer_state(printer)
            with printer_state_lock:
                printer_states[printer.id] = state

        # Мониторинг печатающихся задач
        try:
            monitor_printing_tasks()
        except Exception as exc:
            app.logger.error("Ошибка мониторинга печатающихся задач: %s", exc)

        time.sleep(PRINTER_STATE_INTERVAL)


def monitor_printing_tasks():
    """Отслеживание прогресса печатающихся задач и обновление данных."""
    # Получаем задачи в статусе printing или paused
    printing_tasks = db.get_tasks_by_status(['printing', 'paused'])

    for task in printing_tasks:
        if not task.printer_id:
            continue

        printer = db.get_printer(task.printer_id)
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


def handle_print_complete(task: Task, printer: Printer, filament_used: Optional[float], print_duration: Optional[float]):
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

    app.logger.info("Печать задачи #%s завершена успешно", task.id)


def handle_print_error(task: Task, printer: Printer, filament_used: Optional[float], print_duration: Optional[float]):
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

    app.logger.warning("Печать задачи #%s завершилась с ошибкой", task.id)


def handle_print_cancelled(task: Task, printer: Printer, filament_used: Optional[float], print_duration: Optional[float]):
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

    app.logger.info("Печать задачи #%s отменена", task.id)


def get_printer_or_default(printer_id: Optional[int]) -> Optional[Printer]:
    if printer_id:
        printer = db.get_printer_by_id(printer_id)
        if printer and printer.is_active:
            return printer
    printers = db.get_printers(include_inactive=False)
    return printers[0] if printers else None


def serialize_task(task: Task) -> Dict:
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
            "download_url": url_for('api_task_gcode', task_id=task.id) if task.model_gcode else None,
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
    if not task.model_gcode:
        return
    file_path = os.path.join(UPLOAD_DIR, task.model_gcode)
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except OSError as exc:
            app.logger.warning("Не удалось удалить файл G-code %s: %s", file_path, exc)
    db.update_task(
        task.id,
        model_gcode=None,
        gcode_original_name=None,
        gcode_uploaded_at=None,
        estimated_filament=None,
        estimated_time_minutes=None,
    )


# ---------------------------------------------------------------------------
# Moonraker Print Control Functions
# ---------------------------------------------------------------------------
def upload_gcode_to_printer(printer: Printer, local_file_path: str, filename: str) -> Tuple[bool, str]:
    """
    Загрузка G-code файла на принтер через Moonraker API.
    Возвращает (success, message/uploaded_filename).
    """
    base_url = build_base_url(printer)
    url = f"{base_url}/server/files/upload"

    try:
        with open(local_file_path, 'rb') as f:
            files = {'file': (filename, f, 'application/octet-stream')}
            data = {'root': 'gcodes'}
            response = http.post(url, files=files, data=data, timeout=60)
            response.raise_for_status()
            result = response.json()
            uploaded_path = result.get('item', {}).get('path', filename)
            return True, uploaded_path
    except requests.RequestException as exc:
        app.logger.error("Ошибка загрузки G-code на принтер %s: %s", printer.id, exc)
        return False, str(exc)
    except Exception as exc:
        app.logger.error("Ошибка при загрузке файла: %s", exc)
        return False, str(exc)


def start_print_on_printer(printer: Printer, filename: str) -> Tuple[bool, str]:
    """
    Запуск печати файла на принтере через Moonraker API.
    """
    base_url = build_base_url(printer)
    url = f"{base_url}/printer/print/start"

    try:
        response = http.post(url, params={'filename': filename}, timeout=10)
        response.raise_for_status()
        return True, "ok"
    except requests.RequestException as exc:
        app.logger.error("Ошибка запуска печати на принтере %s: %s", printer.id, exc)
        return False, str(exc)


def pause_print_on_printer(printer: Printer) -> Tuple[bool, str]:
    """Пауза печати на принтере."""
    base_url = build_base_url(printer)
    try:
        response = http.post(f"{base_url}/printer/print/pause", timeout=10)
        response.raise_for_status()
        return True, "ok"
    except requests.RequestException as exc:
        app.logger.error("Ошибка паузы печати на принтере %s: %s", printer.id, exc)
        return False, str(exc)


def resume_print_on_printer(printer: Printer) -> Tuple[bool, str]:
    """Возобновление печати на принтере."""
    base_url = build_base_url(printer)
    try:
        response = http.post(f"{base_url}/printer/print/resume", timeout=10)
        response.raise_for_status()
        return True, "ok"
    except requests.RequestException as exc:
        app.logger.error("Ошибка возобновления печати на принтере %s: %s", printer.id, exc)
        return False, str(exc)


def cancel_print_on_printer(printer: Printer) -> Tuple[bool, str]:
    """Отмена печати на принтере."""
    base_url = build_base_url(printer)
    try:
        response = http.post(f"{base_url}/printer/print/cancel", timeout=10)
        response.raise_for_status()
        return True, "ok"
    except requests.RequestException as exc:
        app.logger.error("Ошибка отмены печати на принтере %s: %s", printer.id, exc)
        return False, str(exc)


def get_printer_print_status(printer: Printer) -> Optional[Dict]:
    """
    Получить статус печати с принтера.
    Возвращает данные print_stats и virtual_sdcard.
    """
    base_url = build_base_url(printer)
    url = f"{base_url}/printer/objects/query"
    payload = {
        "objects": {
            "print_stats": None,
            "virtual_sdcard": None,
        }
    }
    try:
        response = http.post(url, json=payload, timeout=5)
        response.raise_for_status()
        result = response.json().get('result', {})
        return result.get('status', {})
    except requests.RequestException as exc:
        app.logger.warning("Ошибка получения статуса печати принтера %s: %s", printer.id, exc)
        return None


# ---------------------------------------------------------------------------
# Routes - Pages
# ---------------------------------------------------------------------------
@app.route('/')
def index():
    return render_template('dashboard.html')


@app.route('/printer-control')
def printer_control():
    return render_template('printer-control.html')


@app.route('/planning')
def planning():
    return render_template('planning.html')


@app.route('/maintenance')
def maintenance():
    return render_template('maintenance.html')


@app.route('/spools')
def spools():
    return render_template('spools.html')


# ---------------------------------------------------------------------------
# Routes - API
# ---------------------------------------------------------------------------
@app.route('/api/printers', methods=['GET', 'POST'])
def api_printers():
    if request.method == 'GET':
        printers = db.get_printers(include_inactive=False)
        result = []
        with printer_state_lock:
            for printer in printers:
                state = printer_states.get(printer.id, build_default_state())
                mapped_status = STATE_MAP.get(state["status"], state["status"])
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


@app.route('/api/printers/virtual', methods=['POST'])
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


@app.route('/api/printers/<int:printer_id>', methods=['GET', 'PUT', 'DELETE'])
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

        # Для виртуальных принтеров можно менять статус
        if getattr(printer, "is_virtual", False) and 'status' in data:
            status = (data.get('status') or '').strip().lower()
            if status and status in ALLOWED_VIRTUAL_STATUSES:
                updates['virtual_status'] = status
                # Обновляем кэш состояния
                with printer_state_lock:
                    if printer_id in printer_states:
                        printer_states[printer_id]['status'] = status

        # Для реальных принтеров можно менять host/port
        if not getattr(printer, "is_virtual", False):
            if 'host' in data:
                updates['moonraker_host'] = (data.get('host') or '').strip()
            if 'port' in data:
                try:
                    updates['moonraker_port'] = int(data.get('port'))
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


@app.route('/api/state')
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


@app.route('/api/command', methods=['POST'])
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


@app.route('/api/home', methods=['POST'])
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


@app.route('/api/temperature', methods=['POST'])
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


def _serialize_project(project: Project) -> Dict:
    return {
        "id": project.id,
        "name": project.name,
        "desc": project.desc,
        "color": project.color,
    }


def _validate_hex_color(value: Optional[str]) -> Optional[str]:
    if not value:
        return value
    color = value.strip()
    if len(color) not in (4, 7):
        raise ValueError("Цвет должен быть в формате HEX, например #ff00ff")
    if not color.startswith('#'):
        raise ValueError("Цвет должен начинаться с символа #")
    if any(ch not in "0123456789abcdefABCDEF" for ch in color[1:]):
        raise ValueError("Цвет может содержать только шестнадцатеричные символы")
    return color


@app.route('/api/projects', methods=['GET', 'POST'])
def api_projects():
    if request.method == 'GET':
        projects = db.get_projects()
        return jsonify([_serialize_project(project) for project in projects])

    data = request.get_json(force=True, silent=True) or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({"success": False, "message": "Название проекта обязательно"}), 400

    try:
        color = _validate_hex_color(data.get('color')) or "#888888"
    except ValueError as exc:
        return jsonify({"success": False, "message": str(exc)}), 400

    project = db.add_project(
        name=name,
        desc=(data.get('desc') or '').strip() or None,
        color=color,
    )
    return jsonify({"success": True, "project": _serialize_project(project)})


@app.route('/api/projects/<int:project_id>', methods=['GET', 'PUT', 'PATCH', 'DELETE'])
def api_project_detail(project_id: int):
    project = db.get_project(project_id)
    if not project:
        return jsonify({"success": False, "message": "Проект не найден"}), 404

    if request.method == 'GET':
        return jsonify({"success": True, "project": _serialize_project(project)})

    if request.method in ('PUT', 'PATCH'):
        data = request.get_json(force=True, silent=True) or {}
        updates: Dict[str, Optional[str]] = {}

        if 'name' in data:
            name = (data.get('name') or '').strip()
            if not name:
                return jsonify({"success": False, "message": "Название проекта обязательно"}), 400
            updates['name'] = name

        if 'desc' in data:
            updates['desc'] = (data.get('desc') or '').strip() or None

        if 'color' in data:
            try:
                updates['color'] = _validate_hex_color(data.get('color')) or "#888888"
            except ValueError as exc:
                return jsonify({"success": False, "message": str(exc)}), 400

        if not updates:
            return jsonify({"success": False, "message": "Нет данных для обновления"}), 400

        updated_project = db.update_project(project_id, **updates)
        if not updated_project:
            return jsonify({"success": False, "message": "Не удалось обновить проект"}), 400
        return jsonify({"success": True, "project": _serialize_project(updated_project)})

    # DELETE
    if db.delete_project(project_id):
        return jsonify({"success": True})
    return jsonify({
        "success": False,
        "message": "Не удалось удалить проект. Возможно, к нему все еще привязаны задачи."
    }), 409


def serialize_coil(coil: Coil) -> dict:
    """Сериализация катушки с расширенными полями."""
    # Данные из филамента (приоритетные)
    filament = coil.filament
    filament_data = None
    if filament:
        filament_data = {
            "id": filament.id,
            "name": filament.name,
            "material": filament.material,
            "color_hex": filament.color_hex,
            "vendor_id": filament.vendor_id,
            "vendor_name": filament.vendor.name if filament.vendor else None,
        }

    # Цвет: из катушки или из филамента
    color = coil.color_hex or (filament.color_hex if filament else None)

    return {
        "id": coil.id,
        "name": coil.name,
        "filament": filament_data,
        "filament_id": coil.filament_id,
        # Deprecated поля для совместимости
        "material": coil.material.name if coil.material else (filament.material if filament else None),
        "material_id": coil.material_id,
        "vendor": {"id": coil.vendor.id, "name": coil.vendor.name} if coil.vendor else (
            {"id": filament.vendor.id, "name": filament.vendor.name} if filament and filament.vendor else None
        ),
        "vendor_id": coil.vendor_id,
        "remains": coil.remains,
        "initial_weight": coil.initial_weight,
        "used_weight": coil.used_weight,
        "spool_weight": coil.spool_weight,
        "total_weight": coil.total_weight,
        "color_hex": color,
        "price": coil.price,
        "location": coil.location,
        "lot_nr": coil.lot_nr,
        "comment": coil.comment,
        "archived": coil.archived or False,
        "first_used": coil.first_used.isoformat() if coil.first_used else None,
        "last_used": coil.last_used.isoformat() if coil.last_used else None,
        "remains_percent": coil.remains_percent,
        "remains_status": coil.remains_status,
    }


@app.route('/api/coils', methods=['GET', 'POST'])
def api_coils():
    """GET: Список катушек с фильтрами. POST: Создать катушку."""
    if request.method == 'GET':
        filament_id = request.args.get('filament_id', type=int)
        material_id = request.args.get('material_id', type=int)
        vendor_id = request.args.get('vendor_id', type=int)
        archived = request.args.get('archived')
        include_archived = request.args.get('include_archived', '0') == '1'

        archived_filter = None
        if archived is not None:
            archived_filter = archived.lower() in ('true', '1', 'yes')

        coils = db.get_coils(
            filament_id=filament_id,
            material_id=material_id,
            vendor_id=vendor_id,
            archived=archived_filter,
            include_archived=include_archived,
        )
        return jsonify([serialize_coil(coil) for coil in coils])

    # POST - создание катушки
    data = request.get_json(force=True, silent=True) or {}
    # filament_id обязателен, остальное опционально
    required_fields = ['name', 'filament_id', 'remains']
    missing = [f for f in required_fields if data.get(f) is None]
    if missing:
        return jsonify({"success": False, "message": f"Отсутствуют поля: {', '.join(missing)}"}), 400

    coil = db.add_coil(
        name=data['name'],
        filament_id=data['filament_id'],
        remains=data['remains'],
        material_id=data.get('material_id'),  # Deprecated
        vendor_id=data.get('vendor_id'),  # Deprecated
        spool_weight=data.get('spool_weight'),
        initial_weight=data.get('initial_weight', data['remains']),
        color_hex=data.get('color_hex'),
        price=data.get('price'),
        location=data.get('location'),
        lot_nr=data.get('lot_nr'),
        comment=data.get('comment'),
    )
    coil = db.get_coil(coil.id)
    return jsonify({"success": True, "coil": serialize_coil(coil)})


@app.route('/api/coils/<int:coil_id>', methods=['GET', 'PUT', 'PATCH', 'DELETE'])
def api_coil_detail(coil_id: int):
    """Операции с конкретной катушкой."""
    coil = db.get_coil(coil_id)
    if not coil:
        return jsonify({"success": False, "message": "Катушка не найдена"}), 404

    if request.method == 'GET':
        result = serialize_coil(coil)
        # Добавляем историю для детального просмотра
        history = db.get_spool_history(coil_id=coil_id, limit=50)
        result['history'] = [
            {
                "id": h.id,
                "used_weight": h.used_weight,
                "timestamp": h.timestamp.isoformat() if h.timestamp else None,
                "notes": h.notes,
                "task": {"id": h.task.id, "name": h.task.name} if h.task else None,
            }
            for h in history
        ]
        return jsonify(result)

    if request.method == 'DELETE':
        if db.delete_coil(coil_id):
            return jsonify({"success": True})
        return jsonify({"success": False, "message": "Не удалось удалить катушку"}), 400

    # PUT/PATCH - обновление
    data = request.get_json(force=True, silent=True) or {}
    updated = db.update_coil(coil_id, **data)
    if updated:
        updated = db.get_coil(coil_id)
        return jsonify({"success": True, "coil": serialize_coil(updated)})
    return jsonify({"success": False, "message": "Не удалось обновить катушку"}), 400


@app.route('/api/coils/<int:coil_id>/archive', methods=['POST'])
def api_coil_archive(coil_id: int):
    """Архивировать катушку."""
    coil = db.archive_coil(coil_id)
    if coil:
        coil = db.get_coil(coil_id)
        return jsonify({"success": True, "coil": serialize_coil(coil)})
    return jsonify({"success": False, "message": "Катушка не найдена"}), 404


@app.route('/api/coils/<int:coil_id>/unarchive', methods=['POST'])
def api_coil_unarchive(coil_id: int):
    """Разархивировать катушку."""
    coil = db.unarchive_coil(coil_id)
    if coil:
        coil = db.get_coil(coil_id)
        return jsonify({"success": True, "coil": serialize_coil(coil)})
    return jsonify({"success": False, "message": "Катушка не найдена"}), 404


@app.route('/api/coils/<int:coil_id>/adjust', methods=['POST'])
def api_coil_adjust(coil_id: int):
    """Ручная корректировка остатка катушки."""
    data = request.get_json(force=True, silent=True) or {}
    new_remains = data.get('remains')
    if new_remains is None:
        return jsonify({"success": False, "message": "Поле remains обязательно"}), 400

    coil = db.adjust_coil_remains(coil_id, new_remains, notes=data.get('notes'))
    if coil:
        coil = db.get_coil(coil_id)
        return jsonify({"success": True, "coil": serialize_coil(coil)})
    return jsonify({"success": False, "message": "Катушка не найдена"}), 404


@app.route('/api/coils/<int:coil_id>/history')
def api_coil_history(coil_id: int):
    """История расхода катушки."""
    history = db.get_spool_history(coil_id=coil_id)
    return jsonify([
        {
            "id": h.id,
            "used_weight": h.used_weight,
            "timestamp": h.timestamp.isoformat() if h.timestamp else None,
            "notes": h.notes,
            "task": {"id": h.task.id, "name": h.task.name} if h.task else None,
        }
        for h in history
    ])


@app.route('/api/materials')
def api_get_materials():
    materials = db.get_materials()
    return jsonify([
        {
            "id": material.id,
            "name": material.name,
            "nozzle_tmp": material.nozzle_tmp,
            "table_tmp": material.table_tmp,
        }
        for material in materials
    ])


# === Vendors API ===

@app.route('/api/vendors', methods=['GET', 'POST'])
def api_vendors():
    """GET: Список производителей. POST: Создать производителя."""
    if request.method == 'GET':
        vendors = db.get_vendors()
        return jsonify([
            {
                "id": v.id,
                "name": v.name,
                "comment": v.comment,
                "empty_spool_weight": v.empty_spool_weight,
            }
            for v in vendors
        ])

    # POST - создание производителя
    data = request.get_json(force=True, silent=True) or {}
    if not data.get('name'):
        return jsonify({"success": False, "message": "Поле name обязательно"}), 400

    # Валидация веса пустой катушки
    empty_weight = data.get('empty_spool_weight')
    if empty_weight is None or float(empty_weight) <= 0:
        return jsonify({"success": False, "message": "Вес пустой катушки обязателен и должен быть больше 0"}), 400

    vendor = db.add_vendor(
        name=data['name'],
        comment=data.get('comment'),
        empty_spool_weight=data.get('empty_spool_weight'),
    )
    return jsonify({
        "success": True,
        "vendor": {
            "id": vendor.id,
            "name": vendor.name,
            "comment": vendor.comment,
            "empty_spool_weight": vendor.empty_spool_weight,
        }
    })


@app.route('/api/vendors/<int:vendor_id>', methods=['GET', 'PUT', 'PATCH', 'DELETE'])
def api_vendor_detail(vendor_id: int):
    """Операции с конкретным производителем."""
    vendor = db.get_vendor(vendor_id)
    if not vendor:
        return jsonify({"success": False, "message": "Производитель не найден"}), 404

    if request.method == 'GET':
        return jsonify({
            "id": vendor.id,
            "name": vendor.name,
            "comment": vendor.comment,
            "empty_spool_weight": vendor.empty_spool_weight,
        })

    if request.method == 'DELETE':
        if db.delete_vendor(vendor_id):
            return jsonify({"success": True})
        return jsonify({"success": False, "message": "Не удалось удалить производителя"}), 400

    # PUT/PATCH - обновление
    data = request.get_json(force=True, silent=True) or {}

    # Валидация веса пустой катушки при обновлении
    if 'empty_spool_weight' in data:
        empty_weight = data.get('empty_spool_weight')
        if empty_weight is None or float(empty_weight) <= 0:
            return jsonify({"success": False, "message": "Вес пустой катушки должен быть больше 0"}), 400

    updated = db.update_vendor(vendor_id, **data)
    if updated:
        return jsonify({
            "success": True,
            "vendor": {
                "id": updated.id,
                "name": updated.name,
                "comment": updated.comment,
                "empty_spool_weight": updated.empty_spool_weight,
            }
        })
    return jsonify({"success": False, "message": "Не удалось обновить производителя"}), 400


# === Filaments API ===

def serialize_filament(filament):
    """Сериализация филамента."""
    return {
        "id": filament.id,
        "vendor_id": filament.vendor_id,
        "vendor_name": filament.vendor.name if filament.vendor else None,
        "name": filament.name,
        "material": filament.material,
        "color_hex": filament.color_hex,
        "diameter": filament.diameter,
        "density": filament.density,
        "weight": filament.weight,
        "empty_spool_weight": filament.empty_spool_weight,
        "description": filament.description,
    }


@app.route('/api/filaments', methods=['GET', 'POST'])
def api_filaments():
    """Список филаментов или создание нового."""
    if request.method == 'GET':
        vendor_id = request.args.get('vendor_id', type=int)
        material = request.args.get('material')
        filaments = db.get_filaments(vendor_id=vendor_id, material=material)
        return jsonify([serialize_filament(f) for f in filaments])

    # POST - создание
    data = request.get_json(force=True, silent=True) or {}
    if not data.get('name'):
        return jsonify({"success": False, "message": "Название обязательно"}), 400

    filament = db.add_filament(
        name=data['name'],
        vendor_id=data.get('vendor_id'),
        material=data.get('material'),
        color_hex=data.get('color_hex'),
        diameter=data.get('diameter'),
        density=data.get('density'),
        weight=data.get('weight'),
        empty_spool_weight=data.get('empty_spool_weight'),
        description=data.get('description'),
    )
    return jsonify({"success": True, "filament": serialize_filament(filament)})


@app.route('/api/filaments/<int:filament_id>', methods=['GET', 'PUT', 'PATCH', 'DELETE'])
def api_filament_detail(filament_id: int):
    """Операции с конкретным филаментом."""
    filament = db.get_filament(filament_id)
    if not filament:
        return jsonify({"success": False, "message": "Филамент не найден"}), 404

    if request.method == 'GET':
        return jsonify(serialize_filament(filament))

    if request.method == 'DELETE':
        if db.delete_filament(filament_id):
            return jsonify({"success": True})
        return jsonify({"success": False, "message": "Не удалось удалить филамент"}), 400

    # PUT/PATCH - обновление
    data = request.get_json(force=True, silent=True) or {}
    updated = db.update_filament(filament_id, **data)
    if updated:
        return jsonify({"success": True, "filament": serialize_filament(updated)})
    return jsonify({"success": False, "message": "Не удалось обновить филамент"}), 400


@app.route('/api/tasks', methods=['GET', 'POST'])
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


@app.route('/api/tasks/<int:task_id>', methods=['GET', 'PUT', 'PATCH', 'DELETE'])
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


@app.route('/api/tasks/<int:task_id>/gcode', methods=['POST', 'GET', 'DELETE'])
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


@app.route('/api/gcode/parse', methods=['POST'])
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
    import tempfile
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


# ---------------------------------------------------------------------------
# Routes - Print Control API
# ---------------------------------------------------------------------------
@app.route('/api/tasks/<int:task_id>/print/start', methods=['POST'])
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

    printer = db.get_printer(task.printer_id)
    if not printer:
        return jsonify({"success": False, "message": "Принтер не найден"}), 404

    if printer.is_virtual:
        return jsonify({"success": False, "message": "Нельзя печатать на виртуальном принтере"}), 400

    # Проверяем состояние принтера
    with printer_state_lock:
        state = printer_states.get(printer.id, build_default_state())

    if state.get("status") == "offline":
        return jsonify({"success": False, "message": "Принтер недоступен"}), 400

    if state.get("status") == "printing":
        return jsonify({"success": False, "message": "Принтер уже печатает"}), 400

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


@app.route('/api/tasks/<int:task_id>/print/pause', methods=['POST'])
def api_task_print_pause(task_id: int):
    """Пауза печати задачи."""
    task = db.get_task(task_id)
    if not task:
        return jsonify({"success": False, "message": "Задача не найдена"}), 404

    if task.status != 'printing':
        return jsonify({"success": False, "message": "Задача не печатается"}), 400

    printer = db.get_printer(task.printer_id)
    if not printer:
        return jsonify({"success": False, "message": "Принтер не найден"}), 404

    success, msg = pause_print_on_printer(printer)
    if not success:
        return jsonify({"success": False, "message": f"Ошибка паузы: {msg}"}), 500

    db.update_task(task_id, status='paused')
    updated_task = db.get_task(task_id)
    return jsonify({"success": True, "task": serialize_task(updated_task)})


@app.route('/api/tasks/<int:task_id>/print/resume', methods=['POST'])
def api_task_print_resume(task_id: int):
    """Возобновление печати задачи."""
    task = db.get_task(task_id)
    if not task:
        return jsonify({"success": False, "message": "Задача не найдена"}), 404

    if task.status != 'paused':
        return jsonify({"success": False, "message": "Задача не на паузе"}), 400

    printer = db.get_printer(task.printer_id)
    if not printer:
        return jsonify({"success": False, "message": "Принтер не найден"}), 404

    success, msg = resume_print_on_printer(printer)
    if not success:
        return jsonify({"success": False, "message": f"Ошибка возобновления: {msg}"}), 500

    db.update_task(task_id, status='printing')
    updated_task = db.get_task(task_id)
    return jsonify({"success": True, "task": serialize_task(updated_task)})


@app.route('/api/tasks/<int:task_id>/print/cancel', methods=['POST'])
def api_task_print_cancel(task_id: int):
    """Отмена печати задачи."""
    task = db.get_task(task_id)
    if not task:
        return jsonify({"success": False, "message": "Задача не найдена"}), 404

    if task.status not in ('printing', 'paused'):
        return jsonify({"success": False, "message": "Задача не печатается и не на паузе"}), 400

    printer = db.get_printer(task.printer_id)
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
# Routes - Maintenance API
# ---------------------------------------------------------------------------
def _serialize_maintenance_type(mt: MaintenanceType) -> dict:
    return {
        "id": mt.id,
        "code": mt.code,
        "name": mt.name,
        "interval_hours": mt.interval_hours,
        "description": mt.description,
    }


def _serialize_maintenance_record(record: MaintenanceRecord) -> dict:
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


@app.route('/api/maintenance/types', methods=['GET'])
def api_maintenance_types():
    """Получить список типов обслуживания."""
    types = db.get_maintenance_types()
    return jsonify([_serialize_maintenance_type(mt) for mt in types])


@app.route('/api/maintenance/types/<int:type_id>', methods=['PUT'])
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


@app.route('/api/maintenance/status', methods=['GET'])
def api_maintenance_status_all():
    """Получить статус обслуживания всех принтеров."""
    printers = db.get_printers(include_inactive=False)
    result = []
    for printer in printers:
        status = db.get_printer_maintenance_status(printer.id)
        if status:
            result.append(status)
    return jsonify(result)


@app.route('/api/maintenance/status/<int:printer_id>', methods=['GET'])
def api_maintenance_status(printer_id: int):
    """Получить статус обслуживания конкретного принтера."""
    status = db.get_printer_maintenance_status(printer_id)
    if not status:
        return jsonify({"success": False, "message": "Принтер не найден"}), 404
    return jsonify(status)


@app.route('/api/maintenance/upcoming', methods=['GET'])
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


@app.route('/api/maintenance/records', methods=['GET', 'POST'])
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
        app.logger.error("Ошибка при добавлении записи обслуживания: %s", exc)
        return jsonify({"success": False, "message": "Внутренняя ошибка сервера"}), 500


@app.route('/api/maintenance/records/<int:record_id>', methods=['DELETE'])
def api_maintenance_record_delete(record_id: int):
    """Удалить запись обслуживания."""
    deleted = db.delete_maintenance_record(record_id)
    if not deleted:
        return jsonify({"success": False, "message": "Запись не найдена"}), 404
    return jsonify({"success": True})


@app.route('/api/maintenance/force/<int:printer_id>', methods=['POST'])
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
        app.logger.error("Ошибка при принудительном требовании обслуживания: %s", exc)
        return jsonify({"success": False, "message": str(exc)}), 500


# ---------------------------------------------------------------------------
# App bootstrap
# ---------------------------------------------------------------------------
def start_background_threads():
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


if not app.config.get("BACKGROUND_THREADS_STARTED"):
    start_background_threads()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
