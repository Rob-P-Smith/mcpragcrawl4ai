# Crawl4AI RAG MCP Server

A complete Retrieval-Augmented Generation (RAG) system using Crawl4AI for web content extraction, sqlite-vec for vector storage, and LM-Studio MCP integration.

## Installation

### Prerequisites
- Ubuntu/Linux system
- Docker and docker-compose installed
- Python 3.8 or higher
- LM-Studio installed
- At least 4GB RAM available
- 10GB free disk space

### Quick Start

1. **Clone the repository**:
```bash
git clone https://github.com/Rob-P-Smith/mcpragcrawl4ai.git
cd mcpragcrawl4ai
```

2. **Create and activate virtual environment**:
```bash
python3 -m venv crawl4ai_rag_env
source crawl4ai_rag_env/bin/activate
```

3. **Install dependencies**:
```bash
pip install -r requirements.txt
```

4. **Start Docker containers**:
```bash
docker-compose up -d
```

5. **Configure LM-Studio**:
   - Open LM-Studio and go to Program → View MCP Configuration
   - Update the mcp.json file with the correct paths to your virtual environment and script

6. **Test the setup**:
```bash
# Test basic functionality
python3 core/rag_processor.py &
sleep 5
kill %1
```

For detailed documentation, see [docs/index.md](docs/index.md).
