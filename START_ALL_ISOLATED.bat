@echo off
title Launch All Trading Bots - Isolated
color 0E
echo.
echo ============================================
echo    🚀 Launch All 3 Trading Bots
echo ============================================
echo 🎯 Each bot opens in separate terminal window
echo 📊 All dashboards will open automatically
echo.
echo 🔍 Starting Scalper30 Optimized (Terminal 1)...
start "Scalper30 Optimized" cmd /k python run_optimized_bot.py
timeout /t 2 >nul

echo 🔍 Starting Multi-Timeframe Original (Terminal 2)...
start "Multi-Timeframe Original" cmd /k python run_original_multitimeframe.py
timeout /t 2 >nul

echo 🔍 Starting Multi-Timeframe Altered (Terminal 3)...
start "Multi-Timeframe Altered" cmd /k python run_altered_multitimeframe.py
timeout /t 2 >nul

echo.
echo ✅ All 3 bots started in isolated terminals!
echo.
echo 🌐 Dashboard Links:
echo    🔹 Scalper30: http://localhost:5003
echo    🔹 Original MT: http://localhost:5007
echo    🔹 Altered MT: http://localhost:5008
echo.
echo 💡 Each terminal window shows its bot's logs
echo 🎮 Open all 3 dashboards for comparison
echo.
echo Press any key to exit...
pause >nul
