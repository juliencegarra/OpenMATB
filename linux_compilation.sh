#!/usr/bin/env bash
# Compile OpenMATB for Linux with Nuitka (standalone folder main.dist, program main.dist/main.bin), from the .venv
# virtual environment of the repository: python3 -m pip install nuitka ordered-set -r requirements.txt
set -euo pipefail
cd "$(dirname "$0")"  # The data files are given relative to the repository root

source .venv/bin/activate
python3 -m nuitka --standalone --include-data-dir="./includes"="includes" --include-data-dir="./locales"="locales" --include-data-file="config.ini"="config.ini" --include-data-file="VERSION"="VERSION" --include-data-file="LICENSE"="LICENSE" --include-data-file="README.md"="README.md" --remove-output main.py
