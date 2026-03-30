"""Тесты интеграции: retry, circuit breaker, параллельный опрос в web_interface."""
import threading
import time
from unittest.mock import MagicMock, patch

import pytest
import requests

from backend.services.health import HealthRegistry, PrinterHealthState


class TestMoonrakerRequestRetry:
    """Retry через tenacity для HTTP-запросов к Moonraker."""

    def test_retry_on_connection_error(self, monkeypatch):
        """_perform_moonraker_request повторяет запрос при ConnectionError."""
        from backend.api import web_interface

        call_count = 0

        def mock_get(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise requests.ConnectionError("Connection refused")
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = {"result": "ok"}
            return resp

        monkeypatch.setattr(web_interface.http, "get", mock_get)

        result = web_interface._perform_moonraker_request(
            "http://localhost:7125", "server/info", "GET", timeout=1
        )
        assert result.status_code == 200
        assert call_count == 3  # 2 неудачных + 1 успешный

    def test_retry_on_timeout(self, monkeypatch):
        """_perform_moonraker_request повторяет запрос при Timeout."""
        from backend.api import web_interface

        # Используем отдельный счётчик для отслеживания нашего вызова
        attempts = []

        original_post = web_interface.http.post

        def mock_post(*args, **kwargs):
            url = args[0] if args else kwargs.get("url", "")
            # Отслеживаем только наш тестовый вызов
            if "localhost:7125" in str(url):
                attempts.append(1)
                if len(attempts) < 2:
                    raise requests.Timeout("Request timed out")
                resp = MagicMock()
                resp.status_code = 200
                resp.json.return_value = {"result": "ok"}
                return resp
            # Остальные вызовы (фоновый поток) — пусть падают тихо
            raise requests.ConnectionError("test isolation")

        monkeypatch.setattr(web_interface.http, "post", mock_post)

        result = web_interface._perform_moonraker_request(
            "http://localhost:7125", "printer/info", "POST",
            payload={"test": True}, timeout=1
        )
        assert result.status_code == 200
        assert len(attempts) == 2

    def test_retry_exhausted_raises(self, monkeypatch):
        """При исчерпании retry — пробрасывает исключение."""
        from backend.api import web_interface

        def mock_get(*args, **kwargs):
            raise requests.ConnectionError("Connection refused")

        monkeypatch.setattr(web_interface.http, "get", mock_get)

        with pytest.raises(requests.ConnectionError):
            web_interface._perform_moonraker_request(
                "http://localhost:7125", "server/info", "GET", timeout=1
            )


class TestHealthEndpoint:
    """Endpoint /api/health с информацией о circuit breaker."""

    def test_health_endpoint_returns_ok(self, client, monkeypatch):
        """GET /api/health возвращает status=ok."""
        from backend.api import web_interface

        # Подставляем пустой реестр
        monkeypatch.setattr(web_interface, "health_registry", HealthRegistry())

        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"
        assert "health" in data
        assert "printers_total" in data

    def test_health_endpoint_shows_circuit_state(self, client, monkeypatch):
        """GET /api/health показывает состояние circuit breaker для принтеров."""
        from backend.api import web_interface

        registry = HealthRegistry()
        # Создаём состояние принтера с открытым circuit
        hs = registry.get(1)
        for _ in range(5):
            hs.record_failure()

        monkeypatch.setattr(web_interface, "health_registry", registry)
        monkeypatch.setattr(web_interface, "printer_states", {1: {"status": "offline"}})

        resp = client.get("/api/health")
        data = resp.get_json()
        assert data["status"] == "ok"
        health = data["health"]
        assert "1" in health or 1 in health
        printer_health = health.get("1") or health.get(1)
        assert printer_health["circuit_open"] is True
        assert printer_health["consecutive_failures"] == 5


class TestParallelPolling:
    """Параллельный опрос принтеров с circuit breaker."""

    def test_executor_exists(self):
        """ThreadPoolExecutor создан как глобальная переменная."""
        from backend.api import web_interface
        assert hasattr(web_interface, "_executor")
        # Проверяем что это ThreadPoolExecutor
        from concurrent.futures import ThreadPoolExecutor
        assert isinstance(web_interface._executor, ThreadPoolExecutor)

    def test_health_registry_exists(self):
        """HealthRegistry создан как глобальная переменная."""
        from backend.api import web_interface
        assert hasattr(web_interface, "health_registry")
        assert isinstance(web_interface.health_registry, HealthRegistry)
