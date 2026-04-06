"""Тесты для backend/services/health.py — Circuit Breaker для принтеров."""
import time

import pytest

from backend.services.health import HealthRegistry, PrinterHealthState


class TestPrinterHealthStateInitial:
    """Начальное состояние PrinterHealthState."""

    def test_initial_state(self):
        """Новый объект: circuit closed, 0 failures, should_skip=False."""
        state = PrinterHealthState()
        assert state.consecutive_failures == 0
        assert state.circuit_open is False
        assert state.should_skip() is False
        assert state.state == "closed"


class TestRecordFailure:
    """Запись ошибок и открытие circuit."""

    def test_failures_below_threshold(self):
        """4 ошибки — circuit остаётся closed, опрос не пропускается."""
        state = PrinterHealthState()
        for _ in range(4):
            state.record_failure()
        assert state.consecutive_failures == 4
        assert state.circuit_open is False
        assert state.should_skip() is False

    def test_circuit_opens_after_max_failures(self):
        """5 ошибок — circuit открывается, опрос пропускается."""
        state = PrinterHealthState()
        for _ in range(5):
            state.record_failure()
        assert state.consecutive_failures == 5
        assert state.circuit_open is True
        assert state.should_skip() is True
        assert state.state == "open"

    def test_exponential_backoff(self, monkeypatch):
        """Backoff растёт экспоненциально: 5 fail→2s, 6→4s, 7→8s."""
        state = PrinterHealthState()
        fake_time = 100.0

        def mock_monotonic():
            return fake_time

        monkeypatch.setattr(time, "monotonic", mock_monotonic)

        # 5 ошибок → backoff = 2 * 2^0 = 2.0
        for _ in range(5):
            state.record_failure()
        assert state.backoff_until == pytest.approx(102.0)

        # 6 ошибок → backoff = 2 * 2^1 = 4.0
        state.record_failure()
        assert state.backoff_until == pytest.approx(104.0)

        # 7 ошибок → backoff = 2 * 2^2 = 8.0
        state.record_failure()
        assert state.backoff_until == pytest.approx(108.0)

    def test_max_backoff_cap(self, monkeypatch):
        """Backoff не превышает MAX_BACKOFF (60 сек)."""
        state = PrinterHealthState()
        fake_time = 100.0

        def mock_monotonic():
            return fake_time

        monkeypatch.setattr(time, "monotonic", mock_monotonic)

        # 20 ошибок — backoff = 2 * 2^15 = 65536, но cap = 60
        for _ in range(20):
            state.record_failure()
        assert state.backoff_until == pytest.approx(160.0)


class TestRecordSuccess:
    """Закрытие circuit при успехе."""

    def test_record_success_closes_circuit(self):
        """После открытия circuit — record_success закрывает его."""
        state = PrinterHealthState()
        for _ in range(5):
            state.record_failure()
        assert state.circuit_open is True

        state.record_success()
        assert state.consecutive_failures == 0
        assert state.circuit_open is False
        assert state.should_skip() is False
        assert state.state == "closed"


class TestHalfOpen:
    """Переход в half-open после истечения backoff."""

    def test_half_open_after_backoff(self, monkeypatch):
        """После backoff — should_skip=False, state='half-open'."""
        state = PrinterHealthState()
        fake_time = 100.0

        def mock_monotonic():
            return fake_time

        monkeypatch.setattr(time, "monotonic", mock_monotonic)

        for _ in range(5):
            state.record_failure()
        # backoff_until = 102.0, сейчас 100.0 → skip
        assert state.should_skip() is True
        assert state.state == "open"

        # Перематываем время за пределы backoff
        fake_time = 103.0
        assert state.should_skip() is False
        assert state.state == "half-open"


class TestHealthRegistry:
    """Реестр состояний здоровья принтеров."""

    def test_get_creates_state(self):
        """get() создаёт PrinterHealthState при первом обращении."""
        registry = HealthRegistry()
        state = registry.get(1)
        assert isinstance(state, PrinterHealthState)
        assert state.consecutive_failures == 0
        # Повторный вызов возвращает тот же объект
        assert registry.get(1) is state

    def test_remove_deletes_state(self):
        """remove() удаляет состояние принтера."""
        registry = HealthRegistry()
        registry.get(42)
        assert 42 in registry.get_all_states()
        registry.remove(42)
        assert 42 not in registry.get_all_states()

    def test_remove_nonexistent_no_error(self):
        """remove() не падает при удалении несуществующего принтера."""
        registry = HealthRegistry()
        registry.remove(999)  # Не должно бросать исключение
