@echo off
setlocal EnableDelayedExpansion

if not exist ".venv\Scripts\activate.bat" (
    echo ERROR: Virtual environment not found. Run setup.bat first.
    pause
    exit /b 1
)
call .venv\Scripts\activate.bat

python -c "import PySide6" 2>nul
if errorlevel 1 (
    echo ERROR: PySide6 is not installed.
    echo Run:  pip install -e ".[ui]"
    pause
    exit /b 1
)

python -m app.ui.run_ui %*
if errorlevel 1 (
    echo.
    echo The UI exited with an error. See codemangler_ui.log for details.
    pause
)
