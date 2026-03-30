"""Тесты для backend/db/data_model.py — ORM, WAL mode, PRAGMA, конкурентный доступ."""
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest

from backend.db.data_model import DBModel


class TestSQLitePragmas:
    """Проверка PRAGMA-настроек SQLite (WAL, foreign_keys)."""

    def test_wal_mode_enabled(self, db: DBModel):
        """WAL mode должен быть включён для конкурентного доступа."""
        session = db.get_session()
        try:
            result = session.execute(
                __import__("sqlalchemy").text("PRAGMA journal_mode")
            ).fetchone()
            assert result[0] == "wal"
        finally:
            session.close()

    def test_foreign_keys_enabled(self, db: DBModel):
        """PRAGMA foreign_keys должен быть ON для целостности данных."""
        session = db.get_session()
        try:
            result = session.execute(
                __import__("sqlalchemy").text("PRAGMA foreign_keys")
            ).fetchone()
            assert result[0] == 1
        finally:
            session.close()


class TestPrinterCRUD:
    """Базовые операции с принтерами."""

    def test_create_printer(self, db: DBModel):
        """Создание принтера — id не None, имя совпадает."""
        printer = db.add_printer("TestPrinter-1")
        assert printer.id is not None
        assert printer.name == "TestPrinter-1"

    def test_get_printer_by_id(self, db: DBModel):
        """Получение принтера по id — данные корректны."""
        created = db.add_printer("Printer-Get", moonraker_host="192.168.1.10")
        fetched = db.get_printer_by_id(created.id)
        assert fetched is not None
        assert fetched.name == "Printer-Get"
        assert fetched.moonraker_host == "192.168.1.10"

    def test_get_printer_not_found(self, db: DBModel):
        """Получение несуществующего принтера — None."""
        fetched = db.get_printer_by_id(99999)
        assert fetched is None


class TestProjectCRUD:
    """Базовые операции с проектами."""

    def test_create_project(self, db: DBModel):
        """Создание проекта — id, имя, цвет по умолчанию."""
        project = db.add_project("Корпуса v2", "Партия корпусов для клиента")
        assert project.id is not None
        assert project.name == "Корпуса v2"
        assert project.color == "#888888"


class TestTaskCRUD:
    """Базовые операции с задачами."""

    def test_create_task_with_printer(self, db: DBModel):
        """Создание задачи с привязкой к принтеру."""
        printer = db.add_printer("TaskPrinter")
        task = db.add_task(name="Печать детали A", printer_id=printer.id)
        assert task.id is not None
        assert task.name == "Печать детали A"
        assert task.printer_id == printer.id
        assert task.status == "pending"


class TestVendorFilament:
    """Операции с производителями и филаментами."""

    def test_add_vendor_and_filament(self, db: DBModel):
        """Создание производителя и филамента — связь через vendor_id."""
        vendor = db.add_vendor("BestFilament", comment="Тестовый поставщик")
        assert vendor.id is not None
        assert vendor.name == "BestFilament"

        filament = db.add_filament(
            name="PLA+ Premium",
            vendor_id=vendor.id,
            material="PLA",
            color_hex="#FF0000",
        )
        assert filament.id is not None
        assert filament.vendor_id == vendor.id
        assert filament.material == "PLA"


class TestConcurrentAccess:
    """Конкурентный доступ — WAL mode предотвращает 'database is locked'."""

    def test_concurrent_read_write(self, db: DBModel):
        """Чтение и запись из разных потоков не вызывает 'database is locked'."""
        errors: list = []
        barrier = threading.Barrier(2, timeout=10)

        def writer():
            try:
                barrier.wait()
                for i in range(20):
                    db.add_printer(f"Writer-{i}")
            except Exception as exc:
                errors.append(f"writer: {exc}")

        def reader():
            try:
                barrier.wait()
                for _ in range(20):
                    db.get_printers()
            except Exception as exc:
                errors.append(f"reader: {exc}")

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(writer), pool.submit(reader)]
            for f in as_completed(futures):
                f.result()  # Пробросит исключение если поток упал

        assert errors == [], f"Ошибки конкурентного доступа: {errors}"
        # Проверяем что все 20 принтеров записались
        printers = db.get_printers()
        assert len(printers) >= 20


