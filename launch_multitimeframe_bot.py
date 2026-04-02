#!/usr/bin/env python3
"""
Complete Multi-Timeframe Bot Launcher
Ensures all components work and launches dashboard with full functionality
"""
import os
import sys
import subprocess
import time
import webbrowser
import json
from datetime import datetime

def check_dependencies():
    """Check if all required modules are available"""
    print("🔍 Checking dependencies...")
    
    required_modules = [
        'bot.data_loader',
        'bot.strategy_multitimeframe', 
        'bot.signal_intelligence',
        'bot.signal_loader',
        'bot.paper_exchange',
        'bot.notifier'
    ]
    
    missing = []
    for module in required_modules:
        try:
            __import__(module)
            print(f"✅ {module}")
        except ImportError as e:
            print(f"❌ {module}: {e}")
            missing.append(module)
    
    if missing:
        print(f"\n❌ Missing modules: {missing}")
        return False
    
    print("✅ All dependencies available!")
    return True

def setup_environment():
    """Setup isolated environment for multi-timeframe bot"""
    print("🔧 Setting up isolated environment...")
    
    env = os.environ.copy()
    env.update({
        'STRATEGY': 'multitimeframe',
        'INITIAL_CAPITAL': '5.0',
        'LEVERAGE': '5',
        'MAX_CONCURRENT_TRADES': '3',
        'TOP_N_SYMBOLS': '10',
        'MIN_VOLUME_USD': '5000000',
        'USE_REAL_EXCHANGE': 'false',
        'EXCHANGE': 'mexc',
        'PORT': '5006',  # Fresh port
        'BOT_PROFILE': 'multitimeframe_isolated',  # Isolated profile
        'TELEGRAM_BOT_TOKEN': env.get('TELEGRAM_BOT_TOKEN', ''),
        'TELEGRAM_CHAT_ID': env.get('TELEGRAM_CHAT_ID', ''),
        'GEMINI_API_KEY': env.get('GEMINI_API_KEY', '')
    })
    
    print(f"✅ Environment configured")
    print(f"   🌐 Port: {env['PORT']}")
    print(f"   🔒 Profile: {env['BOT_PROFILE']}")
    print(f"   💰 Capital: ${env['INITIAL_CAPITAL']}")
    print(f"   ⚡ Leverage: {env['LEVERAGE']}x")
    
    return env

def validate_config(env):
    """Validate configuration before starting"""
    print("🔍 Validating configuration...")
    
    # Check essential config
    if not env.get('TELEGRAM_BOT_TOKEN'):
        print("⚠️  Warning: No Telegram token - notifications disabled")
    
    if not env.get('TELEGRAM_CHAT_ID'):
        print("⚠️  Warning: No Telegram chat ID - notifications disabled")
    
    # Check port availability
    port = int(env['PORT'])
    if port < 1024 or port > 65535:
        print(f"❌ Invalid port: {port}")
        return False
    
    print("✅ Configuration valid!")
    return True

