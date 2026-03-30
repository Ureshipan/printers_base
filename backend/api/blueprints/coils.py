"""Blueprint: API катушек, вендоров, филаментов, материалов."""
from flask import Blueprint, jsonify, request

from backend.api.state import db
from backend.db.data_model import Coil

coils_bp = Blueprint('coils', __name__)


def serialize_coil(coil: Coil) -> dict:
    """Сериализация катушки с расширенными полями."""
    # Данные из филамента (приоритетные)
    filament = coil.filament
    filament_data = None
    if filament:
        filament_data = {
            "id": filament.id,
            "name": filament.name,
            "material": filament.material,
            "color_hex": filament.color_hex,
            "vendor_id": filament.vendor_id,
            "vendor_name": filament.vendor.name if filament.vendor else None,
        }

    # Цвет: из катушки или из филамента
    color = coil.color_hex or (filament.color_hex if filament else None)

    return {
        "id": coil.id,
        "name": coil.name,
        "filament": filament_data,
        "filament_id": coil.filament_id,
        # Deprecated поля для совместимости
        "material": coil.material.name if coil.material else (filament.material if filament else None),
        "material_id": coil.material_id,
        "vendor": {"id": coil.vendor.id, "name": coil.vendor.name} if coil.vendor else (
            {"id": filament.vendor.id, "name": filament.vendor.name} if filament and filament.vendor else None
        ),
        "vendor_id": coil.vendor_id,
        "remains": coil.remains,
        "initial_weight": coil.initial_weight,
        "used_weight": coil.used_weight,
        "spool_weight": coil.spool_weight,
        "total_weight": coil.total_weight,
        "color_hex": color,
        "price": coil.price,
        "location": coil.location,
        "lot_nr": coil.lot_nr,
        "comment": coil.comment,
        "archived": coil.archived or False,
        "first_used": coil.first_used.isoformat() if coil.first_used else None,
        "last_used": coil.last_used.isoformat() if coil.last_used else None,
        "remains_percent": coil.remains_percent,
        "remains_status": coil.remains_status,
    }


def serialize_filament(filament):
    """Сериализация филамента."""
    return {
        "id": filament.id,
        "vendor_id": filament.vendor_id,
        "vendor_name": filament.vendor.name if filament.vendor else None,
        "name": filament.name,
        "material": filament.material,
        "color_hex": filament.color_hex,
        "diameter": filament.diameter,
        "density": filament.density,
        "weight": filament.weight,
        "empty_spool_weight": filament.empty_spool_weight,
        "description": filament.description,
    }


@coils_bp.route('/api/coils', methods=['GET', 'POST'])
def api_coils():
    """GET: Список катушек с фильтрами. POST: Создать катушку."""
    if request.method == 'GET':
        filament_id = request.args.get('filament_id', type=int)
        material_id = request.args.get('material_id', type=int)
        vendor_id = request.args.get('vendor_id', type=int)
        archived = request.args.get('archived')
        include_archived = request.args.get('include_archived', '0') == '1'

        archived_filter = None
        if archived is not None:
            archived_filter = archived.lower() in ('true', '1', 'yes')

        coils = db.get_coils(
            filament_id=filament_id,
            material_id=material_id,
            vendor_id=vendor_id,
            archived=archived_filter,
            include_archived=include_archived,
        )
        return jsonify([serialize_coil(coil) for coil in coils])

    # POST - создание катушки
    data = request.get_json(force=True, silent=True) or {}
    # filament_id обязателен, остальное опционально
    required_fields = ['name', 'filament_id', 'remains']
    missing = [f for f in required_fields if data.get(f) is None]
    if missing:
        return jsonify({"success": False, "message": f"Отсутствуют поля: {', '.join(missing)}"}), 400

    coil = db.add_coil(
        name=data['name'],
        filament_id=data['filament_id'],
        remains=data['remains'],
        material_id=data.get('material_id'),  # Deprecated
        vendor_id=data.get('vendor_id'),  # Deprecated
        spool_weight=data.get('spool_weight'),
        initial_weight=data.get('initial_weight', data['remains']),
        color_hex=data.get('color_hex'),
        price=data.get('price'),
        location=data.get('location'),
        lot_nr=data.get('lot_nr'),
        comment=data.get('comment'),
    )
    coil = db.get_coil(coil.id)
    return jsonify({"success": True, "coil": serialize_coil(coil)})


