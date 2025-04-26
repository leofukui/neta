format:
	poetry run black src

lint:
	poetry run ruff check src --fix

test:
	poetry run pytest
