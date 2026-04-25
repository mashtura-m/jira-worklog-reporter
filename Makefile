VENV=venv
PYTHON=$(VENV)/bin/python
PIP=$(VENV)/bin/pip

.PHONY: install run clean

install:
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

run:
	$(PYTHON) -m src.main

clean:
	rm -rf $(VENV)