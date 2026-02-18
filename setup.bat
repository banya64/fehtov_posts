@echo off
setlocal

rem Always run from this script directory
pushd "%~dp0"

set "VENV_DIR=.venv"

if not exist "%VENV_DIR%\" (
    echo Creating virtual environment...
    py -3.12 -m venv "%VENV_DIR%"
)

echo Activating virtual environment...
call "%VENV_DIR%\Scripts\activate.bat"

echo Installing requirements...
python -m pip install -r requirements.txt

echo Running app...
python main.py

popd
pause
