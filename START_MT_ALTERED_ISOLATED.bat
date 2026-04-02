@echo off
title Multi-Timeframe Altered - Isolated Terminal
color 0C
echo.
echo ============================================
echo    Multi-Timeframe Altered - Terminal 3
echo ============================================
echo 🚀 Starting Altered Multi-Timeframe Strategy...
echo 📊 Relaxed config: ADX 15, Stoch 30/70
echo 🎯 Goal: More frequent trades
echo 🌐 Dashboard: http://localhost:5008
echo 🔒 Profile: Multi-Timeframe-Altered
echo.
echo 🔍 Opening in isolated terminal window...
start "Multi-Timeframe Altered" cmd /k python run_altered_multitimeframe.py
echo.
echo ✅ Altered MT bot started in isolated terminal
echo 💰 Keep this terminal open for monitoring
pause
