#!/bin/bash
# Crawl4AI RAG MCP Client Setup Script for Linux/macOS

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}========================================"
echo "Crawl4AI RAG MCP Client Setup"
echo -e "========================================${NC}"
echo ""

# Check if Docker is installed
echo -e "${YELLOW}[1/6] Checking Docker...${NC}"
if ! command -v docker &> /dev/null; then
    echo -e "${RED}  ✗ Docker is not installed${NC}"
    echo -e "${YELLOW}    Please install Docker first:${NC}"
    echo -e "${CYAN}    https://docs.docker.com/get-docker/${NC}"
    exit 1
fi

if ! command -v docker compose &> /dev/null; then
    echo -e "${RED}  ✗ docker compose is not available${NC}"
    echo -e "${YELLOW}    Please install Docker Compose or upgrade Docker${NC}"
    exit 1
fi

echo -e "${GREEN}  ✓ Docker is installed: $(docker --version)${NC}"

# Check if Docker daemon is running
if ! docker ps &> /dev/null; then
    echo -e "${RED}  ✗ Docker daemon is not running${NC}"
    echo -e "${YELLOW}    Please start Docker and try again${NC}"
    exit 1
fi
echo -e "${GREEN}  ✓ Docker daemon is running${NC}"

echo ""

# Check if .env exists
echo -e "${YELLOW}[2/6] Checking configuration...${NC}"
if [ -f .env ]; then
    echo -e "${YELLOW}  ! Configuration file .env already exists${NC}"
    read -p "  Do you want to overwrite it? (y/N): " overwrite
    if [[ ! "$overwrite" =~ ^[Yy]$ ]]; then
        echo -e "${GREEN}  Keeping existing .env file${NC}"
        USE_EXISTING=true
    else
        echo -e "${GREEN}  Creating new .env file from template...${NC}"
        cp .env_template.txt .env
        USE_EXISTING=false
    fi
else
    echo -e "${GREEN}  Creating .env file from template...${NC}"
    cp .env_template.txt .env
    USE_EXISTING=false
fi

echo ""

# Get server details from user if creating new config
if [ "$USE_EXISTING" != "true" ]; then
    echo -e "${YELLOW}[3/6] Collecting server information...${NC}"
    echo -e "${CYAN}  Please enter your remote server details:${NC}"
    echo ""

    # Get server URL
    read -p "  Remote server URL (e.g., http://192.168.10.50:8080): " SERVER_URL
    while [ -z "$SERVER_URL" ]; do
        echo -e "${RED}    Server URL is required!${NC}"
        read -p "  Remote server URL: " SERVER_URL
    done

    # Get API key
    read -p "  Remote API key (from server administrator): " API_KEY
    while [ -z "$API_KEY" ]; do
        echo -e "${RED}    API key is required!${NC}"
        read -p "  Remote API key: " API_KEY
    done

    # Get optional blocked domain keyword
    read -p "  Blocked domain keyword (optional, press Enter to skip): " KEYWORD
    if [ -z "$KEYWORD" ]; then
        KEYWORD="<YourKeyword>"
    fi

    echo ""
    echo -e "${GREEN}  Updating .env file with your settings...${NC}"

    # Update .env file with user's values
    sed -i.bak "s|REMOTE_API_URL=http://192.168.10.50:8080|REMOTE_API_URL=$SERVER_URL|g" .env
    sed -i.bak "s|REMOTE_API_KEY=<APIKEY>|REMOTE_API_KEY=$API_KEY|g" .env
    sed -i.bak "s|BLOCKED_DOMAIN_KEYWORD=<YourKeyword>|BLOCKED_DOMAIN_KEYWORD=$KEYWORD|g" .env
    rm .env.bak

    echo -e "${GREEN}  ✓ Configuration saved to .env${NC}"
else
    echo -e "${YELLOW}[3/6] Using existing configuration${NC}"
fi

echo ""

# Test server connectivity
echo -e "${YELLOW}[4/6] Testing server connectivity...${NC}"
SERVER_URL=$(grep "^REMOTE_API_URL=" .env | cut -d'=' -f2)
if [ ! -z "$SERVER_URL" ]; then
    HEALTH_URL="$SERVER_URL/health"
    echo -e "${CYAN}  Testing connection to $HEALTH_URL...${NC}"

    if curl -s -f -m 5 "$HEALTH_URL" > /dev/null; then
        echo -e "${GREEN}  ✓ Server is reachable and healthy${NC}"
    else
        echo -e "${RED}  ✗ Cannot reach server${NC}"
        echo -e "${YELLOW}    This may be normal if the server is not running yet.${NC}"
        echo -e "${YELLOW}    You can continue, but verify server connectivity before using the client.${NC}"
    fi
fi

echo ""

# Stop any existing containers
echo -e "${YELLOW}[5/6] Stopping any existing client containers...${NC}"
docker compose down 2>&1 > /dev/null || true
echo -e "${GREEN}  ✓ Cleanup complete${NC}"

echo ""

# Build and start the client
echo -e "${YELLOW}[6/6] Building and starting client container...${NC}"
echo -e "${CYAN}  This may take a few minutes on first run...${NC}"

if docker compose up -d --build; then
    echo -e "${GREEN}  ✓ Client container started successfully${NC}"
else
    echo -e "${RED}  ✗ Failed to start client container${NC}"
    echo -e "${YELLOW}  Check logs with: docker compose logs${NC}"
    exit 1
fi

echo ""
echo -e "${CYAN}========================================"
echo -e "${GREEN}Setup Complete!${NC}"
echo -e "${CYAN}========================================${NC}"
echo ""

# Show container status
echo -e "${YELLOW}Container Status:${NC}"
docker compose ps

echo ""
echo -e "${CYAN}Next Steps:${NC}"
echo -e "${NC}  1. Configure your LLM (Claude Desktop, LM Studio) to use the MCP server"
echo "     See SETUP.md for detailed instructions"
echo ""
echo "  2. For Claude Desktop, edit the config file:"
echo "     macOS: ~/Library/Application Support/Claude/claude_desktop_config.json"
echo "     Linux: ~/.config/Claude/claude_desktop_config.json"
echo ""
echo "     Add this configuration:"
echo -e "${CYAN}     {"
echo '       "mcpServers": {'
echo '         "crawl4ai-rag": {'
echo '           "command": "docker",'
echo '           "args": ["exec", "-i", "crawl4ai-rag-client", "python", "-m", "core.rag_processor"]'
echo '         }'
echo '       }'
echo -e "     }${NC}"
echo ""
echo "  3. Restart your LLM application"
echo ""

echo -e "${CYAN}Useful Commands:${NC}"
echo "  View logs:    docker compose logs -f"
echo "  Stop client:  docker compose down"
echo "  Start client: docker compose up -d"
echo "  Check status: docker compose ps"
echo ""

echo -e "${CYAN}Documentation:${NC}"
echo "  Detailed setup guide:    SETUP.md"
echo "  Configuration reference: .env_template.txt"
echo ""