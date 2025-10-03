# Server Deployment

This deploys the Crawl4AI RAG API server on Ubuntu server (192.168.10.50).

## Prerequisites

- Docker and docker-compose installed
- Port 8080 available for API access

## Setup

1. **Generate API key**:

   ```bash
   # Replace 'test-key-12345-for-development-only' in .env with a secure key
   openssl rand -base64 32
   ```

2. **Update .env**:

   - Set `LOCAL_API_KEY` to your generated key

3. **Start services**:

   ```bash
   docker-compose up -d
   ```

4. **Verify deployment**:
   ```bash
   curl http://localhost:8080/health
   ```

## Services

- **crawl4ai**: Web crawling service (port 11235)
- **api-server**: REST API server (port 8080)

## Database

- Location: `../../data/crawl4ai_rag.db`
- Persistent across container restarts

## API Documentation

Once running: http://192.168.10.50:8080/docs
