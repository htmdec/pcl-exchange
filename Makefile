# Simple validation harness for PCL Exchange repo

SHELL := /bin/bash

# JSON Schema tools via Node
AJV ?= npx ajv

# Python tools
PYTHON ?= python3
PIP ?= pip3

EXAMPLE := examples/pcl_action_crate_example.json

.PHONY: help install validate validate-json validate-shacl clean

help:
	@echo "Targets:"
	@echo "  make install        # Install CLI tools (ajv-cli and pyshacl)"
	@echo "  make validate       # Validate everything (JSON Schema and SHACL)"
	@echo "  make validate-json  # Validate JSON Schemas against example(s)"
	@echo "  make validate-shacl # Validate example crate against SHACL shapes"
	@echo "  make clean          # Clean caches"

install:
	$(PIP) install --upgrade pyshacl rdflib
	npm -v >/dev/null 2>&1 || (echo 'Node/npm required for ajv-cli' && exit 1)
	npx --yes ajv-cli --version >/dev/null || true

validate: validate-json validate-shacl

validate-json:
	$(AJV) validate -s schemas/envelope.json -d $(EXAMPLE) --strict=false || true
	$(AJV) validate -s schemas/error.json -d <(echo '{"type":"https://w3id.org/pcl-profile/action/v1#Error","timestamp":"2025-01-01T00:00:00Z","code":"INVALID_ENVELOPE","reason":"demo"}') --strict=false

validate-shacl:
	$(PYTHON) scripts/validate_shacl.py --data $(EXAMPLE) --shapes shapes/measurement_request.ttl shapes/workflow_launch.ttl

clean:
	rm -rf .pytest_cache node_modules
