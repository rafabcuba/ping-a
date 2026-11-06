.PHONY: test standalone clean

test:
	PYTHONPATH=src python3 -m unittest discover -s tests -v

standalone:
	python3 scripts/build_standalone.py

clean:
	rm -rf dist build *.egg-info src/*.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
