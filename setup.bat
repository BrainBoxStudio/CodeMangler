@echo off
setlocal EnableDelayedExpansion

echo === CodeMangler Setup ===
echo.

:: Check Python is available
where python >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Install Python 3.10+ and add it to PATH.
    exit /b 1
)

:: Verify Python version >= 3.10
for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PY_VER=%%v
for /f "tokens=1,2 delims=." %%a in ("%PY_VER%") do (
    set PY_MAJOR=%%a
    set PY_MINOR=%%b
)
if %PY_MAJOR% LSS 3 (
    echo ERROR: Python 3.10+ required. Found %PY_VER%.
    exit /b 1
)
if %PY_MAJOR% EQU 3 if %PY_MINOR% LSS 10 (
    echo ERROR: Python 3.10+ required. Found %PY_VER%.
    exit /b 1
)
echo [OK] Python %PY_VER%

:: Create virtual environment if not present
if not exist ".venv\" (
    echo Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment.
        exit /b 1
    )
    echo [OK] Virtual environment created.
) else (
    echo [OK] Virtual environment already exists.
)

:: Activate
call .venv\Scripts\activate.bat

:: Upgrade pip quietly
echo Upgrading pip...
python -m pip install --upgrade pip --quiet
echo [OK] pip up to date.

:: Install core dependencies
echo Installing core dependencies...
pip install -e "." --quiet
if errorlevel 1 (
    echo ERROR: Core install failed.
    exit /b 1
)
echo [OK] Core dependencies installed.

:: Install dev dependencies
echo Installing dev dependencies...
pip install -e ".[dev]" --quiet
if errorlevel 1 (
    echo ERROR: Dev install failed.
    exit /b 1
)
echo [OK] Dev dependencies installed.

echo.
echo === Optional extras ===
echo.
echo   Desktop UI (PySide6):
echo     pip install -e ".[ui]"   then run run_ui.bat
echo.
echo   PII (Presidio + spaCy NER):
echo     pip install -e ".[pii]"  then  python -m spacy download en_core_web_sm
echo.
echo   Local LLM HTTP client:
echo     pip install -e ".[llm]"
echo.
echo   Identifier renaming (Phase 2):
echo     pip install -e ".[code]"
echo.

:: Quick smoke test
echo Running tests...
python -m pytest app/tests --tb=short -q
if errorlevel 1 (
    echo WARNING: Some tests failed — check output above.
) else (
    echo [OK] All tests passed.
)

echo.
echo === Setup complete ===
echo Activate the environment with:  .venv\Scripts\activate.bat
echo Then run:                        codemangler --help
echo Or use run.bat directly.
echo.
endlocal
