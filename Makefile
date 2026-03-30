.PHONY: run dev test test-unit test-cov lint lint-fix install

# Установка зависимостей
install:
	pip install -r requirements.txt

# Запуск (разработка — Flask dev server)
dev:
	python -m backend.api.web_interface

# Запуск (продакшен — Gunicorn)
run:
	gunicorn --config gunicorn_config.py backend.api.web_interface:app

# Тесты
test:
	pytest tests/ --tb=short -q

test-unit:
	pytest tests/unit/ --tb=short -q

test-cov:
	pytest tests/ --cov=backend --cov-report=term-missing --cov-fail-under=70 --tb=short -q

# Линтинг
lint:
	ruff check backend/

lint-fix:
	ruff check --fix backend/
