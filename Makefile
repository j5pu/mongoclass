.PHONY: clean publish tests version

SHELL := $(shell bash -c 'command -v bash')
ROOT_DIR:=$(shell dirname $(realpath $(firstword $(MAKEFILE_LIST))))
PYTHONPATH := $(ROOT_DIR)/src
export PYTHONPATH

echo:
	echo $(PYTHONPATH)

build: clean
	@source venv/bin/activate && python3 -m build --wheel


clean:
	@rm -rf build dist mongita **/*.egg-info *.egg-info .mypy_cache .pytest_cache .tox setup.cfg setup.py .vscode \
		pyrightconfig.json

commit: tests
	@git add .
	@git commit --quiet -a -m "$${msg:-auto}" || true
	@git push --quiet

publish: commit
	@source venv/bin/activate && python3 -m twine -u __token__ upload dist/*
	@make clean

requirements:
	@source venv/bin/activate && pip3 install --upgrade pip pip-tools && \
		pip-compile --all-extras --no-annotate --quiet -o /tmp/requirements.txt pyproject.toml && \
		pip3 install -r /tmp/requirements.txt

tests: clean build
	@source venv/bin/activate && python -m unittest
