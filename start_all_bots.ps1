# Start all bot instances with proper log redirection
Write-Host "Starting ProfitBot RSD on port 5001..." -ForegroundColor Cyan
Start-Process python -ArgumentList "main.py --profile rsd --port 5001 --strategy rsd" -NoNewWindow -RedirectStandardOutput "bot_rsd.log" -RedirectStandardError "bot_rsd_err.log"

Write-Host "Starting ProfitBot Smart Money on port 5002..." -ForegroundColor Cyan
Start-Process python -ArgumentList "main.py --profile smart_money --port 5002 --strategy smart_money" -NoNewWindow -RedirectStandardOutput "bot_smart.log" -RedirectStandardError "bot_smart_err.log"

Write-Host "Starting ProfitBot Three Dollar on port 5003..." -ForegroundColor Cyan
Start-Process python -ArgumentList "main.py --profile three_dollar --port 5003 --strategy smart_money --capital 3.00" -NoNewWindow -RedirectStandardOutput "bot_debug.log" -RedirectStandardError "bot_debug_err.log"

Write-Host "All bots started! Check logs for details." -ForegroundColor Green
Write-Host "Dashboards available at:"
Write-Host " - http://localhost:5001 (RSD)"
Write-Host " - http://localhost:5002 (Smart Money)"
Write-Host " - http://localhost:5003 (Three Dollar)"
