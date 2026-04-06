"""HTTP-клиент для взаимодействия с Moonraker API.

Содержит все функции для HTTP-запросов к принтерам через Moonraker:
retry, fallback, опрос состояния, управление печатью.
"""
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from backend.api.state import (
    db,
    http,
    DEFAULT_PRINTER_PORT,
    DEFAULT_FALLBACK_HOST,
    DISCOVERY_ENABLED,
)
from backend.db.data_model import Printer

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# URL / параметры
# ---------------------------------------------------------------------------
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


def enrich_params_with_printer(
    printer: Printer, params: Optional[List[Tuple[str, str]]] = None
) -> List[Tuple[str, str]]:
    params_list = list(params or [])
    if printer.moonraker_printer:
        params_list.append(('printer', printer.moonraker_printer))
    return params_list


# ---------------------------------------------------------------------------
# Базовые HTTP-запросы с retry и fallback
# ---------------------------------------------------------------------------
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout)),
    reraise=True,
)
def _perform_moonraker_request(
    base_url: str,
    endpoint: str,
    method: str,
    params: Optional[List[Tuple[str, str]]] = None,
    payload: Optional[dict] = None,
    timeout: int = 5,
):
    """HTTP запрос к Moonraker с retry (tenacity)."""
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
        logger.warning(
            "Moonraker %s %s failed for %s:%s (%s)",
            method, endpoint, printer.moonraker_host, printer.moonraker_port, exc,
        )
        # Try fallback host if configured
        if printer.moonraker_host and printer.moonraker_host != DEFAULT_FALLBACK_HOST:
            fallback_base_url = f"http://{DEFAULT_FALLBACK_HOST}:{DEFAULT_PRINTER_PORT}"
            try:
                fallback_response = _perform_moonraker_request(
                    fallback_base_url, endpoint, method, params_list, payload, timeout
                )
                fallback_response.raise_for_status()
                logger.info(
                    "Использован резервный Moonraker-хост %s для принтера %s",
                    DEFAULT_FALLBACK_HOST, printer.id,
                )
                return fallback_response
            except requests.RequestException as fallback_exc:
                logger.warning(
                    "Fallback Moonraker %s %s failed for %s:%s (%s)",
                    method, endpoint, DEFAULT_FALLBACK_HOST,
                    DEFAULT_PRINTER_PORT, fallback_exc,
                )
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


# ---------------------------------------------------------------------------
# Обнаружение и регистрация принтеров
# ---------------------------------------------------------------------------
def fetch_printers_for_host(host: str, port: int) -> List[Dict[str, Optional[str]]]:
    """Получить список принтеров для хоста Moonraker.

    Каждый экземпляр Moonraker управляет одним принтером (docs/external_api/printer.md).
    Используем GET /printer/info для получения hostname как display_name.
    """
    base_url = f"http://{host}:{port}"
    display_name = None
    try:
        response = http.get(f"{base_url}/printer/info", timeout=5)
        if response.status_code == 200:
            result = response.json().get("result", {})
            display_name = result.get("hostname")
    except requests.RequestException:
        pass
    return [{"moonraker_printer": None, "display_name": display_name}]


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
        logger.warning("Не удалось выполнить поиск принтеров: %s", exc)

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


# ---------------------------------------------------------------------------
# Опрос состояния принтера
# ---------------------------------------------------------------------------
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
        # Данные для оффлайн-принтеров (ручной ввод)
        state["progress"] = getattr(printer, "manual_progress", 0) or 0
        state["filename"] = getattr(printer, "manual_filename", None)
        manual_start = getattr(printer, "manual_print_start", None)
        state["manual_print_start"] = manual_start.isoformat() if manual_start else None
        state["is_offline"] = True
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
        logger.debug("Не удалось обновить состояние принтера %s: %s", printer.id, exc)
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
            state_message = webhooks.get("state_message", "")
            if klipper_state == "shutdown":
                state["status"] = "offline"
            elif klipper_state == "error" and "Unable to connect" in state_message:
                # MCU недоступен — принтер физически выключен
                state["status"] = "offline"
            elif klipper_state == "startup":
                # Klipper загружается
                state["status"] = "offline"
            else:
                state["status"] = "error"
            state["status_message"] = state_message
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
        logger.warning("Ошибка обработки состояния принтера %s: %s", printer.id, exc)

    return state


# ---------------------------------------------------------------------------
# Управление печатью через Moonraker
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
        logger.error("Ошибка загрузки G-code на принтер %s: %s", printer.id, exc)
        return False, str(exc)
    except Exception as exc:
        logger.error("Ошибка при загрузке файла: %s", exc)
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
        logger.error("Ошибка запуска печати на принтере %s: %s", printer.id, exc)
        return False, str(exc)


def pause_print_on_printer(printer: Printer) -> Tuple[bool, str]:
    """Пауза печати на принтере."""
    base_url = build_base_url(printer)
    try:
        response = http.post(f"{base_url}/printer/print/pause", timeout=10)
        response.raise_for_status()
        return True, "ok"
    except requests.RequestException as exc:
        logger.error("Ошибка паузы печати на принтере %s: %s", printer.id, exc)
        return False, str(exc)


def resume_print_on_printer(printer: Printer) -> Tuple[bool, str]:
    """Возобновление печати на принтере."""
    base_url = build_base_url(printer)
    try:
        response = http.post(f"{base_url}/printer/print/resume", timeout=10)
        response.raise_for_status()
        return True, "ok"
    except requests.RequestException as exc:
        logger.error("Ошибка возобновления печати на принтере %s: %s", printer.id, exc)
        return False, str(exc)


def cancel_print_on_printer(printer: Printer) -> Tuple[bool, str]:
    """Отмена печати на принтере."""
    base_url = build_base_url(printer)
    try:
        # Сначала очищаем состояние паузы (если есть) чтобы избежать
        # ошибки "Unknown g-code state: PAUSE_state" при отмене из паузы
        try:
            http.post(
                f"{base_url}/printer/gcode/script",
                json={"script": "CLEAR_PAUSE"},
                timeout=5
            )
        except requests.RequestException:
            pass  # Игнорируем ошибку - команда может не поддерживаться

        response = http.post(f"{base_url}/printer/print/cancel", timeout=10)
        response.raise_for_status()
        return True, "ok"
    except requests.RequestException as exc:
        logger.error("Ошибка отмены печати на принтере %s: %s", printer.id, exc)
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
        logger.warning("Ошибка получения статуса печати принтера %s: %s", printer.id, exc)
        return None
