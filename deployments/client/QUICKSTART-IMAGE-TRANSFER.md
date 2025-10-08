# Quick Start: Build and Transfer Docker Image

**Use Case**: Build Docker image on Linux, transfer to Windows workstation for MCP client deployment.

## On Linux Build Machine

```bash
cd /path/to/mcpragcrawl4ai/deployments/client

# Build and export Docker image
./build-image.sh

# This creates: crawl4ai-rag-client.tar (~200-300MB)
```

## Transfer to Windows

**Copy these files to your Windows workstation:**
1. `crawl4ai-rag-client.tar` (Docker image)
2. `.env_template.txt` (config template)
3. `docker-compose.yml` (container setup)
4. `deploy-on-windows.ps1` (deployment script)

**Methods**: USB drive, SCP, network share, cloud storage

## On Windows Workstation

**Open PowerShell in the directory with transferred files:**

```powershell
# Run deployment script
.\deploy-on-windows.ps1

# Follow prompts to:
# - Load Docker image
# - Configure .env
# - Start container
```

**Configure Claude Desktop:**

Edit: `%APPDATA%\Claude\claude_desktop_config.json`

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

**Restart Claude Desktop** - Tools will appear!

---

**See [IMAGE-TRANSFER.md](IMAGE-TRANSFER.md) for detailed instructions and troubleshooting.**
