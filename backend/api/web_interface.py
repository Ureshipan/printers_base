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

# Add the project root to the Python path
PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
sys.path.append(PROJECT_ROOT)

from backend.db.data_model import DBModel, Coil, Printer, Project, Task  # noqa: E402


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
    params = enrich_params_with_printer(printer, [
        ('print_stats', ''),
        ('extruder', ''),
        ('heater_bed', ''),
        ('toolhead', ''),
        ('virtual_sdcard', ''),
    ])
    try:
        response = http.get(f"{base_url}/printer/objects/query", params=params, timeout=5)
        response.raise_for_status()
        payload = response.json().get("result", {}).get("status", {})
    except requests.RequestException as exc:
        app.logger.debug("Не удалось обновить состояние принтера %s: %s", printer.id, exc)
        state["status"] = "offline"
        return state

    try:
        print_stats = payload.get("print_stats", {})
        extruder = payload.get("extruder", {})
        heater_bed = payload.get("heater_bed", {})
        toolhead = payload.get("toolhead", {})
        virtual_sdcard = payload.get("virtual_sdcard", {})

        state["status"] = print_stats.get("state", "unknown")
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

        time.sleep(PRINTER_STATE_INTERVAL)


def get_printer_or_default(printer_id: Optional[int]) -> Optional[Printer]:
    if printer_id:
        printer = db.get_printer_by_id(printer_id)
        if printer and printer.is_active:
            return printer
    printers = db.get_printers(include_inactive=False)
    return printers[0] if printers else None


def estimate_print_parameters(file_path: str) -> Tuple[float, float]:
    """
    Stub function that pretends to parse a G-code file and returns
    estimated filament usage (grams) and print time (minutes).
    """
    try:
        size_kb = os.path.getsize(file_path) / 1024
    except OSError:
        size_kb = 0

    estimated_filament = round(5.0 + size_kb * 0.05, 2)
    estimated_time = round(30.0 + size_kb * 0.2, 1)
    return estimated_filament, estimated_time


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
        },
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


@app.route('/api/printers/<int:printer_id>', methods=['DELETE'])
def api_delete_printer(printer_id: int):
    deleted = db.delete_printer(printer_id)
    if deleted:
        with printer_state_lock:
            printer_states.pop(printer_id, None)
        return jsonify({"success": True})
    return jsonify({"success": False, "message": "Принтер не найден"}), 404


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
        response = moonraker_post(printer, "printer/gcode/script", {"script": command})
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
        response = moonraker_post(printer, "printer/gcode/script", {"script": command})
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


@app.route('/api/coils')
def api_get_coils():
    coils = db.get_coils()
    return jsonify([
        {
            "id": coil.id,
            "name": coil.name,
            "material": coil.material.name if coil.material else None,
            "material_id": coil.material.id if coil.material else None,
            "remains": coil.remains,
        }
        for coil in coils
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
        updated_task = db.get_task(task_id)
        return jsonify({"success": True, "task": serialize_task(updated_task)})

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

    estimated_filament, estimated_time = estimate_print_parameters(stored_path)
    updated_task = db.update_task(
        task.id,
        model_gcode=stored_name,
        gcode_original_name=file.filename,
        gcode_uploaded_at=datetime.now(timezone.utc),
        estimated_filament=estimated_filament,
        estimated_time_minutes=estimated_time,
        material_amount=estimated_filament,
    )
    if not updated_task:
        return jsonify({"success": False, "message": "Не удалось сохранить данные файла"}), 500
    updated_task = db.get_task(task.id)
    return jsonify({"success": True, "task": serialize_task(updated_task)})


# ---------------------------------------------------------------------------
# App bootstrap
# ---------------------------------------------------------------------------
def start_background_threads():
    if app.config.get("BACKGROUND_THREADS_STARTED"):
        return
    app.config["BACKGROUND_THREADS_STARTED"] = True
    synchronize_printers_with_db()
    update_thread = threading.Thread(target=update_printer_states_loop, daemon=True)
    update_thread.start()


if not app.config.get("BACKGROUND_THREADS_STARTED"):
    start_background_threads()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
