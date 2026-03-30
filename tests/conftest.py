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


@pytest.fixture
def client(db, monkeypatch):
    """Flask test client с тестовой БД."""
    # Импортируем app после настройки sys.path
    from backend.api import web_interface

    # Подставляем тестовую БД вместо продакшен
    monkeypatch.setattr(web_interface, "db", db)

    web_interface.app.config["TESTING"] = True
    with web_interface.app.test_client() as test_client:
        yield test_client
