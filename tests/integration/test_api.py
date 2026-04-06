"""Integration-тесты Flask REST API endpoints.

Проверяем: status code, структуру JSON, CRUD через HTTP.
Мокаем только Moonraker (probe_moonraker_host, upsert_printers_for_host).
"""
from unittest.mock import patch, MagicMock

import pytest


# ---------------------------------------------------------------------------
# Страницы (HTML)
# ---------------------------------------------------------------------------
class TestPages:
    """Проверка что HTML-страницы отдаются."""

    def test_dashboard(self, client):
        resp = client.get("/")
        assert resp.status_code == 200

    def test_planning_page(self, client):
        resp = client.get("/planning")
        assert resp.status_code == 200

    def test_maintenance_page(self, client):
        resp = client.get("/maintenance")
        assert resp.status_code == 200

    def test_spools_page(self, client):
        resp = client.get("/spools")
        assert resp.status_code == 200

    def test_printer_control_page(self, client):
        resp = client.get("/printer-control")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Принтеры
# ---------------------------------------------------------------------------
class TestPrintersAPI:
    """Тесты CRUD принтеров."""

    def test_get_printers_empty(self, client):
        """Пустой список принтеров при старте."""
        resp = client.get("/api/printers")
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_create_virtual_printer(self, client):
        """Создание виртуального принтера (не требует Moonraker)."""
        resp = client.post("/api/printers/virtual", json={
            "name": "Virtual Test",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["printer"]["name"] == "Virtual Test"
        assert data["printer"]["is_virtual"] is True
        assert "id" in data["printer"]

    def test_create_virtual_printer_no_name(self, client):
        """Ошибка при создании виртуального принтера без имени."""
        resp = client.post("/api/printers/virtual", json={})
        assert resp.status_code == 400
        assert resp.get_json()["success"] is False

    def test_create_real_printer(self, client, monkeypatch):
        """Создание реального принтера (мокаем probe + upsert)."""
        from backend.api import web_interface
        from backend.api.blueprints import printers as bp_printers
        from backend.db.data_model import Printer

        mock_probe = lambda *a, **kw: True  # noqa: E731
        monkeypatch.setattr(web_interface, "probe_moonraker_host", mock_probe)
        monkeypatch.setattr(bp_printers, "probe_moonraker_host", mock_probe)

        # upsert_printers_for_host возвращает список Printer
        def mock_upsert(host, port):
            printer = web_interface.db.add_virtual_printer(name=f"Printer@{host}")
            return [printer]

        monkeypatch.setattr(web_interface, "upsert_printers_for_host", mock_upsert)
        monkeypatch.setattr(bp_printers, "upsert_printers_for_host", mock_upsert)

        resp = client.post("/api/printers", json={
            "host": "192.168.1.100",
            "port": 7125,
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert len(data["printers"]) == 1

    def test_create_real_printer_no_host(self, client):
        """Ошибка при создании принтера без хоста."""
        resp = client.post("/api/printers", json={"port": 7125})
        assert resp.status_code == 400
        assert resp.get_json()["success"] is False

    def test_get_printer_by_id(self, client):
        """Получение принтера по ID."""
        # Создаём виртуальный принтер
        create_resp = client.post("/api/printers/virtual", json={
            "name": "GetById Test",
        })
        pid = create_resp.get_json()["printer"]["id"]

        resp = client.get(f"/api/printers/{pid}")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["printer"]["name"] == "GetById Test"

    def test_get_printer_not_found(self, client):
        """404 при запросе несуществующего принтера."""
        resp = client.get("/api/printers/9999")
        assert resp.status_code == 404

    def test_delete_printer(self, client):
        """Удаление принтера."""
        create_resp = client.post("/api/printers/virtual", json={
            "name": "ToDelete",
        })
        pid = create_resp.get_json()["printer"]["id"]

        resp = client.delete(f"/api/printers/{pid}")
        assert resp.status_code == 200
        assert resp.get_json()["success"] is True

        # Проверяем что удалился
        resp = client.get(f"/api/printers/{pid}")
        assert resp.status_code == 404

    def test_update_virtual_printer(self, client):
        """Обновление виртуального принтера."""
        create_resp = client.post("/api/printers/virtual", json={
            "name": "BeforeUpdate",
        })
        pid = create_resp.get_json()["printer"]["id"]

        resp = client.put(f"/api/printers/{pid}", json={
            "name": "AfterUpdate",
            "status": "work",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["printer"]["name"] == "AfterUpdate"


# ---------------------------------------------------------------------------
# Проекты
# ---------------------------------------------------------------------------
class TestProjectsAPI:
    """Тесты CRUD проектов."""

    def test_get_projects_empty(self, client):
        """Пустой список проектов."""
        resp = client.get("/api/projects")
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_create_project(self, client):
        """Создание проекта."""
        resp = client.post("/api/projects", json={
            "name": "Test Project",
            "desc": "Description",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["project"]["name"] == "Test Project"
        assert "id" in data["project"]

    def test_create_project_no_name(self, client):
        """Ошибка при создании проекта без имени."""
        resp = client.post("/api/projects", json={"desc": "no name"})
        assert resp.status_code == 400
        assert resp.get_json()["success"] is False

    def test_get_project_by_id(self, client):
        """Получение проекта по ID."""
        create_resp = client.post("/api/projects", json={"name": "ById"})
        pid = create_resp.get_json()["project"]["id"]

        resp = client.get(f"/api/projects/{pid}")
        assert resp.status_code == 200
        assert resp.get_json()["project"]["name"] == "ById"

    def test_get_project_not_found(self, client):
        """404 при запросе несуществующего проекта."""
        resp = client.get("/api/projects/9999")
        assert resp.status_code == 404

    def test_update_project(self, client):
        """Обновление проекта (PATCH)."""
        create_resp = client.post("/api/projects", json={"name": "Old"})
        pid = create_resp.get_json()["project"]["id"]

        resp = client.patch(f"/api/projects/{pid}", json={"name": "New"})
        assert resp.status_code == 200
        assert resp.get_json()["project"]["name"] == "New"

    def test_delete_project(self, client):
        """Удаление проекта."""
        create_resp = client.post("/api/projects", json={"name": "Del"})
        pid = create_resp.get_json()["project"]["id"]

        resp = client.delete(f"/api/projects/{pid}")
        assert resp.status_code == 200
        assert resp.get_json()["success"] is True


# ---------------------------------------------------------------------------
# Задачи
# ---------------------------------------------------------------------------
class TestTasksAPI:
    """Тесты CRUD задач."""

    @pytest.fixture
    def _printer_and_project(self, client):
        """Создаёт принтер + проект, возвращает их ID."""
        pr = client.post("/api/printers/virtual", json={"name": "TaskPrinter"})
        proj = client.post("/api/projects", json={"name": "TaskProject"})
        return pr.get_json()["printer"]["id"], proj.get_json()["project"]["id"]

    def test_get_tasks_empty(self, client):
        """Пустой список задач."""
        resp = client.get("/api/tasks")
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_create_task(self, client, _printer_and_project):
        """Создание задачи."""
        printer_id, project_id = _printer_and_project
        resp = client.post("/api/tasks", json={
            "name": "Test Task",
            "printer_id": printer_id,
            "project_id": project_id,
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["task"]["name"] == "Test Task"
        assert data["task"]["printer"]["id"] == printer_id
        assert data["task"]["project"]["id"] == project_id

    def test_create_task_missing_fields(self, client):
        """Ошибка при создании задачи без обязательных полей."""
        resp = client.post("/api/tasks", json={"name": "NoIds"})
        assert resp.status_code == 400
        assert resp.get_json()["success"] is False

    def test_get_task_by_id(self, client, _printer_and_project):
        """Получение задачи по ID."""
        printer_id, project_id = _printer_and_project
        create_resp = client.post("/api/tasks", json={
            "name": "GetMe",
            "printer_id": printer_id,
            "project_id": project_id,
        })
        tid = create_resp.get_json()["task"]["id"]

        resp = client.get(f"/api/tasks/{tid}")
        assert resp.status_code == 200
        assert resp.get_json()["task"]["name"] == "GetMe"

    def test_get_task_not_found(self, client):
        """404 при запросе несуществующей задачи."""
        resp = client.get("/api/tasks/9999")
        assert resp.status_code == 404

    def test_delete_task(self, client, _printer_and_project):
        """Удаление задачи."""
        printer_id, project_id = _printer_and_project
        create_resp = client.post("/api/tasks", json={
            "name": "DelMe",
            "printer_id": printer_id,
            "project_id": project_id,
        })
        tid = create_resp.get_json()["task"]["id"]

        resp = client.delete(f"/api/tasks/{tid}")
        assert resp.status_code == 200
        assert resp.get_json()["success"] is True


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
class TestHealthAPI:
    """Тест health endpoint."""

    def test_health_returns_ok(self, client):
        """GET /api/health возвращает status=ok."""
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"
        assert "printers_total" in data
        assert "health" in data


# ---------------------------------------------------------------------------
# Катушки (Coils)
# ---------------------------------------------------------------------------
class TestCoilsAPI:
    """Тесты API катушек."""

    def test_get_coils_empty(self, client):
        """Пустой список катушек."""
        resp = client.get("/api/coils")
        assert resp.status_code == 200
        assert resp.get_json() == []


# ---------------------------------------------------------------------------
# Производители (Vendors)
# ---------------------------------------------------------------------------
class TestVendorsAPI:
    """Тесты API производителей."""

    def test_get_vendors_empty(self, client):
        """Пустой список производителей."""
        resp = client.get("/api/vendors")
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_create_vendor(self, client):
        """Создание производителя."""
        resp = client.post("/api/vendors", json={
            "name": "TestVendor",
            "empty_spool_weight": 250.0,
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["vendor"]["name"] == "TestVendor"

    def test_create_vendor_no_name(self, client):
        """Ошибка при создании производителя без имени."""
        resp = client.post("/api/vendors", json={"empty_spool_weight": 250})
        assert resp.status_code == 400
        assert resp.get_json()["success"] is False

    def test_create_vendor_no_weight(self, client):
        """Ошибка при создании производителя без веса катушки."""
        resp = client.post("/api/vendors", json={"name": "NoWeight"})
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Материалы (Materials)
# ---------------------------------------------------------------------------
class TestMaterialsAPI:
    """Тесты API материалов."""

    def test_get_materials(self, client):
        """Список материалов (может быть пустым)."""
        resp = client.get("/api/materials")
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)
