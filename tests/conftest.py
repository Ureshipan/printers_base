"""Общие фикстуры для тестов PrinterBase."""
import os
import sys

import pytest

# Корень проекта — для импортов backend.*
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.db.data_model import DBModel  # noqa: E402


@pytest.fixture
def db(tmp_path):
    """Тестовая SQLite БД в tmpdir — не трогает продакшен."""
    return DBModel(db_path=str(tmp_path / "test.db"))


# Все модули, которые импортируют db/printer_states/health_registry напрямую.
# Нужно патчить каждый, т.к. `from X import Y` создаёт локальную привязку.
_DB_MODULES = [
    "backend.api.web_interface",
    "backend.api.state",
    "backend.api.helpers",
    "backend.services.moonraker_client",
    "backend.services.background",
    "backend.api.blueprints.printers",
    "backend.api.blueprints.tasks",
    "backend.api.blueprints.print_control",
    "backend.api.blueprints.projects",
    "backend.api.blueprints.coils",
    "backend.api.blueprints.maintenance",
    "backend.api.blueprints.control",
]


@pytest.fixture
def client(db, monkeypatch):
    """Flask test client с тестовой БД."""
    import importlib

    # Подставляем тестовую БД во ВСЕ модули
    for mod_name in _DB_MODULES:
        mod = importlib.import_module(mod_name)
        if hasattr(mod, "db"):
            monkeypatch.setattr(mod, "db", db)

    from backend.api import web_interface

    web_interface.app.config["TESTING"] = True
    with web_interface.app.test_client() as test_client:
        yield test_client
