"""Circuit Breaker для мониторинга состояния принтеров.

При недоступности принтера — пропускаем опрос с экспоненциальным backoff,
чтобы не тратить время на timeout'ы в фоновом потоке.
"""
import time
import logging
from dataclasses import dataclass
from typing import Dict

logger = logging.getLogger(__name__)


@dataclass
class PrinterHealthState:
    """Состояние здоровья конкретного принтера.

    Circuit Breaker с тремя состояниями:
    - CLOSED (нормальная работа, опрос выполняется)
    - OPEN (принтер недоступен, опрос пропускается)
    - HALF-OPEN (backoff истёк, пробуем одну попытку)
    """

    consecutive_failures: int = 0
    last_failure_time: float = 0.0
    circuit_open: bool = False
    backoff_until: float = 0.0

    # Порог последовательных ошибок для открытия circuit
    MAX_FAILURES: int = 5
    # Базовое время backoff (секунды)
    BASE_BACKOFF: float = 2.0
    # Максимальное время backoff (секунды)
    MAX_BACKOFF: float = 60.0

    def record_failure(self) -> None:
        """Записать неудачную попытку. Открыть circuit при достижении порога."""
        self.consecutive_failures += 1
        self.last_failure_time = time.monotonic()
        if self.consecutive_failures >= self.MAX_FAILURES:
            self.circuit_open = True
            # Экспоненциальный backoff: 2, 4, 8, 16... до MAX_BACKOFF
            backoff = min(
                self.BASE_BACKOFF * (2 ** (self.consecutive_failures - self.MAX_FAILURES)),
                self.MAX_BACKOFF,
            )
            self.backoff_until = time.monotonic() + backoff
            logger.warning(
                "Circuit OPEN: %d последовательных ошибок, backoff %.1f сек",
                self.consecutive_failures,
                backoff,
            )

    def record_success(self) -> None:
        """Записать успешную попытку. Закрыть circuit."""
        if self.circuit_open:
            logger.info("Circuit CLOSED: принтер снова доступен")
        self.consecutive_failures = 0
        self.circuit_open = False
        self.backoff_until = 0.0

    def should_skip(self) -> bool:
        """Проверить, нужно ли пропустить опрос этого принтера.

        Returns:
            True — пропустить (circuit open, backoff не истёк).
            False — опрашивать (closed или half-open).
        """
        if not self.circuit_open:
            return False
        # Backoff истёк — переходим в half-open, пробуем одну попытку
        if time.monotonic() >= self.backoff_until:
            return False
        return True

    @property
    def state(self) -> str:
        """Текущее состояние circuit breaker."""
        if not self.circuit_open:
            return "closed"
        if time.monotonic() >= self.backoff_until:
            return "half-open"
        return "open"


class HealthRegistry:
    """Реестр состояний здоровья всех принтеров.

    Один экземпляр на приложение. Хранит PrinterHealthState
    для каждого принтера по его id.
    """

    def __init__(self) -> None:
        self._states: Dict[int, PrinterHealthState] = {}

    def get(self, printer_id: int) -> PrinterHealthState:
        """Получить или создать состояние для принтера."""
        if printer_id not in self._states:
            self._states[printer_id] = PrinterHealthState()
        return self._states[printer_id]

    def remove(self, printer_id: int) -> None:
        """Удалить состояние принтера (при удалении из БД)."""
        self._states.pop(printer_id, None)

    def get_all_states(self) -> Dict[int, PrinterHealthState]:
        """Получить все состояния (для API/мониторинга)."""
        return dict(self._states)
