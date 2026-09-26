@echo off
REM One-click launcher for Twitch Drops Miner.
REM First run: creates the "env" virtual environment and installs requirements.
REM Every run after that: launches the miner straight away.
REM Extra arguments are passed to the app, e.g.: start.bat --tray
REM Use "--console" as the first argument to see the console output: start.bat --console

set "dirpath=%~dp0"
if "%dirpath:~-1%" == "\" set "dirpath=%dirpath:~0,-1%"

REM Find a Python executable for the first-time setup
set "pyexe="
py -3 --version > nul 2>&1
if %errorlevel% EQU 0 set "pyexe=py -3"
if defined pyexe goto :python_found
python --version > nul 2>&1
if %errorlevel% EQU 0 set "pyexe=python"
:python_found

REM Create the virtual environment and install requirements on the first run
if exist "%dirpath%\env\scripts\python.exe" goto :run

echo:
if not defined pyexe (
    echo No Python executable found in PATH!
    echo Please install Python 3.10 or newer first: https://www.python.org/downloads/
    echo:
    pause
    exit /b 1
)
echo First run detected - setting up the environment...
%pyexe% -m venv "%dirpath%\env"
if %errorlevel% NEQ 0 (
    echo:
    echo Failed to create the virtual environment!
    echo:
    pause
    exit /b 1
)
echo Installing requirements, this may take a few minutes...
"%dirpath%\env\scripts\python" -m pip install -U pip
"%dirpath%\env\scripts\python" -m pip install -r "%dirpath%\requirements.txt"
if %errorlevel% NEQ 0 (
    echo:
    echo Failed to install requirements - delete the "env" folder and try again.
    echo:
    pause
    exit /b 1
)
echo:
echo Environment setup completed successfully.
echo:

:run
REM Default to the windowless pythonw.exe; "--console" keeps the console window open
set "exepath=%dirpath%\env\scripts\pythonw.exe"
if /i "%~1"=="--console" (
    set "exepath=%dirpath%\env\scripts\python.exe"
    shift
)

start "TwitchDropsMiner" "%exepath%" "%dirpath%\main.py" %1 %2 %3 %4 %5 %6 %7 %8 %9
exit /b 0
