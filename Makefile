.PHONY: dev test backup migrate revision clean

dev:
	uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

test:
	pytest -v

migrate:
	alembic upgrade head

revision:
	alembic revision --autogenerate -m "$(m)"

backup:
	mkdir -p backups
	sqlite3 data/bakery.db ".backup 'backups/bakery_$$(date +%Y%m%d_%H%M%S).db'"
	@echo "Backup complete."

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete