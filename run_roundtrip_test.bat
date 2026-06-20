@echo off
if not exist ".venv\Scripts\activate.bat" (
    echo ERROR: Virtual environment not found. Run setup.bat first.
    exit /b 1
)
call .venv\Scripts\activate.bat
python scripts\roundtrip_test.py
