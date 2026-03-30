"""Blueprint: API проектов (CRUD)."""
from typing import Dict, Optional

from flask import Blueprint, jsonify, request

from backend.api.state import db
from backend.db.data_model import Project

projects_bp = Blueprint('projects', __name__)


def _serialize_project(project: Project) -> Dict:
    """Сериализация проекта."""
    return {
        "id": project.id,
        "name": project.name,
        "desc": project.desc,
        "color": project.color,
    }


def _validate_hex_color(value: Optional[str]) -> Optional[str]:
    """Валидация HEX-цвета."""
    if not value:
        return value
    color = value.strip()
    if len(color) not in (4, 7):
        raise ValueError("Цвет должен быть в формате HEX, например #ff00ff")
    if not color.startswith('#'):
        raise ValueError("Цвет должен начинаться с символа #")
    if any(ch not in "0123456789abcdefABCDEF" for ch in color[1:]):
        raise ValueError("Цвет может содержать только шестнадцатеричные символы")
    return color


@projects_bp.route('/api/projects', methods=['GET', 'POST'])
def api_projects():
    if request.method == 'GET':
        projects = db.get_projects()
        return jsonify([_serialize_project(project) for project in projects])

    data = request.get_json(force=True, silent=True) or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({"success": False, "message": "Название проекта обязательно"}), 400

    try:
        color = _validate_hex_color(data.get('color')) or "#888888"
    except ValueError as exc:
        return jsonify({"success": False, "message": str(exc)}), 400

    project = db.add_project(
        name=name,
        desc=(data.get('desc') or '').strip() or None,
        color=color,
    )
    return jsonify({"success": True, "project": _serialize_project(project)})


@projects_bp.route('/api/projects/<int:project_id>', methods=['GET', 'PUT', 'PATCH', 'DELETE'])
def api_project_detail(project_id: int):
    project = db.get_project(project_id)
    if not project:
        return jsonify({"success": False, "message": "Проект не найден"}), 404

    if request.method == 'GET':
        return jsonify({"success": True, "project": _serialize_project(project)})

    if request.method in ('PUT', 'PATCH'):
        data = request.get_json(force=True, silent=True) or {}
        updates: Dict[str, Optional[str]] = {}

        if 'name' in data:
            name = (data.get('name') or '').strip()
            if not name:
                return jsonify({"success": False, "message": "Название проекта обязательно"}), 400
            updates['name'] = name

        if 'desc' in data:
            updates['desc'] = (data.get('desc') or '').strip() or None

        if 'color' in data:
            try:
                updates['color'] = _validate_hex_color(data.get('color')) or "#888888"
            except ValueError as exc:
                return jsonify({"success": False, "message": str(exc)}), 400

        if not updates:
            return jsonify({"success": False, "message": "Нет данных для обновления"}), 400

        updated_project = db.update_project(project_id, **updates)
        if not updated_project:
            return jsonify({"success": False, "message": "Не удалось обновить проект"}), 400
        return jsonify({"success": True, "project": _serialize_project(updated_project)})

    # DELETE
    if db.delete_project(project_id):
        return jsonify({"success": True})
    return jsonify({
        "success": False,
        "message": "Не удалось удалить проект. Возможно, к нему все еще привязаны задачи."
    }), 409
