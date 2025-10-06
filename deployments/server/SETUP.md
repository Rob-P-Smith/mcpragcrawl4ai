# Server Deployment Setup Guide

This directory contains the configuration for deploying the full Crawl4AI RAG MCP Server with REST API, database, and Crawl4AI integration.

## Quick Start

### 1. Create Environment File

```bash
# Copy the template
cp .env_template.txt .env

# Edit with your configuration
nano .env  # or use your preferred editor
```

### 2. Configure Critical Settings

At minimum, update these settings in `.env`:

- **LOCAL_API_KEY**: Generate a secure key
  ```bash
  openssl rand -base64 32
  ```

- **BLOCKED_DOMAIN_KEYWORD**: Set a secret keyword for admin operations
  ```bash
  openssl rand -base64 16
  ```

### 3. Ensure Docker Network Exists

The server requires the `crawler_default` network to communicate with Crawl4AI:

```bash
docker network create crawler_default
```

### 4. Start the Server

```bash
# Start all services
docker compose up -d

# Check status
docker compose ps

# View logs
docker compose logs -f
```

### 5. Verify Installation

```bash
# Check health endpoint
curl http://localhost:8080/health

# Should return: {"status":"healthy","timestamp":"..."}
```

## Ports

- **8080**: REST API server
- **3000**: MCP server (for LLM integration)
- **11235**: Crawl4AI service (internal only)

## Data Persistence

The database and logs are stored in `../../data/` which is mounted as a volume:

- Database: `../../data/crawl4ai_rag.db`
- Logs: `../../data/crawl4ai_api.log`

**Important**: Backup this directory regularly!

## Updating Configuration

To apply changes to `.env`:

```bash
docker compose down
docker compose up -d
```

## Security Checklist

- [ ] Generated strong `LOCAL_API_KEY` (32+ characters)
- [ ] Set unique `BLOCKED_DOMAIN_KEYWORD`
- [ ] Configured appropriate `RATE_LIMIT_PER_MINUTE`
- [ ] Reviewed `ENABLE_CORS` setting for your use case
- [ ] Database backup strategy in place

## Common Issues

### Container fails to start

Check logs:
```bash
docker compose logs
```

Common causes:
- Invalid `.env` syntax (no spaces around `=`)
- Missing `crawler_default` network
- Port conflicts (8080 or 3000 already in use)

### Cannot connect to Crawl4AI

Ensure Crawl4AI is running:
```bash
docker network ls | grep crawler_default
docker ps | grep crawl4ai
```

### Database errors

Check database file permissions:
```bash
ls -la ../../data/
```

## Advanced Configuration

See `.env_template.txt` for detailed documentation of all available settings.

## Getting Help

For issues and questions:
- Check logs: `docker compose logs -f`
- Review `.env_template.txt` for configuration details
- Verify network connectivity: `docker network inspect crawler_default`
