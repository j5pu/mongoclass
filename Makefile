.PHONY: clean publish tests version

msg := fix: $(shell git status --porcelain | grep -v "^??" | cut -c4- | tr '\n' ' ')
SHELL := $(shell bash -c 'command -v bash')
ROOT_DIR:=$(shell dirname $(realpath $(firstword $(MAKEFILE_LIST))))
PYTHONPATH := $(ROOT_DIR)/src
PYTHONTRACEMALLOC := 20
export msg
export PYTHONPATH
export PYTHONTRACEMALLOC

brew:
	@brew bundle --file=src/huti/data/Brewfile --no-lock --quiet

build: clean
	@{ [ "$${CI-}" ] || source venv/bin/activate; } && python3 -m build --wheel

clean:
	@sudo rm -rf build dist mongita **/*.egg-info *.egg-info .mypy_cache .pytest_cache .tox setup.cfg setup.py .vscode \
		pyrightconfig.json mongita .coverage .ruff_cache  || true

commit: tests tox
	@git add -A .
	@git commit --quiet -a -m "$${msg:-fix:}" || true

coverage:
	@{ [ "$${CI-}" ] || source venv/bin/activate; } && coverage run -m pytest && coverage report

lint:
	@{ [ "$${CI-}" ] || source venv/bin/activate; } && ruff check src

publish: tag
	@make build
	@{ [ "$${CI-}" ] || source venv/bin/activate; } && twine upload -u __token__ dist/*
	@make clean

pyenv:
	@pyenv install 3.9
	@pyenv install 3.10
	@pyenv install 3.11
	@pyenv install 3.12-dev

requirements:
	@test -d venv || python3.10 -m venv venv
	@source venv/bin/activate && pip3 install --upgrade huti
	@venv/bin/dependencies

secrets:
	@gh secret set GH_TOKEN --body "$$GITHUB_TOKEN"
	@grep -v GITHUB_ /Users/j5pu/secrets/profile.d/secrets.sh > /tmp/secrets
	@gh secret set -f  /tmp/secrets

tag: commit
	@NEXT=$$(svu next --strip-prefix) && \
		CURRENT=$$(svu --strip-prefix) && \
		TAG=$$(git tag --list --sort=-v:refname | head -n1) && \
		{ test $$NEXT != $$CURRENT || test $$NEXT != $$TAG; } && \
		CHANGED=1 && echo $$CURRENT $$NEXT $$TAG && \
		git tag $$NEXT && \
		git push --quiet --tags  || true

tests: lint build
	@{ [ "$${CI-}" ] || source venv/bin/activate; } && python -m unittest  && pytest

tox:
	@eval "$$(pyenv init --path)";{  [ "$${CI-}" ] || source venv/bin/activate; } && \
		PY_IGNORE_IMPORTMISMATCH=1 tox