class TestCoilCRUD:
    """CRUD операции с катушками."""

    def _create_coil_with_deps(self, db: DBModel, remains: float = 800.0) -> "Coil":
        """Вспомогательный метод: создать vendor + filament + coil."""
        vendor = db.add_vendor("TestVendor")
        filament = db.add_filament(
            name="PLA Test", vendor_id=vendor.id, material="PLA", color_hex="#00FF00",
        )
        return db.add_coil(
            name="Катушка-1", remains=remains,
            filament_id=filament.id, initial_weight=1000.0,
        )

    def test_add_coil(self, db: DBModel):
        """Создание катушки — id, имя, остаток, связь с филаментом."""
        coil = self._create_coil_with_deps(db)
        assert coil.id is not None
        assert coil.name == "Катушка-1"
        assert coil.remains == 800.0
        assert coil.filament_id is not None

    def test_adjust_remains(self, db: DBModel):
        """Ручная корректировка остатка — обновляет remains."""
        coil = self._create_coil_with_deps(db, remains=800.0)
        updated = db.adjust_coil_remains(coil.id, new_remains=600.0, notes="Тест")
        assert updated is not None
        assert updated.remains == 600.0

    def test_archive_coil(self, db: DBModel):
        """Архивация катушки — archived == True."""
        coil = self._create_coil_with_deps(db)
        archived = db.archive_coil(coil.id)
        assert archived is not None
        assert archived.archived is True

    def test_get_coils_with_archived_filter(self, db: DBModel):
        """Фильтрация катушек: активные vs. архивные."""
        coil1 = self._create_coil_with_deps(db)
        coil2 = self._create_coil_with_deps(db)
        db.archive_coil(coil2.id)

        # По умолчанию — только активные
        active = db.get_coils()
        assert len(active) == 1
        assert active[0].id == coil1.id

        # С include_archived — все
        all_coils = db.get_coils(include_archived=True)
        assert len(all_coils) == 2


class TestMaintenanceCRUD:
    """CRUD операции с обслуживанием."""

    def test_init_maintenance_types(self, db: DBModel):
        """Инициализация типов ТО — создаёт 3 типа по умолчанию."""
        db.init_maintenance_types()
        types = db.get_maintenance_types()
        assert len(types) == 3
        codes = {t.code for t in types}
        assert codes == {"nozzle", "rollers", "extruder"}

    def test_init_maintenance_types_idempotent(self, db: DBModel):
        """Повторная инициализация — не дублирует записи."""
        db.init_maintenance_types()
        db.init_maintenance_types()
        types = db.get_maintenance_types()
        assert len(types) == 3

    def test_add_maintenance_record(self, db: DBModel):
        """Добавление записи о ТО — связь с принтером и типом."""
        db.init_maintenance_types()
        printer = db.add_printer("MaintenancePrinter")
        types = db.get_maintenance_types()
        nozzle_type = next(t for t in types if t.code == "nozzle")

        record = db.add_maintenance_record(
            printer_id=printer.id,
            maintenance_type_id=nozzle_type.id,
            notes="Замена сопла 0.4",
        )
        assert record.id is not None
        assert record.printer_id == printer.id
        assert record.maintenance_type_id == nozzle_type.id
        assert record.notes == "Замена сопла 0.4"

    def test_get_maintenance_status(self, db: DBModel):
        """Статус обслуживания — needs_maintenance при превышении интервала."""
        db.init_maintenance_types()
        printer = db.add_printer("StatusPrinter")
        # Устанавливаем наработку выше интервала сопла (200ч)
        db.update_printer(printer.id, print_hours=250.0)

        status = db.get_printer_maintenance_status(printer.id)
        assert status["printer_id"] == printer.id
        assert status["needs_maintenance"] is True
        # Должен быть overdue для nozzle (250 > 200)
        nozzle_status = next(
            s for s in status["maintenance_status"] if s["type_code"] == "nozzle"
        )
        assert nozzle_status["is_overdue"] is True


