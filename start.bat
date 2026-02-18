@echo off
setlocal

rem Always run from this script directory
pushd "%~dp0"

set "VENV_DIR=.venv"

if not exist "%VENV_DIR%\\Scripts\\activate.bat" (
    echo Virtual environment not found.
    echo First run: setup.bat
    popd
    pause
    exit /b 1
)

echo Activating virtual environment...
call "%VENV_DIR%\\Scripts\\activate.bat"

echo Running app...
python main.py

popd
pause
