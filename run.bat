@echo off
setlocal EnableDelayedExpansion

:: Activate virtual environment
if not exist ".venv\Scripts\activate.bat" (
    echo ERROR: Virtual environment not found. Run setup.bat first.
    exit /b 1
)
call .venv\Scripts\activate.bat

:: Pass all arguments through to codemangler
codemangler %*
