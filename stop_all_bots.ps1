# Stop all bot instances listening on target ports
$ports = 5001, 5002, 5003

foreach ($port in $ports) {
    Write-Host "Checking port $port..." -ForegroundColor Yellow
    $connections = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
    if ($connections) {
        foreach ($conn in $connections) {
            $pid = $conn.OwningProcess
            if ($pid -gt 0) {
                Write-Host "Stopping process $pid on port $port..." -ForegroundColor Red
                Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
            }
        }
    } else {
        Write-Host "No process found on port $port." -ForegroundColor Gray
    }
}

Write-Host "All specified bots stopped." -ForegroundColor Green
