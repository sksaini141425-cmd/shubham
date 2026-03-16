@echo off
setlocal enabledelayedexpansion

echo ============================================================
echo 🚀 PROFITBOT PRO - SCALPER70 LAUNCHER
echo ============================================================
echo.
echo Please select a mode:
echo [1] Local Simulation (Safe, local only, no API needed)
echo [2] Bybit Testnet (Shows trades in your Bybit account)
echo.
set /p choice="Enter choice (1 or 2): "

echo.
echo ============================================================
echo 🛠️  Strategy: Scalper70 (70%% Winrate Target)
echo ⚡ Leverage: 50x
echo 📊 Dashboard: http://localhost:5000
echo ============================================================
echo.

:: Check for python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Python not found! Please install Python 3.10+ and try again.
    pause
    exit /b
)

:: Install requirements
echo 📦 Checking dependencies...
pip install -r requirements.txt --quiet

if "%choice%"=="1" (
    echo 🚀 Starting LOCAL SIMULATION...
    python run_local_sim.py
) else if "%choice%"=="2" (
    echo 🚀 Starting BYBIT TESTNET MODE...
    python run_bybit_testnet.py
) else (
    echo ❌ Invalid choice. Please run the bat file again.
)

pause
