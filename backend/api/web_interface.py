"""Точка входа PrinterBase.

Для разработки: python -m backend.api.web_interface
Для Gunicorn:   gunicorn --config gunicorn_config.py backend.api.web_interface:app
"""
from backend.api.app import create_app
from backend.services.background import start_background_threads

# Создаём app (для Gunicorn и тестов)
app = create_app()

# ---------------------------------------------------------------------------
# Re-exports для обратной совместимости (тесты и другие модули импортируют отсюда)
# ---------------------------------------------------------------------------
from backend.api.state import (  # noqa: F401,E402
    db,
    http,
    printer_states,
    printer_state_lock,
    health_registry,
    _printer_action_locks,
    _printer_action_locks_lock,
    _get_printer_lock,
    DEFAULT_PRINTER_PORT,
    DEFAULT_FALLBACK_HOST,
    DISCOVERY_ENABLED,
    DISCOVERY_INTERVAL_SECONDS,
    PRINTER_STATE_INTERVAL,
    ALLOWED_GCODE_EXTENSIONS,
    ALLOWED_VIRTUAL_STATUSES,
    DATABASE_PATH,
    UPLOAD_DIR,
    STATE_MAP,
)

from backend.services.moonraker_client import (  # noqa: F401,E402
    build_printer_key,
    build_base_url,
    enrich_params_with_printer,
    _perform_moonraker_request,
    _request_with_fallback,
    moonraker_get,
    moonraker_post,
    fetch_printers_for_host,
    fetch_printer_display_name,
    probe_moonraker_host,
    upsert_printers_for_host,
    synchronize_printers_with_db,
    build_default_state,
    fetch_printer_state,
    upload_gcode_to_printer,
    start_print_on_printer,
    pause_print_on_printer,
    resume_print_on_printer,
    cancel_print_on_printer,
    get_printer_print_status,
)

from backend.services.background import (  # noqa: F401,E402
    _executor,
    update_printer_states_loop,
    monitor_printing_tasks,
    handle_print_complete,
    handle_print_error,
    handle_print_cancelled,
)

# Helpers re-export
from backend.api.helpers import (  # noqa: F401,E402
    allowed_gcode_file,
    get_printer_or_default,
    serialize_task,
    remove_task_gcode,
)

# ---------------------------------------------------------------------------
# Запуск фоновых потоков
# ---------------------------------------------------------------------------
# НЕ запускаем при импорте модуля — с preload_app=True потоки стартуют
# в мастер-процессе gunicorn и погибают при fork().
# Gunicorn: потоки стартуют через post_worker_init в gunicorn_config.py
# Dev-режим: потоки стартуют в __main__ ниже

if __name__ == '__main__':
    start_background_threads(app)
    app.run(host='0.0.0.0', port=5000, debug=True)