@coils_bp.route('/api/coils/<int:coil_id>', methods=['GET', 'PUT', 'PATCH', 'DELETE'])
def api_coil_detail(coil_id: int):
    """Операции с конкретной катушкой."""
    coil = db.get_coil(coil_id)
    if not coil:
        return jsonify({"success": False, "message": "Катушка не найдена"}), 404

    if request.method == 'GET':
        result = serialize_coil(coil)
        # Добавляем историю для детального просмотра
        history = db.get_spool_history(coil_id=coil_id, limit=50)
        result['history'] = [
            {
                "id": h.id,
                "used_weight": h.used_weight,
                "timestamp": h.timestamp.isoformat() if h.timestamp else None,
                "notes": h.notes,
                "task": {"id": h.task.id, "name": h.task.name} if h.task else None,
            }
            for h in history
        ]
        return jsonify(result)

    if request.method == 'DELETE':
        if db.delete_coil(coil_id):
            return jsonify({"success": True})
        return jsonify({"success": False, "message": "Не удалось удалить катушку"}), 400

    # PUT/PATCH - обновление
    data = request.get_json(force=True, silent=True) or {}
    updated = db.update_coil(coil_id, **data)
    if updated:
        updated = db.get_coil(coil_id)
        return jsonify({"success": True, "coil": serialize_coil(updated)})
    return jsonify({"success": False, "message": "Не удалось обновить катушку"}), 400


@coils_bp.route('/api/coils/<int:coil_id>/archive', methods=['POST'])
def api_coil_archive(coil_id: int):
    """Архивировать катушку."""
    coil = db.archive_coil(coil_id)
    if coil:
        coil = db.get_coil(coil_id)
        return jsonify({"success": True, "coil": serialize_coil(coil)})
    return jsonify({"success": False, "message": "Катушка не найдена"}), 404


@coils_bp.route('/api/coils/<int:coil_id>/unarchive', methods=['POST'])
def api_coil_unarchive(coil_id: int):
    """Разархивировать катушку."""
    coil = db.unarchive_coil(coil_id)
    if coil:
        coil = db.get_coil(coil_id)
        return jsonify({"success": True, "coil": serialize_coil(coil)})
    return jsonify({"success": False, "message": "Катушка не найдена"}), 404


@coils_bp.route('/api/coils/<int:coil_id>/adjust', methods=['POST'])
def api_coil_adjust(coil_id: int):
    """Ручная корректировка остатка катушки."""
    data = request.get_json(force=True, silent=True) or {}
    new_remains = data.get('remains')
    if new_remains is None:
        return jsonify({"success": False, "message": "Поле remains обязательно"}), 400

    coil = db.adjust_coil_remains(coil_id, new_remains, notes=data.get('notes'))
    if coil:
        coil = db.get_coil(coil_id)
        return jsonify({"success": True, "coil": serialize_coil(coil)})
    return jsonify({"success": False, "message": "Катушка не найдена"}), 404


@coils_bp.route('/api/coils/<int:coil_id>/history')
def api_coil_history(coil_id: int):
    """История расхода катушки."""
    history = db.get_spool_history(coil_id=coil_id)
    return jsonify([
        {
            "id": h.id,
            "used_weight": h.used_weight,
            "timestamp": h.timestamp.isoformat() if h.timestamp else None,
            "notes": h.notes,
            "task": {"id": h.task.id, "name": h.task.name} if h.task else None,
        }
        for h in history
    ])


@coils_bp.route('/api/materials')
def api_get_materials():
    materials = db.get_materials()
    return jsonify([
        {
            "id": material.id,
            "name": material.name,
            "nozzle_tmp": material.nozzle_tmp,
            "table_tmp": material.table_tmp,
        }
        for material in materials
    ])


# === Vendors API ===