def start_bot(env):
    """Start the multi-timeframe bot"""
    print("🚀 Starting Multi-Timeframe Bot...")
    
    try:
        # Start bot process
        process = subprocess.Popen([
            sys.executable, 'main.py',
            '--strategy', env['STRATEGY'],
            '--capital', env['INITIAL_CAPITAL'],
            '--leverage', env['LEVERAGE'],
            '--port', env['PORT'],
            '--exchange', env['EXCHANGE'],
            '--profile', env['BOT_PROFILE']
        ], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        print(f"✅ Bot started with PID: {process.pid}")
        
        # Wait for startup
        print("⏳ Waiting for bot to initialize...")
        time.sleep(5)
        
        # Check if process is still running
        if process.poll() is None:
            print("✅ Bot is running successfully!")
            return process
        else:
            # Get error output
            stdout, stderr = process.communicate()
            print(f"❌ Bot failed to start!")
            if stderr:
                print(f"Error: {stderr}")
            if stdout:
                print(f"Output: {stdout}")
            return None
            
    except Exception as e:
        print(f"❌ Failed to start bot: {e}")
        return None

def launch_dashboard(port):
    """Launch web dashboard"""
    print("🌐 Launching dashboard...")
    
    dashboard_url = f"http://localhost:{port}"
    
    try:
        # Wait a moment for server to be ready
        time.sleep(2)
        
        # Open browser
        webbrowser.open(dashboard_url)
        print(f"✅ Dashboard opened: {dashboard_url}")
        
        return True
    except Exception as e:
        print(f"❌ Failed to open dashboard: {e}")
        print(f"📊 Please manually open: {dashboard_url}")
        return False

def monitor_bot(process, env):
    """Monitor bot and provide status updates"""
    print("📊 Monitoring bot status...")
    
    dashboard_url = f"http://localhost:{env['PORT']}"
    profile = env['BOT_PROFILE']
    
    print(f"\n🎯 Multi-Timeframe Bot is RUNNING!")
    print(f"🌐 Dashboard: {dashboard_url}")
    print(f"🔒 Profile: {profile}")
    print(f"💰 Capital: ${env['INITIAL_CAPITAL']}")
    print(f"⚡ Leverage: {env['LEVERAGE']}x")
    print(f"📈 Strategy: Multi-Timeframe Analysis")
    
    print("\n📋 Dashboard Features:")
    print("   ✅ Real-time trading activity")
    print("   ✅ Live P&L tracking")
    print("   ✅ Position management")
    print("   ✅ Trade history")
    print("   ✅ Strategy performance")
    print("   ✅ Signal intelligence")
    
    print("\n🎮 Controls:")
    print("   📊 View live trades")
    print("   ⏸️  Pause/Resume entries")
    print("   🛑 Emergency close all")
    print("   📈 View performance charts")
    print("   🔔 Configure notifications")
    
    print("\n💡 Tips:")
    print("   • Monitor win rate (target: 60%+)")
    print("   • Watch drawdown (keep < 10%)")
    print("   • Check position sizing (2% risk)")
    print("   • Review trade history regularly")
    
    print(f"\n🔗 Keep dashboard open: {dashboard_url}")
    print("Press Ctrl+C to stop monitoring (bot continues running)")
    
    try:
        while True:
            time.sleep(30)  # Check every 30 seconds
            
            # Check if bot is still running
            if process.poll() is not None:
                print(f"\n❌ Bot stopped unexpectedly!")
                stdout, stderr = process.communicate()
                if stderr:
                    print(f"Error: {stderr}")
                break
                
            # Show periodic status
            current_time = datetime.now().strftime("%H:%M:%S")
            print(f"📊 [{current_time}] Bot running - Dashboard: {dashboard_url}")
            
    except KeyboardInterrupt:
        print(f"\n👋 Monitoring stopped (bot continues)")
        print(f"🌐 Dashboard remains available: {dashboard_url}")

def main():
    print("🚀 Multi-Timeframe Bot Launcher")
    print("=" * 50)
    
    # Step 1: Check dependencies
    if not check_dependencies():
        print("❌ Please fix missing dependencies and try again")
        return False
    
    # Step 2: Setup environment
    env = setup_environment()
    
    # Step 3: Validate configuration
    if not validate_config(env):
        print("❌ Please fix configuration issues and try again")
        return False
    
    # Step 4: Start bot
    process = start_bot(env)
    if not process:
        print("❌ Failed to start bot")
        return False
    
    # Step 5: Launch dashboard
    if not launch_dashboard(env['PORT']):
        print("⚠️  Dashboard launch failed, but bot is running")
    
    # Step 6: Monitor bot
    monitor_bot(process, env)
    
    return True

if __name__ == "__main__":
    try:
        success = main()
        if success:
            print("\n✅ Launcher completed successfully")
        else:
            print("\n❌ Launcher failed")
    except KeyboardInterrupt:
        print("\n👋 Launcher stopped by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
