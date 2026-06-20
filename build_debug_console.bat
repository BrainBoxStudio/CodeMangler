@echo off
call .venv\Scripts\activate.bat
pyinstaller --noconfirm --clean --onefile --name CodeMangler_debug --add-data "app\resources;app\resources" app\ui\run_ui.py
