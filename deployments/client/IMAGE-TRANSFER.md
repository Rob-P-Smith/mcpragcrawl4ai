# Building and Transferring Docker Image for Windows Deployment

This guide explains how to build the Docker image on your Linux build machine and transfer it to your Windows workstation for deployment.

## Overview

**Build Machine (Linux)**: Build the Docker image and export it to a `.tar` file
**Transfer**: Move the `.tar` file to your Windows workstation
**Windows Workstation**: Load the image and deploy the MCP client

## Step 1: Build the Docker Image (Linux)

On your Linux machine where you have the project:

```bash
cd /path/to/mcpragcrawl4ai/deployments/client

# Run the build script
./build-image.sh
```

This will:
1. Build the Docker image (`crawl4ai-rag-client:latest`)
2. Export it to `crawl4ai-rag-client.tar` (~200-300MB)
3. Display instructions for transfer

**Output files in `deployments/client/`:**
- `crawl4ai-rag-client.tar` - Docker image (the main file you need)

## Step 2: Transfer Files to Windows

You need to transfer these files from `deployments/client/` to your Windows workstation:

### Required Files:
1. **`crawl4ai-rag-client.tar`** - Docker image (~200-300MB)
2. **`.env_template.txt`** - Configuration template
3. **`docker-compose.yml`** - Container orchestration
4. **`deploy-on-windows.ps1`** - Windows deployment script

### Optional (for reference):
5. **`SETUP.md`** - Detailed setup guide
6. **`README.md`** - Overview and documentation

### Transfer Methods:

#### Option A: SCP (if you have SSH access to Windows)
```bash
# From Linux machine
cd deployments/client

scp crawl4ai-rag-client.tar user@windows-pc:/path/to/destination/
scp .env_template.txt user@windows-pc:/path/to/destination/
scp docker-compose.yml user@windows-pc:/path/to/destination/
scp deploy-on-windows.ps1 user@windows-pc:/path/to/destination/
```

#### Option B: Network Share
```bash
# Mount Windows share on Linux
sudo mount -t cifs //windows-pc/SharedFolder /mnt/share -o username=youruser

# Copy files
cp crawl4ai-rag-client.tar /mnt/share/
cp .env_template.txt /mnt/share/
cp docker-compose.yml /mnt/share/
cp deploy-on-windows.ps1 /mnt/share/
```

#### Option C: USB Drive
```bash
# Copy to USB drive
cp crawl4ai-rag-client.tar /media/usb/
cp .env_template.txt /media/usb/
cp docker-compose.yml /media/usb/
cp deploy-on-windows.ps1 /media/usb/

# Then physically move USB to Windows PC
```

#### Option D: Cloud Storage (Dropbox, Google Drive, etc.)
Upload files to cloud storage and download on Windows.

## Step 3: Deploy on Windows

On your Windows workstation:

### Prerequisites
- **Docker Desktop for Windows** installed and running
- Files transferred to a directory (e.g., `C:\mcprag-client\`)

### Automated Deployment

1. Open **PowerShell** as Administrator
2. Navigate to the directory with your files:
   ```powershell
   cd C:\mcprag-client\
   ```

3. Run the deployment script:
   ```powershell
   .\deploy-on-windows.ps1
   ```

The script will:
- Check Docker Desktop is running
- Load the Docker image
- Create `.env` from template
- Prompt you to configure server settings
- Optionally start the container

### Manual Deployment

If you prefer manual steps:

#### 1. Load the Docker Image
```powershell
docker load -i crawl4ai-rag-client.tar
```

#### 2. Verify the Image
```powershell
docker images crawl4ai-rag-client
```

Should show:
```
REPOSITORY              TAG       IMAGE ID       CREATED        SIZE
crawl4ai-rag-client     latest    abc123def456   X hours ago    XXX MB
```

#### 3. Configure Environment
```powershell
# Create .env from template
Copy-Item .env_template.txt .env

# Edit configuration
notepad .env
```

**Required settings in `.env`:**
```bash
IS_SERVER=false
REMOTE_API_URL=http://YOUR_SERVER_IP:8080
REMOTE_API_KEY=your_api_key_from_server
```

#### 4. Test Server Connectivity
```powershell
Invoke-WebRequest -Uri "http://YOUR_SERVER_IP:8080/health"
```

Should return JSON with `"status":"healthy"`

#### 5. Start the Container
```powershell
docker compose up -d
```

#### 6. Verify Container is Running
```powershell
docker compose ps
```

Should show `crawl4ai-rag-client` with status `Up`

## Step 4: Configure Your LLM

### Claude Desktop

1. Find the configuration file:
   - Windows: `%APPDATA%\Claude\claude_desktop_config.json`
   - Full path: `C:\Users\YourUsername\AppData\Roaming\Claude\claude_desktop_config.json`

2. Edit the file (create if it doesn't exist):
   ```json
   {
     "mcpServers": {
       "crawl4ai-rag": {
         "command": "docker",
         "args": ["exec", "-i", "crawl4ai-rag-client", "python", "-m", "core.rag_processor"]
       }
     }
   }
   ```

3. Restart Claude Desktop

4. Verify tools are available - you should see tools like:
   - crawl_url
   - crawl_and_remember
   - search_memory
   - etc.

## Troubleshooting

### Image Load Fails

**Error**: `Error response from daemon: open ... no such file or directory`

**Solution**:
- Verify file is not corrupted: `docker load -i crawl4ai-rag-client.tar`
- Check file size matches what was built
- Re-transfer if size doesn't match

### Container Won't Start

**Check logs:**
```powershell
docker compose logs
```

**Common issues:**
- `.env` file missing or misconfigured
- `REMOTE_API_URL` incorrect
- `REMOTE_API_KEY` doesn't match server

### Can't Connect to Server

**Test connectivity:**
```powershell
Test-NetConnection -ComputerName YOUR_SERVER_IP -Port 8080
```

**Check:**
- Server is running
- Firewall allows port 8080
- VPN is connected (if required)
- Server IP is correct in `.env`

### Claude Desktop Doesn't See Tools

**Verify container:**
```powershell
docker ps --filter "name=crawl4ai-rag-client"
```

**Check container name matches config:**
- Config should reference: `crawl4ai-rag-client`
- Container name from `docker ps` should match

**Restart Claude Desktop** after changing config

**Check Claude Desktop logs:**
- Location: `%APPDATA%\Claude\logs\`

## Managing the Client

### Useful Commands

```powershell
# View logs
docker compose logs -f

# Stop container
docker compose down

# Start container
docker compose up -d

# Restart container
docker compose restart

# Check status
docker compose ps

# Update configuration and restart
docker compose down
notepad .env
docker compose up -d
```

### Updating the Image

To update to a new version:

1. Stop and remove old container:
   ```powershell
   docker compose down
   ```

2. Remove old image:
   ```powershell
   docker rmi crawl4ai-rag-client:latest
   ```

3. Transfer new `.tar` file from Linux build machine

4. Load new image:
   ```powershell
   docker load -i crawl4ai-rag-client.tar
   ```

5. Start with new image:
   ```powershell
   docker compose up -d
   ```

## Security Notes

- Keep `.env` file secure - it contains your API key
- Don't commit `.env` to version control
- Use HTTPS for production (`REMOTE_API_URL=https://...`)
- Restrict access to the Windows workstation
- Keep Docker Desktop updated

## File Sizes

Approximate file sizes for transfer:

- **crawl4ai-rag-client.tar**: ~200-300MB (Docker image)
- **.env_template.txt**: ~6KB
- **docker-compose.yml**: ~1KB
- **deploy-on-windows.ps1**: ~5KB

**Total transfer size**: ~200-300MB

## Architecture Reminder

```
┌─────────────────┐         ┌──────────────────┐         ┌──────────────────┐
│   Claude Desktop│ ◄─MCP─► │   Docker Client  │ ◄─HTTP─►│   Remote Server  │
│   (Windows PC)  │  stdio  │   (MCP→API)      │   REST  │   (Full RAG)     │
└─────────────────┘         └──────────────────┘         └──────────────────┘
                            crawl4ai-rag-client          Database + Crawl4AI
                            (Runs on Windows)            (Runs on Linux)
```

The client container runs on your Windows workstation and translates MCP calls from Claude Desktop into REST API calls to your remote Linux server.