@coils_bp.route('/api/vendors', methods=['GET', 'POST'])
def api_vendors():
    """GET: Список производителей. POST: Создать производителя."""
    if request.method == 'GET':
        vendors = db.get_vendors()
        return jsonify([
            {
                "id": v.id,
                "name": v.name,
                "comment": v.comment,
                "empty_spool_weight": v.empty_spool_weight,
            }
            for v in vendors
        ])

    # POST - создание производителя
    data = request.get_json(force=True, silent=True) or {}
    if not data.get('name'):
        return jsonify({"success": False, "message": "Поле name обязательно"}), 400

    # Валидация веса пустой катушки
    empty_weight = data.get('empty_spool_weight')
    if empty_weight is None or float(empty_weight) <= 0:
        return jsonify({"success": False, "message": "Вес пустой катушки обязателен и должен быть больше 0"}), 400

    vendor = db.add_vendor(
        name=data['name'],
        comment=data.get('comment'),
        empty_spool_weight=data.get('empty_spool_weight'),
    )
    return jsonify({
        "success": True,
        "vendor": {
            "id": vendor.id,
            "name": vendor.name,
            "comment": vendor.comment,
            "empty_spool_weight": vendor.empty_spool_weight,
        }
    })


@coils_bp.route('/api/vendors/<int:vendor_id>', methods=['GET', 'PUT', 'PATCH', 'DELETE'])
def api_vendor_detail(vendor_id: int):
    """Операции с конкретным производителем."""
    vendor = db.get_vendor(vendor_id)
    if not vendor:
        return jsonify({"success": False, "message": "Производитель не найден"}), 404

    if request.method == 'GET':
        return jsonify({
            "id": vendor.id,
            "name": vendor.name,
            "comment": vendor.comment,
            "empty_spool_weight": vendor.empty_spool_weight,
        })

    if request.method == 'DELETE':
        if db.delete_vendor(vendor_id):
            return jsonify({"success": True})
        return jsonify({"success": False, "message": "Не удалось удалить производителя"}), 400

    # PUT/PATCH - обновление
    data = request.get_json(force=True, silent=True) or {}

    # Валидация веса пустой катушки при обновлении
    if 'empty_spool_weight' in data:
        empty_weight = data.get('empty_spool_weight')
        if empty_weight is None or float(empty_weight) <= 0:
            return jsonify({"success": False, "message": "Вес пустой катушки должен быть больше 0"}), 400

    updated = db.update_vendor(vendor_id, **data)
    if updated:
        return jsonify({
            "success": True,
            "vendor": {
                "id": updated.id,
                "name": updated.name,
                "comment": updated.comment,
                "empty_spool_weight": updated.empty_spool_weight,
            }
        })
    return jsonify({"success": False, "message": "Не удалось обновить производителя"}), 400


# === Filaments API ===

@coils_bp.route('/api/filaments', methods=['GET', 'POST'])
def api_filaments():
    """Список филаментов или создание нового."""
    if request.method == 'GET':
        vendor_id = request.args.get('vendor_id', type=int)
        material = request.args.get('material')
        filaments = db.get_filaments(vendor_id=vendor_id, material=material)
        return jsonify([serialize_filament(f) for f in filaments])

    # POST - создание
    data = request.get_json(force=True, silent=True) or {}
    if not data.get('name'):
        return jsonify({"success": False, "message": "Название обязательно"}), 400

    filament = db.add_filament(
        name=data['name'],
        vendor_id=data.get('vendor_id'),
        material=data.get('material'),
        color_hex=data.get('color_hex'),
        diameter=data.get('diameter'),
        density=data.get('density'),
        weight=data.get('weight'),
        empty_spool_weight=data.get('empty_spool_weight'),
        description=data.get('description'),
    )
    return jsonify({"success": True, "filament": serialize_filament(filament)})


@coils_bp.route('/api/filaments/<int:filament_id>', methods=['GET', 'PUT', 'PATCH', 'DELETE'])
def api_filament_detail(filament_id: int):
    """Операции с конкретным филаментом."""
    filament = db.get_filament(filament_id)
    if not filament:
        return jsonify({"success": False, "message": "Филамент не найден"}), 404

    if request.method == 'GET':
        return jsonify(serialize_filament(filament))

    if request.method == 'DELETE':
        if db.delete_filament(filament_id):
            return jsonify({"success": True})
        return jsonify({"success": False, "message": "Не удалось удалить филамент"}), 400

    # PUT/PATCH - обновление
    data = request.get_json(force=True, silent=True) or {}
    updated = db.update_filament(filament_id, **data)
    if updated:
        return jsonify({"success": True, "filament": serialize_filament(updated)})
    return jsonify({"success": False, "message": "Не удалось обновить филамент"}), 400
