# REAL BINANCE TRADING SETUP GUIDE

## 🚨 SECURITY FIRST
1. Delete ALL exposed API keys from Binance immediately
2. Create NEW API keys with minimal permissions
3. Never share API keys in chat or public

## 📋 SETUP STEPS

### Step 1: Install Dependencies
```bash
pip install -r requirements_real.txt
```

### Step 2: Create Secure Environment File
```bash
# Copy the example file
cp .env.example .env

# Edit .env with your NEW SECURE keys
# NEVER commit .env to git or share it
```

### Step 3: Configure .env File
```
BINANCE_API_KEY=your_new_secure_api_key_here
BINANCE_SECRET=your_new_secure_secret_here
USE_TESTNET=true  # Start with testnet!
```

### Step 4: Test Connection
```python
from real_binance_exchange import RealBinanceExchange

# Test with testnet first
exchange = RealBinanceExchange(use_testnet=True)
balance = exchange.get_account_summary()
print(f"Balance: ${balance['balance']}")
```

### Step 5: Replace Fake Exchange in Main Bot
In `profitbot_dashboard.py`, replace the fake exchange:

```python
# OLD (Fake)
# from exchange import SimulatedExchange
# exchange = SimulatedExchange()

# NEW (Real)
from real_binance_exchange import RealBinanceExchange
exchange = RealBinanceExchange(use_testnet=True)  # Start safe
```

## 🧪 TESTNET FIRST
- Start with `use_testnet=True`
- Use Binance Testnet (no real money)
- Verify all functionality works
- Test with small amounts

## 🚀 GO LIVE (When Ready)
1. Change `use_testnet=False`
2. Start with very small amounts ($10-20)
3. Monitor closely
4. Scale up gradually

## ⚠️ IMPORTANT WARNINGS
- Real money trading involves risk
- Start with amounts you can afford to lose
- Monitor positions constantly
- Set proper stop losses
- Never leave unattended with large positions

## 🔧 TROUBLESHOOTING
- API Key errors: Check keys in .env file
- Permission errors: Ensure API keys have trading permissions
- Network errors: Check internet connection
- Balance errors: Ensure USDT balance in account

## 📞 SUPPORT
- Binance API documentation
- Testnet funding: https://testnet.binance.vision/
- Issues: Check logs for detailed error messages
