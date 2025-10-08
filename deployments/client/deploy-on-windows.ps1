# Crawl4AI RAG MCP Client - Windows Deployment Script
# Use this script on your Windows workstation after transferring the Docker image

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Crawl4AI RAG MCP Client - Windows Deploy" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Configuration
$IMAGE_FILE = "crawl4ai-rag-client.tar"
$IMAGE_NAME = "crawl4ai-rag-client:latest"

# Check if Docker is installed and running
Write-Host "[1/5] Checking Docker Desktop..." -ForegroundColor Yellow
try {
    $dockerVersion = docker --version 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Docker not found"
    }
    Write-Host "  [OK] Docker is installed: $dockerVersion" -ForegroundColor Green

    # Check if Docker daemon is running
    docker ps 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  [X] Docker Desktop is not running!" -ForegroundColor Red
        Write-Host "    Please start Docker Desktop and wait for it to be ready." -ForegroundColor Yellow
        exit 1
    }
    Write-Host "  [OK] Docker Desktop is running" -ForegroundColor Green
}
catch {
    Write-Host "  [X] Docker is not installed or not in PATH" -ForegroundColor Red
    Write-Host "    Please install Docker Desktop for Windows from:" -ForegroundColor Yellow
    Write-Host "    https://www.docker.com/products/docker-desktop" -ForegroundColor Cyan
    exit 1
}

Write-Host ""

# Check if image file exists
Write-Host "[2/5] Checking for Docker image file..." -ForegroundColor Yellow
if (-not (Test-Path $IMAGE_FILE)) {
    Write-Host "  [X] Docker image file not found: $IMAGE_FILE" -ForegroundColor Red
    Write-Host ""
    Write-Host "  Please ensure you have transferred the following files:" -ForegroundColor Yellow
    Write-Host "    - $IMAGE_FILE (Docker image)" -ForegroundColor White
    Write-Host "    - .env_template.txt (configuration)" -ForegroundColor White
    Write-Host "    - docker-compose.yml (orchestration)" -ForegroundColor White
    Write-Host "    - deploy-on-windows.ps1 (this script)" -ForegroundColor White
    exit 1
}

$imageSize = (Get-Item $IMAGE_FILE).Length / 1MB
$imageSizeRounded = [math]::Round($imageSize, 2)
Write-Host ("  [OK] Found image file: " + $IMAGE_FILE + " (" + $imageSizeRounded + " MB)") -ForegroundColor Green

Write-Host ""

# Load the Docker image
Write-Host "[3/5] Loading Docker image..." -ForegroundColor Yellow
Write-Host "  This may take a few minutes..." -ForegroundColor Cyan

$loadOutput = docker load -i $IMAGE_FILE 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "  [X] Failed to load Docker image" -ForegroundColor Red
    Write-Host "  Error: $loadOutput" -ForegroundColor Yellow
    exit 1
}

Write-Host "  [OK] Docker image loaded successfully" -ForegroundColor Green

Write-Host ""

# Verify the image
Write-Host "[4/5] Verifying Docker image..." -ForegroundColor Yellow
$images = docker images crawl4ai-rag-client --format "{{.Repository}}:{{.Tag}}" 2>&1
if ($images -match "crawl4ai-rag-client") {
    Write-Host "  [OK] Image verified: $images" -ForegroundColor Green
}
else {
    Write-Host "  [X] Image verification failed" -ForegroundColor Red
    exit 1
}

Write-Host ""

# Check for configuration
Write-Host "[5/5] Checking configuration..." -ForegroundColor Yellow

if (-not (Test-Path ".env_template.txt")) {
    Write-Host "  ! Warning: .env_template.txt not found" -ForegroundColor Yellow
    Write-Host "    You'll need to create .env manually" -ForegroundColor Yellow
}
elseif (-not (Test-Path ".env")) {
    Write-Host "  Creating .env from template..." -ForegroundColor Cyan
    Copy-Item ".env_template.txt" ".env"
    Write-Host "  [OK] Created .env file" -ForegroundColor Green
    Write-Host ""
    Write-Host "  [!] IMPORTANT: Edit .env with your server details!" -ForegroundColor Yellow
    $edit = Read-Host "  Open .env in Notepad now? (Y/n)"
    if ($edit -ne "n" -and $edit -ne "N") {
        notepad .env
    }
}
else {
    Write-Host "  [OK] Configuration file .env exists" -ForegroundColor Green
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Deployment Ready!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Show what needs to be configured
Write-Host "Before starting the client:" -ForegroundColor Yellow
Write-Host ""
Write-Host "1. Configure .env file (if not done yet):" -ForegroundColor White
Write-Host "   notepad .env" -ForegroundColor Cyan
Write-Host ""
Write-Host "   Required settings:" -ForegroundColor White
Write-Host "   - IS_SERVER=false" -ForegroundColor Gray
Write-Host "   - REMOTE_API_URL=http://YOUR_SERVER_IP:8080" -ForegroundColor Gray
Write-Host "   - REMOTE_API_KEY=your_api_key_from_server" -ForegroundColor Gray
Write-Host ""

Write-Host "2. Test server connectivity:" -ForegroundColor White
Write-Host "   Invoke-WebRequest -Uri 'http://YOUR_SERVER_IP:8080/health'" -ForegroundColor Cyan
Write-Host ""

Write-Host "3. Start the client:" -ForegroundColor White
Write-Host "   docker compose up -d" -ForegroundColor Cyan
Write-Host ""

Write-Host "4. Configure Claude Desktop:" -ForegroundColor White
Write-Host "   Edit: %APPDATA%\Claude\claude_desktop_config.json" -ForegroundColor Cyan
Write-Host ""
Write-Host "   Add this configuration:" -ForegroundColor White
Write-Host "   {" -ForegroundColor Gray
Write-Host "     `"mcpServers`": {" -ForegroundColor Gray
Write-Host "       `"crawl4ai-rag`": {" -ForegroundColor Gray
Write-Host "         `"command`": `"docker`"," -ForegroundColor Gray
Write-Host "         `"args`": [`"exec`", `"-i`", `"crawl4ai-rag-client`", `"python`", `"-m`", `"core.rag_processor`"]" -ForegroundColor Gray
Write-Host "       }" -ForegroundColor Gray
Write-Host "     }" -ForegroundColor Gray
Write-Host "   }" -ForegroundColor Gray
Write-Host ""

Write-Host "5. Restart Claude Desktop" -ForegroundColor White
Write-Host ""

Write-Host "Useful Commands:" -ForegroundColor Cyan
Write-Host "  Start:  docker compose up -d" -ForegroundColor White
Write-Host "  Stop:   docker compose down" -ForegroundColor White
Write-Host "  Logs:   docker compose logs -f" -ForegroundColor White
Write-Host "  Status: docker compose ps" -ForegroundColor White
Write-Host ""

$startNow = Read-Host "Start the client now? (y/N)"
if ($startNow -eq "y" -or $startNow -eq "Y") {
    Write-Host ""
    Write-Host "Starting client container..." -ForegroundColor Yellow
    docker compose up -d

    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Host "[OK] Client is running!" -ForegroundColor Green
        Write-Host ""
        docker compose ps
    }
    else {
        Write-Host ""
        Write-Host "[X] Failed to start client" -ForegroundColor Red
        Write-Host "Check logs with: docker compose logs" -ForegroundColor Yellow
    }
}
else {
    Write-Host ""
    Write-Host "To start later, run: docker compose up -d" -ForegroundColor Cyan
}

Write-Host ""
