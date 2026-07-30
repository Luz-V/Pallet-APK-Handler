#!/usr/bin/env bash

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"

exec "$PROJECT_ROOT/.venv/bin/python" "$PROJECT_ROOT/main.py"
