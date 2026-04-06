"""Общее состояние приложения PrinterBase.

Глобальные переменные, конфигурация, shared state —
всё, что используется несколькими модулями.
"""
import os
import sys
import threading
import logging
from typing import Dict

import requests
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Корень проекта
PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
sys.path.append(PROJECT_ROOT)

if os.path.exists(os.path.join(PROJECT_ROOT, ".env")):
    load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

from backend.db.data_model import DBModel  # noqa: E402
from backend.services.health import HealthRegistry  # noqa: E402

# ---------------------------------------------------------------------------
# Конфигурация
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

# ---------------------------------------------------------------------------
# Shared state (синглтоны для всего приложения)
# ---------------------------------------------------------------------------
db = DBModel(db_path=DATABASE_PATH)
http = requests.Session()

# Кеш состояний принтеров: printer_id -> state dict
printer_states: Dict[int, Dict] = {}
printer_state_lock = threading.Lock()

# Circuit breaker реестр
health_registry = HealthRegistry()

# Per-printer locks для защиты от одновременного запуска печати
_printer_action_locks: Dict[int, threading.Lock] = {}
_printer_action_locks_lock = threading.Lock()  # Lock для создания per-printer locks


def _get_printer_lock(printer_id: int) -> threading.Lock:
    """Получить lock для конкретного принтера (thread-safe)."""
    with _printer_action_locks_lock:
        if printer_id not in _printer_action_locks:
            _printer_action_locks[printer_id] = threading.Lock()
        return _printer_action_locks[printer_id]


# Маппинг статусов Moonraker -> приложение
STATE_MAP = {
    "printing": "work",
    "paused": "idle",
    "standby": "idle",
    "complete": "awaiting_removal",  # Требует подтверждения уборки детали
    "error": "error",
    "offline": "offline",
    "ready": "idle",
}
