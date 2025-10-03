#!/bin/bash
echo "=Setting up Crawl4AI MCP Client..."

if [ ! -f .env ]; then
    echo "Creating .env from template..."
    cp .env-template .env
    echo "Please edit .env with your server IP and API key"
else
    echo ".env file already exists"
fi

echo "=3 Building MCP client Docker image..."
docker-compose build

echo "Starting MCP client container..."
docker-compose up -d

echo ""
echo "MCP Client is running!"
echo ""
echo "Next steps:"
echo "1. Edit .env with correct SERVER-IP and API key"
echo "2. Restart with: docker-compose restart"
echo "3. Check logs: docker-compose logs -f"
echo "4. Configure LM-Studio to connect to this container"
echo ""
echo "=
 Container status:"
docker-compose ps