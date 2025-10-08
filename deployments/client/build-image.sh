#!/bin/bash
# Build and export Crawl4AI RAG MCP Client Docker image for transfer

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}========================================"
echo "Crawl4AI RAG MCP Client Image Builder"
echo -e "========================================${NC}"
echo ""

# Configuration
IMAGE_NAME="crawl4ai-rag-client"
IMAGE_TAG="latest"
OUTPUT_FILE="crawl4ai-rag-client.tar"

echo -e "${YELLOW}Building Docker image for Windows deployment...${NC}"
echo ""
echo "Image name: ${CYAN}${IMAGE_NAME}:${IMAGE_TAG}${NC}"
echo "Output file: ${CYAN}${OUTPUT_FILE}${NC}"
echo ""

# Check if Docker is available
if ! command -v docker &> /dev/null; then
    echo -e "${RED}✗ Docker is not installed${NC}"
    exit 1
fi

echo -e "${YELLOW}[1/4] Building Docker image...${NC}"
echo -e "${CYAN}  This may take several minutes...${NC}"

# Build from project root (two directories up)
cd "$(dirname "$0")/../.."

if docker build -f deployments/client/Dockerfile -t ${IMAGE_NAME}:${IMAGE_TAG} .; then
    echo -e "${GREEN}  ✓ Image built successfully${NC}"
else
    echo -e "${RED}  ✗ Failed to build image${NC}"
    exit 1
fi

echo ""
echo -e "${YELLOW}[2/4] Checking image size...${NC}"
IMAGE_SIZE=$(docker images ${IMAGE_NAME}:${IMAGE_TAG} --format "{{.Size}}")
echo -e "${CYAN}  Image size: ${IMAGE_SIZE}${NC}"

echo ""
echo -e "${YELLOW}[3/4] Exporting image to ${OUTPUT_FILE}...${NC}"
echo -e "${CYAN}  This may take a few minutes...${NC}"

cd deployments/client

if docker save -o ${OUTPUT_FILE} ${IMAGE_NAME}:${IMAGE_TAG}; then
    echo -e "${GREEN}  ✓ Image exported successfully${NC}"
else
    echo -e "${RED}  ✗ Failed to export image${NC}"
    exit 1
fi

echo ""
echo -e "${YELLOW}[4/4] Verifying export...${NC}"

if [ -f ${OUTPUT_FILE} ]; then
    FILE_SIZE=$(du -h ${OUTPUT_FILE} | cut -f1)
    echo -e "${GREEN}  ✓ Export file created: ${FILE_SIZE}${NC}"
else
    echo -e "${RED}  ✗ Export file not found${NC}"
    exit 1
fi

echo ""
echo -e "${CYAN}========================================"
echo -e "${GREEN}Build Complete!${NC}"
echo -e "${CYAN}========================================${NC}"
echo ""

echo -e "${CYAN}Next Steps:${NC}"
echo ""
echo -e "${YELLOW}1. Transfer the image to your Windows workstation:${NC}"
echo "   File: ${CYAN}$(pwd)/${OUTPUT_FILE}${NC}"
echo ""
echo "   Methods:"
echo "   - SCP: ${CYAN}scp ${OUTPUT_FILE} user@windows-pc:/path/to/destination/${NC}"
echo "   - USB drive: Copy ${OUTPUT_FILE} to USB"
echo "   - Network share: Copy to shared folder"
echo ""
echo -e "${YELLOW}2. On your Windows workstation:${NC}"
echo ""
echo "   ${CYAN}# Load the image${NC}"
echo "   docker load -i ${OUTPUT_FILE}"
echo ""
echo "   ${CYAN}# Verify the image${NC}"
echo "   docker images ${IMAGE_NAME}"
echo ""
echo "   ${CYAN}# Copy required files to Windows${NC}"
echo "   - .env_template.txt"
echo "   - docker-compose.yml"
echo "   - deploy-on-windows.ps1"
echo ""
echo "   ${CYAN}# On Windows, create .env and start${NC}"
echo "   Copy-Item .env_template.txt .env"
echo "   notepad .env  # Edit with your server details"
echo "   docker compose up -d"
echo ""
echo -e "${YELLOW}3. Configure your LLM (Claude Desktop):${NC}"
echo "   Edit: ${CYAN}%APPDATA%\\Claude\\claude_desktop_config.json${NC}"
echo ""
echo "   Add:"
echo -e '   ${CYAN}{'
echo '     "mcpServers": {'
echo '       "crawl4ai-rag": {'
echo '         "command": "docker",'
echo '         "args": ["exec", "-i", "crawl4ai-rag-client", "python", "-m", "core.rag_processor"]'
echo '       }'
echo '     }'
echo -e '   }${NC}'
echo ""

echo -e "${CYAN}Files to transfer:${NC}"
echo "  1. ${OUTPUT_FILE} (Docker image)"
echo "  2. .env_template.txt (configuration template)"
echo "  3. docker-compose.yml (container orchestration)"
echo "  4. deploy-on-windows.ps1 (Windows deployment script)"
echo "  5. SETUP.md (documentation)"
echo ""

echo -e "${CYAN}Documentation:${NC}"
echo "  See SETUP.md for detailed Windows deployment instructions"
echo ""
