# Crawl4AI RAG MCP Client Setup Script for Windows PowerShell
# This script automates the client deployment setup process

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Crawl4AI RAG MCP Client Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if Docker is installed and running
Write-Host "[1/6] Checking Docker Desktop..." -ForegroundColor Yellow
try {
    $dockerVersion = docker --version 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Docker not found"
    }
    Write-Host "  ✓ Docker is installed: $dockerVersion" -ForegroundColor Green

    # Check if Docker daemon is running
    docker ps 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  ✗ Docker Desktop is not running!" -ForegroundColor Red
        Write-Host "    Please start Docker Desktop and wait for it to be ready, then run this script again." -ForegroundColor Yellow
        exit 1
    }
    Write-Host "  ✓ Docker Desktop is running" -ForegroundColor Green
}
catch {
    Write-Host "  ✗ Docker is not installed or not in PATH" -ForegroundColor Red
    Write-Host "    Please install Docker Desktop for Windows from:" -ForegroundColor Yellow
    Write-Host "    https://www.docker.com/products/docker-desktop" -ForegroundColor Cyan
    exit 1
}

Write-Host ""

# Check if .env already exists
Write-Host "[2/6] Checking configuration..." -ForegroundColor Yellow
if (Test-Path ".env") {
    Write-Host "  ! Configuration file .env already exists" -ForegroundColor Yellow
    $overwrite = Read-Host "  Do you want to overwrite it? (y/N)"
    if ($overwrite -ne "y" -and $overwrite -ne "Y") {
        Write-Host "  Keeping existing .env file" -ForegroundColor Green
        $useExisting = $true
    }
    else {
        Write-Host "  Creating new .env file from template..." -ForegroundColor Green
        Copy-Item ".env_template.txt" ".env" -Force
        $useExisting = $false
    }
}
else {
    Write-Host "  Creating .env file from template..." -ForegroundColor Green
    Copy-Item ".env_template.txt" ".env"
    $useExisting = $false
}

Write-Host ""

# Get server details from user if creating new config
if (-not $useExisting) {
    Write-Host "[3/6] Collecting server information..." -ForegroundColor Yellow
    Write-Host "  Please enter your remote server details:" -ForegroundColor Cyan
    Write-Host ""

    # Get server URL
    $serverUrl = Read-Host "  Remote server URL (e.g., http://192.168.10.50:8080)"
    while ([string]::IsNullOrWhiteSpace($serverUrl)) {
        Write-Host "    Server URL is required!" -ForegroundColor Red
        $serverUrl = Read-Host "  Remote server URL"
    }

    # Get API key
    $apiKey = Read-Host "  Remote API key (from server administrator)"
    while ([string]::IsNullOrWhiteSpace($apiKey)) {
        Write-Host "    API key is required!" -ForegroundColor Red
        $apiKey = Read-Host "  Remote API key"
    }

    # Get optional blocked domain keyword
    $keyword = Read-Host "  Blocked domain keyword (optional, press Enter to skip)"
    if ([string]::IsNullOrWhiteSpace($keyword)) {
        $keyword = "<YourKeyword>"
    }

    Write-Host ""
    Write-Host "  Updating .env file with your settings..." -ForegroundColor Green

    # Update .env file with user's values
    $envContent = Get-Content ".env" -Raw
    $envContent = $envContent -replace "REMOTE_API_URL=http://192.168.10.50:8080", "REMOTE_API_URL=$serverUrl"
    $envContent = $envContent -replace "REMOTE_API_KEY=<APIKEY>", "REMOTE_API_KEY=$apiKey"
    $envContent = $envContent -replace "BLOCKED_DOMAIN_KEYWORD=<YourKeyword>", "BLOCKED_DOMAIN_KEYWORD=$keyword"
    $envContent | Set-Content ".env" -NoNewline

    Write-Host "  ✓ Configuration saved to .env" -ForegroundColor Green
}
else {
    Write-Host "[3/6] Using existing configuration" -ForegroundColor Yellow
}

