"""Application Factory для PrinterBase.

Создаёт Flask-приложение с зарегистрированными blueprints.
"""
import logging

from flask import Flask

from backend.api.state import UPLOAD_DIR

# Конфигурация structured logging (один раз при импорте)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def create_app(testing: bool = False) -> Flask:
    """Создать и настроить Flask-приложение.

    Args:
        testing: включить режим тестирования.
    """
    app = Flask(
        __name__,
        template_folder='../../frontend/templates',
        static_folder='../../frontend/static',
    )

    app.config['UPLOAD_FOLDER'] = UPLOAD_DIR
    app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024  # 200MB
    app.config['TESTING'] = testing

    # Регистрация blueprints (ленивый импорт для избежания circular imports)
    from backend.api.blueprints.pages import pages_bp
    from backend.api.blueprints.printers import printers_bp
    from backend.api.blueprints.tasks import tasks_bp
    from backend.api.blueprints.print_control import print_control_bp
    from backend.api.blueprints.projects import projects_bp
    from backend.api.blueprints.coils import coils_bp
    from backend.api.blueprints.maintenance import maintenance_bp
    from backend.api.blueprints.control import control_bp

    app.register_blueprint(pages_bp)
    app.register_blueprint(printers_bp)
    app.register_blueprint(tasks_bp)
    app.register_blueprint(print_control_bp)
    app.register_blueprint(projects_bp)
    app.register_blueprint(coils_bp)
    app.register_blueprint(maintenance_bp)
    app.register_blueprint(control_bp)

    return app
