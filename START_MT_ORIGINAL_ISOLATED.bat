@echo off
title Multi-Timeframe Original - Isolated Terminal
color 0A
echo.
echo ============================================
echo    Multi-Timeframe Original - Terminal 2
echo ============================================
echo 🚀 Starting Original Multi-Timeframe Strategy...
echo 📊 Your exact config: ADX 25, Stoch 20/80
echo 💰 Expected profit: $2000+
echo 🌐 Dashboard: http://localhost:5007
echo 🔒 Profile: Multi-Timeframe-Original
echo.
echo 🔍 Opening in isolated terminal window...
start "Multi-Timeframe Original" cmd /k python run_original_multitimeframe.py
echo.
echo ✅ Original MT bot started in isolated terminal
echo 💰 Keep this terminal open for monitoring
pause