Write-Host ""

# Test server connectivity
Write-Host "[4/6] Testing server connectivity..." -ForegroundColor Yellow
$envVars = Get-Content ".env" | Where-Object { $_ -match "^REMOTE_API_URL=" }
if ($envVars) {
    $serverUrl = ($envVars -split "=", 2)[1]
    $healthUrl = "$serverUrl/health"

    try {
        Write-Host "  Testing connection to $healthUrl..." -ForegroundColor Cyan
        $response = Invoke-WebRequest -Uri $healthUrl -TimeoutSec 5 -UseBasicParsing
        if ($response.StatusCode -eq 200) {
            Write-Host "  ✓ Server is reachable and healthy" -ForegroundColor Green
        }
        else {
            Write-Host "  ! Server returned status code: $($response.StatusCode)" -ForegroundColor Yellow
        }
    }
    catch {
        Write-Host "  ✗ Cannot reach server: $($_.Exception.Message)" -ForegroundColor Red
        Write-Host "    This may be normal if the server is not running yet." -ForegroundColor Yellow
        Write-Host "    You can continue, but verify server connectivity before using the client." -ForegroundColor Yellow
    }
}

Write-Host ""

# Stop any existing containers
Write-Host "[5/6] Stopping any existing client containers..." -ForegroundColor Yellow
docker compose down 2>&1 | Out-Null
Write-Host "  ✓ Cleanup complete" -ForegroundColor Green

Write-Host ""

# Build and start the client
Write-Host "[6/6] Building and starting client container..." -ForegroundColor Yellow
Write-Host "  This may take a few minutes on first run..." -ForegroundColor Cyan

$buildOutput = docker compose up -d --build 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ✗ Failed to start client container" -ForegroundColor Red
    Write-Host "  Error output:" -ForegroundColor Yellow
    Write-Host $buildOutput
    exit 1
}

Write-Host "  ✓ Client container started successfully" -ForegroundColor Green

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Setup Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Show container status
Write-Host "Container Status:" -ForegroundColor Yellow
docker compose ps

Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Cyan
Write-Host "  1. Configure your LLM (Claude Desktop, LM Studio) to use the MCP server" -ForegroundColor White
Write-Host "     See SETUP.md for detailed instructions" -ForegroundColor White
Write-Host ""
Write-Host "  2. For Claude Desktop (Windows), edit:" -ForegroundColor White
Write-Host "     %APPDATA%\Claude\claude_desktop_config.json" -ForegroundColor Cyan
Write-Host ""
Write-Host "     Add this configuration:" -ForegroundColor White
Write-Host '     {' -ForegroundColor Gray
Write-Host '       "mcpServers": {' -ForegroundColor Gray
Write-Host '         "crawl4ai-rag": {' -ForegroundColor Gray
Write-Host '           "command": "docker",' -ForegroundColor Gray
Write-Host '           "args": ["exec", "-i", "crawl4ai-rag-client", "python", "-m", "core.rag_processor"]' -ForegroundColor Gray
Write-Host '         }' -ForegroundColor Gray
Write-Host '       }' -ForegroundColor Gray
Write-Host '     }' -ForegroundColor Gray
Write-Host ""
Write-Host "  3. Restart your LLM application" -ForegroundColor White
Write-Host ""

Write-Host "Useful Commands:" -ForegroundColor Cyan
Write-Host "  View logs:    docker compose logs -f" -ForegroundColor White
Write-Host "  Stop client:  docker compose down" -ForegroundColor White
Write-Host "  Start client: docker compose up -d" -ForegroundColor White
Write-Host "  Check status: docker compose ps" -ForegroundColor White
Write-Host ""

Write-Host "Documentation:" -ForegroundColor Cyan
Write-Host "  Detailed setup guide:    SETUP.md" -ForegroundColor White
Write-Host "  Configuration reference: .env_template.txt" -ForegroundColor White
Write-Host ""
