@echo off
setlocal EnableDelayedExpansion

if not exist ".venv\Scripts\activate.bat" (
    echo ERROR: Virtual environment not found. Run setup.bat first.
    pause
    exit /b 1
)
call .venv\Scripts\activate.bat

echo === CodeMangler: Build Standalone Executables ===
echo.

:: Ensure PyInstaller is available
python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo Installing PyInstaller...
    pip install pyinstaller --quiet
    if errorlevel 1 (
        echo ERROR: Failed to install PyInstaller.
        pause
        exit /b 1
    )
)
echo [OK] PyInstaller available.
echo.

:: tree-sitter-language-pack ships ~300 precompiled grammars as package data
:: that PyInstaller's import scanner can't discover by itself — without
:: --collect-all, the packaged exe would silently lose code-identifier
:: renaming. Only added when the [code] extra is actually installed.
set CODE_COLLECT=
python -c "import tree_sitter_language_pack" 2>nul
if not errorlevel 1 (
    set CODE_COLLECT=--collect-all tree_sitter_language_pack --collect-all tree_sitter
    echo [OK] tree-sitter-language-pack found - identifier renaming will be bundled.
) else (
    echo NOTE: tree-sitter-language-pack not installed - exes will skip code-identifier renaming.
    echo       Run "pip install -e .[code]" then re-run this script to include it.
)
echo.

set UI_AVAILABLE=1
python -c "import PySide6" 2>nul
if errorlevel 1 set UI_AVAILABLE=0

:: ---- Build CLI exe ----
echo Building dist\codemangler-cli.exe ...
pyinstaller --noconfirm --clean --onefile --name codemangler-cli %CODE_COLLECT% app\main.py
if errorlevel 1 (
    echo ERROR: CLI build failed.
    pause
    exit /b 1
)
echo [OK] dist\codemangler-cli.exe
echo.

:: ---- Build UI exe ----
if "%UI_AVAILABLE%"=="1" (
    echo Building dist\CodeMangler.exe ...
    REM --add-data bundles app\resources\ (logo + app icon) into the exe so
    REM the About tab's image and the window icon still resolve when frozen
    REM (app/ui/resource_paths.py looks under sys._MEIPASS\app\resources at
    REM runtime). --icon sets the .exe file's own icon (Explorer/taskbar).
    pyinstaller --noconfirm --clean --onefile --windowed --name CodeMangler ^
        --add-data "app\resources;app\resources" ^
        --icon "app\resources\code_mangler_app_icon.ico" ^
        %CODE_COLLECT% app\ui\run_ui.py
    if errorlevel 1 (
        echo ERROR: UI build failed.
        pause
        exit /b 1
    )
    echo [OK] dist\CodeMangler.exe
) else (
    echo SKIPPED: PySide6 not installed - run "pip install -e .[ui]" then re-run this
    echo          script to also build the desktop UI exe.
)

echo.
echo === Build complete ===
echo Executables are in the dist\ folder. They are large (single-file builds
echo bundling the Python runtime and, if present, ~300 tree-sitter grammars).
echo.
pause
endlocal
