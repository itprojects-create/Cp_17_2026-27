test-golden:
	python -m pytest backend/tests/test_golden_cases.py -v

test-all:
	python -m pytest backend/tests -v

verify:
	python -m pytest backend/tests -v
	cd frontend && npm run build

