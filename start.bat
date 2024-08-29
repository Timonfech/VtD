@echo off
if not exist "venv\Scripts\activate.bat" (
    echo "Virtual environment not found."
) else (
REM Activate the virtual environment
call venv\Scripts\activate.bat
)

REM Check for required environment variables
setlocal
set "required_vars=data_source malware_destination fp_destination"
set "missing_vars="

for %%V in (%required_vars%) do (
    if not defined %%V (
        set "missing_vars=1"
        echo Warning: Environment variable %%V is not set. It is recommended to set it for proper functionality.
    )
)

if defined missing_vars (
    echo.
    echo Please consider setting these variables before running the script.
)

REM Check if PowerShell is available
where powershell >nul 2>nul
if %errorlevel% == 0 (
    REM Run the Python script in PowerShell
    powershell -Command "python %~dp0main.py"
) else (
    REM Fallback to command prompt
    python %~dp0main.py
)

pause
