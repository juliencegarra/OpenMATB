source .venv/bin/activate
python3 -m nuitka --standalone --include-data-dir="./includes"="includes" --include-data-dir="./locales"="locales" --include-data-file="config.ini"="config.ini" --include-data-file="LICENSE"="LICENSE" --include-data-file="README.md"="README.md" --remove-output main.py
