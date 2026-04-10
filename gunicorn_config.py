"""Gunicorn конфигурация для Raspberry Pi 4B (4GB RAM, ARM64).

Запуск: gunicorn --config gunicorn_config.py backend.api.web_interface:app
"""

# Сетевые настройки
bind = "0.0.0.0:5000"

# Воркеры — оптимизировано для RPi 4B (4GB RAM)
workers = 2                    # (2*CPU+1)/2 ~ 2-3, ограничено RAM
worker_class = "gthread"       # Потоки — экономнее RAM чем fork
threads = 4                    # 4 потока на воркер = 8 concurrent requests

# Таймауты
timeout = 60                   # Загрузка G-code может быть долгой (до 200MB)
graceful_timeout = 30
keepalive = 5

# Recycling — борьба с утечками памяти
max_requests = 500
max_requests_jitter = 50

# Оптимизация памяти
preload_app = True             # Экономия RAM через copy-on-write

# Логирование
accesslog = "-"
errorlog = "-"
loglevel = "warning"


def post_worker_init(worker):
    """Запуск фоновых потоков в каждом воркере Gunicorn после fork().

    preload_app=True загружает приложение в мастер-процессе,
    но потоки не наследуются при fork(). Поэтому запускаем
    фоновые потоки в каждом воркере отдельно.
    """
    from backend.api.web_interface import app
    from backend.services.background import start_background_threads
    start_background_threads(app)
