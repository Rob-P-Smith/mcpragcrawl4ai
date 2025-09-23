# Quick Start Guide

This guide provides step-by-step instructions for getting started with the Crawl4AI RAG MCP Server.

## Prerequisites

- Ubuntu/Linux system
- Docker and docker-compose installed
- Python 3.8 or higher
- LM-Studio installed
- At least 4GB RAM available
- 10GB free disk space

## Step 1: Setup Docker Container

Create the Docker configuration for Crawl4AI:

```bash
# Create docker-compose.yml
cat > docker-compose.yml << 'EOF'
services:
  crawl4ai:
    image: unclecode/crawl4ai:latest
    container_name: crawl4ai
    ports:
      - "11235:11235"
    shm_size: '1gb'
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:11235/"]
      interval: 30s
      timeout: 10s
      retries: 3
    environment:
      - LOG_LEVEL=INFO
EOF

# Start the container
docker-compose up -d

# Verify container is running
docker-compose ps
```

## Step 2: Test Docker Container

Verify the Crawl4AI container is working:

```bash
# Wait for container to be healthy
sleep 30

# Test basic connectivity
curl http://localhost:11235/

# Test crawling functionality
curl -X POST http://localhost:11235/crawl \
  -H "Content-Type: application/json" \
  -d '{"urls": ["https://httpbin.org/html"]}'
```

Expected response should include `"success": true` and crawled content.

## Step 3: Create Python Virtual Environment

```bash
# Create virtual environment
python3 -m venv crawl4ai_rag_env

# Activate environment
source crawl4ai_rag_env/bin/activate

# Upgrade pip
pip install --upgrade pip
```

## Step 4: Install Dependencies

Install all required Python packages:

```bash
# Core dependencies
pip install sentence-transformers==5.1.0
pip install sqlite-vec==0.1.6
pip install numpy==2.3.2
pip install requests==2.32.5

# Additional dependencies that may be required
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
pip install transformers==4.56.1
pip install huggingface-hub
```

## Step 5: Test sqlite-vec Installation

Run the test script to verify sqlite-vec is working:

```bash
python test_sqlite_vec.py
```

## Step 6: Test Sentence Transformers

Verify the sentence transformer model loads correctly:

```bash
python -c "
from sentence_transformers import SentenceTransformer
print('Loading model...')
model = SentenceTransformer('all-MiniLM-L6-v2')
print('✓ Model loaded successfully')
test_text = ['Hello world', 'Testing embeddings']
embeddings = model.encode(test_text)
print(f'✓ Embeddings generated: {embeddings.shape}')
"
```

## Step 7: Add RAG Server Script

Create the main RAG server script. Copy the complete `crawl4ai_rag_optimized.py` script to your home directory and make it executable:

```bash
# Make script executable
chmod +x crawl4ai_rag_optimized.py

# Test script initialization
python crawl4ai_rag_optimized.py &
SCRIPT_PID=$!
sleep 5
kill $SCRIPT_PID

# You should see:
# Initializing RAG system...
# RAG system ready!
```

## Step 8: Test RAG Server Manually

Test the MCP server with manual JSON-RPC calls:

```bash
# Test tools listing
echo '{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}' | python crawl4ai_rag_optimized.py

# Test crawling and storing
echo '{"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "crawl_and_remember", "arguments": {"url": "https://httpbin.org/html"}}}' | python crawl4ai_rag_optimized.py

# Test search functionality
echo '{"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "search_memory", "arguments": {"query": "test content"}}}' | python crawl4ai_rag_optimized.py
```

## Step 9: Configure LM-Studio MCP

Update LM-Studio's MCP configuration file:

```bash
# Get the full paths
VENV_PATH=$(pwd)/crawl4ai_rag_env
SCRIPT_PATH=$(pwd)/crawl4ai_rag_optimized.py

echo "Virtual Environment: $VENV_PATH"
echo "Script Path: $SCRIPT_PATH"
```

In LM-Studio, go to **Program → View MCP Configuration** and update `mcp.json`:

```json
{
  "mcpServers": {
    "crawl4ai-rag": {
      "command": "/home/YOUR_USERNAME/crawl4ai_rag_env/bin/python",
      "args": ["/home/YOUR_USERNAME/crawl4ai_rag_optimized.py"],
      "env": {
        "PYTHONPATH": "/home/YOUR_USERNAME/crawl4ai_rag_env/lib/python3.11/site-packages"
      }
    }
  }
}
```

Replace `YOUR_USERNAME` with your actual username and adjust Python version as needed.

## Step 10: Verify LM-Studio Integration

1. **Restart LM-Studio completely** (close and reopen)
2. **Check Integrations panel** - should show `crawl4ai-rag` with blue toggle
3. **Verify available tools**:

   **Basic Tools:**
   - `crawl_url` - Crawl single page without storing
   - `crawl_and_remember` - Crawl single page and store permanently
   - `crawl_temp` - Crawl single page and store temporarily
   
   **Deep Crawling Tools:**
   - `deep_crawl_dfs` - Deep crawl multiple pages without storing (preview only)
   - `deep_crawl_and_store` - Deep crawl and store all pages permanently
   
   **Knowledge Management:**
   - `search_memory` - Search stored content using semantic similarity
   - `list_memory` - List all stored content
   - `forget_url` - Remove specific content by URL
   - `clear_temp_memory` - Clear session content

4. **Test with simple command**: "List what's in memory"