class TestSpoolHistory:
    """История расхода материала."""

    def _create_coil(self, db: DBModel) -> "Coil":
        """Вспомогательный метод: создать катушку."""
        vendor = db.add_vendor("HistVendor")
        filament = db.add_filament(
            name="PETG", vendor_id=vendor.id, material="PETG", color_hex="#0000FF",
        )
        return db.add_coil(
            name="Катушка-Hist", remains=500.0,
            filament_id=filament.id, initial_weight=1000.0,
        )

    def test_add_spool_history(self, db: DBModel):
        """Создание записи расхода — id, вес, coil_id."""
        coil = self._create_coil(db)
        history = db.add_spool_history(
            coil_id=coil.id, used_weight=50.0, notes="Печать детали",
        )
        assert history.id is not None
        assert history.coil_id == coil.id
        assert history.used_weight == 50.0

    def test_adjust_remains_creates_history(self, db: DBModel):
        """Ручная корректировка создаёт запись в истории."""
        coil = self._create_coil(db)
        db.adjust_coil_remains(coil.id, new_remains=400.0, notes="Корректировка")

        history = db.get_spool_history(coil_id=coil.id)
        assert len(history) == 1
        assert history[0].used_weight == 100.0  # 500 - 400
        assert history[0].notes == "Корректировка"

    def test_get_spool_history_empty(self, db: DBModel):
        """Пустая история — пустой список."""
        coil = self._create_coil(db)
        history = db.get_spool_history(coil_id=coil.id)
        assert history == []


class TestConnectionPool:
    """Проверка настроек пула соединений для многопоточной нагрузки."""

    def test_pool_handles_concurrent_connections(self, db: DBModel):
        """Пул должен выдержать 15+ одновременных запросов без TimeoutError."""
        from concurrent.futures import ThreadPoolExecutor, as_completed

        errors: list = []

        def db_operation(i: int):
            try:
                db.add_printer(f"PoolTest-{i}")
                db.get_printers()
            except Exception as exc:
                errors.append(str(exc))

        # 15 одновременных потоков — имитация gunicorn + background threads
        with ThreadPoolExecutor(max_workers=15) as pool:
            futures = [pool.submit(db_operation, i) for i in range(15)]
            for f in as_completed(futures):
                f.result()

        assert errors == [], f"Pool overflow errors: {errors}"
        printers = db.get_printers()
        assert len(printers) == 15

    def test_pool_size_allows_overflow(self, db: DBModel):
        """max_overflow > 0 — пул может расширяться сверх pool_size."""
        pool = db.engine.pool
        assert pool.size() + pool.overflow() >= 0  # Просто проверяем что пул существует
        # Главная проверка — max_overflow не 0
        # В QueuePool: _max_overflow доступен как атрибут
        if hasattr(pool, '_max_overflow'):
            assert pool._max_overflow > 0, "max_overflow=0 вызовет TimeoutError при пиковой нагрузке"


class TestSessionGetAPI:
    """Проверка отсутствия deprecated session.query().get() паттерна."""

    def test_get_printer_uses_session_get(self, db: DBModel):
        """get_printer_by_id не должен вызывать LegacyAPIWarning."""
        import warnings
        printer = db.add_printer("SessionGetTest")
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = db.get_printer_by_id(printer.id)
            assert result is not None
            # Проверяем отсутствие LegacyAPIWarning
            legacy_warnings = [
                x for x in w
                if "LegacyAPIWarning" in str(type(x.category).__name__)
                or "legacy" in str(x.message).lower()
            ]
            assert legacy_warnings == [], (
                f"Deprecated API warnings: {[str(w.message) for w in legacy_warnings]}"
            )

    def test_get_task_uses_session_get(self, db: DBModel):
        """get_task не должен вызывать LegacyAPIWarning."""
        import warnings
        printer = db.add_printer("TaskPrinter2")
        task = db.add_task(name="Test task", printer_id=printer.id)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = db.get_task(task.id)
            assert result is not None
            legacy_warnings = [
                x for x in w
                if "LegacyAPIWarning" in str(type(x.category).__name__)
                or "legacy" in str(x.message).lower()
            ]
            assert legacy_warnings == [], (
                f"Deprecated API warnings: {[str(w.message) for w in legacy_warnings]}"
            )

    def test_get_coil_uses_session_get(self, db: DBModel):
        """get_coil не должен вызывать LegacyAPIWarning."""
        import warnings
        vendor = db.add_vendor("WarnVendor")
        filament = db.add_filament(
            name="PLA Warn", vendor_id=vendor.id, material="PLA", color_hex="#112233",
        )
        coil = db.add_coil(
            name="WarnCoil", remains=500.0,
            filament_id=filament.id, initial_weight=1000.0,
        )
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = db.get_coil(coil.id)
            assert result is not None
            legacy_warnings = [
                x for x in w
                if "LegacyAPIWarning" in str(type(x.category).__name__)
                or "legacy" in str(x.message).lower()
            ]
            assert legacy_warnings == [], (
                f"Deprecated API warnings: {[str(w.message) for w in legacy_warnings]}"
            )
