"""Тесты per-printer Lock для защиты от race condition при запуске печати."""
import threading
import time

import pytest


class TestGetPrinterLock:
    """Тесты функции _get_printer_lock — per-printer lock management."""

    def test_same_printer_returns_same_lock(self):
        """Один и тот же printer_id возвращает один и тот же Lock."""
        from backend.api.web_interface import _get_printer_lock

        lock1 = _get_printer_lock(1)
        lock2 = _get_printer_lock(1)
        assert lock1 is lock2

    def test_different_printers_return_different_locks(self):
        """Разные printer_id возвращают разные Lock-и."""
        from backend.api.web_interface import _get_printer_lock

        lock_a = _get_printer_lock(100)
        lock_b = _get_printer_lock(200)
        assert lock_a is not lock_b

    def test_lock_is_threading_lock(self):
        """Возвращаемый объект — threading.Lock."""
        from backend.api.web_interface import _get_printer_lock

        lock = _get_printer_lock(999)
        assert isinstance(lock, type(threading.Lock()))

    def test_concurrent_access_to_get_printer_lock(self):
        """Потокобезопасное создание lock-ов из нескольких потоков."""
        from backend.api.web_interface import _get_printer_lock

        results = []
        barrier = threading.Barrier(5)

        def get_lock():
            barrier.wait()
            lock = _get_printer_lock(42)
            results.append(lock)

        threads = [threading.Thread(target=get_lock) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        # Все потоки должны получить один и тот же объект Lock
        assert len(results) == 5
        assert all(r is results[0] for r in results)


class TestPrintStartRaceCondition:
    """Тест: двойной запуск печати на одном принтере — второй получает 409."""

    def test_concurrent_print_start_second_gets_409(self, client, db, monkeypatch):
        """Два одновременных POST /print/start — второй должен вернуть 409."""
        from backend.api import web_interface
        from backend.api.blueprints import print_control as bp_pc

        # Создаём принтер и задачу
        printer = db.add_printer(
            name="TestPrinter",
            moonraker_host="192.168.1.100",
            moonraker_port=7125,
        )
        printer_id = printer.id
        task = db.add_task(
            name="TestTask",
            printer_id=printer_id,
        )
        task_id = task.id
        # Загружаем фейковый gcode
        import os
        gcode_filename = "test_race.gcode"
        gcode_path = os.path.join(web_interface.UPLOAD_DIR, gcode_filename)
        os.makedirs(os.path.dirname(gcode_path), exist_ok=True)
        with open(gcode_path, "w") as f:
            f.write("G28\n")

        db.update_task(task_id, status="pending", model_gcode=gcode_filename)

        # Принтер online, idle — патчим и в web_interface, и в blueprint
        test_state = {
            "status": "standby",
            "temperature": {"extruder": 0.0, "bed": 0.0},
            "progress": 0,
            "filename": None,
        }
        with web_interface.printer_state_lock:
            web_interface.printer_states[printer_id] = test_state
        # Blueprint использует свою привязку printer_states — синхронизируем
        bp_pc.printer_states[printer_id] = test_state

        # Мокаем upload и start — upload медленный (имитация race condition)
        barrier = threading.Barrier(2, timeout=10)
        call_count = {"upload": 0, "start": 0}

        def slow_upload(printer, local_path, filename):
            call_count["upload"] += 1
            # Первый вызов ждёт, чтобы второй запрос тоже пришёл
            try:
                barrier.wait(timeout=5)
            except threading.BrokenBarrierError:
                pass
            time.sleep(0.1)
            return True, filename

        def mock_start(printer, filename):
            call_count["start"] += 1
            return True, "ok"

        monkeypatch.setattr(web_interface, "upload_gcode_to_printer", slow_upload)
        monkeypatch.setattr(web_interface, "start_print_on_printer", mock_start)
        # Патчим и blueprint-модуль (у него своя привязка через from...import)
        monkeypatch.setattr(bp_pc, "upload_gcode_to_printer", slow_upload)
        monkeypatch.setattr(bp_pc, "start_print_on_printer", mock_start)

        results = []

        def do_start():
            with web_interface.app.test_client() as c:
                resp = c.post(f"/api/tasks/{task_id}/print/start")
                results.append(resp.status_code)

        t1 = threading.Thread(target=do_start)
        t2 = threading.Thread(target=do_start)
        t1.start()
        t2.start()
        t1.join(timeout=15)
        t2.join(timeout=15)

        # Один должен пройти (200), другой — заблокирован (409)
        assert sorted(results) == [200, 409], f"Expected [200, 409], got {sorted(results)}"

        # Только одна задача реально стартовала
        assert call_count["start"] == 1

        # Очистка
        try:
            os.remove(gcode_path)
        except OSError:
            pass
