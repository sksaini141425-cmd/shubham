@echo off
title Multi-Timeframe Trading Bot
color 0A
echo.
echo ============================================
echo    Multi-Timeframe Trading Bot Launcher
echo ============================================
echo.
echo 🚀 Starting Advanced Multi-Timeframe Bot...
echo 📊 Features: Multi-Timeframe Analysis
echo ⚡ Dynamic Risk Management
echo 🎯 Optimized for BTCUSDT
echo.
echo 🔍 Checking dependencies...
python -c "import bot.data_loader, bot.strategy_multitimeframe, bot.signal_intelligence; print('✅ All dependencies OK')"
if errorlevel 1 (
    echo ❌ Missing dependencies - Please install requirements
    pause
    exit /b 1
)
echo.
echo 🔧 Starting bot with isolated environment...
echo 🌐 Dashboard will open automatically
echo.
python launch_multitimeframe_bot.py
if errorlevel 1 (
    echo ❌ Bot failed to start
    pause
    exit /b 1
)
echo.
echo ✅ Bot launcher completed
pause
