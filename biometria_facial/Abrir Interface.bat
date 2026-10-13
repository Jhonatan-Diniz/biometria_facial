@echo off
setlocal
cd /d "%~dp0"

if exist "%~dp0..\.venv\Scripts\python.exe" (
    "%~dp0..\.venv\Scripts\python.exe" "%~dp0main.py"
    goto fim
)

if exist "%~dp0venv\Scripts\python.exe" (
    "%~dp0venv\Scripts\python.exe" "%~dp0main.py"
    goto fim
)

where py >nul 2>nul
if not errorlevel 1 (
    py -3.11 "%~dp0main.py"
    goto fim
)

where python >nul 2>nul
if not errorlevel 1 (
    python "%~dp0main.py"
    goto fim
)

echo Python nao foi encontrado. Instale o Python 3.11 ou crie o ambiente .venv.

:fim
echo.
pause
