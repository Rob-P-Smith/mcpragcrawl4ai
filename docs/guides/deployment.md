# Deployment Guide

This guide covers deployment scenarios for the Crawl4AI RAG MCP Server.

> **Note**: For comprehensive deployment instructions including Docker server and client deployments, see the [Complete Deployment Guide](../deployments.md).

## Local Development Environment

### Prerequisites
- Ubuntu/Linux system or macOS
- Docker installed
- Python 3.8 or higher
- At least 4GB RAM available
- 10GB free disk space

### Setup Steps

1. **Clone the repository**:
```bash
git clone https://github.com/Rob-P-Smith/mcpragcrawl4ai.git
cd mcpragcrawl4ai
```

2. **Create and activate virtual environment**:
```bash
python3 -m venv .venv
source .venv/bin/activate  # Linux/Mac
# or
.venv\Scripts\activate  # Windows
```

3. **Install dependencies**:
```bash
pip install -r requirements.txt
```

4. **Start Crawl4AI service**:
```bash
docker run -d \
  --name crawl4ai \
  --network crawler_default \
  -p 11235:11235 \
  unclecode/crawl4ai:latest
```

5. **Configure environment**:
```bash
cat > .env << EOF
# Server Configuration
IS_SERVER=true
LOCAL_API_KEY=$(openssl rand -base64 32)

# Database Configuration
DB_PATH=./data/crawl4ai_rag.db
USE_MEMORY_DB=true  # Enable RAM database for 10-50x faster performance

# Service Configuration
CRAWL4AI_URL=http://localhost:11235

# Optional: Security Configuration
BLOCKED_DOMAIN_KEYWORD=$(openssl rand -base64 16)
EOF
```

6. **Run MCP server**:
```bash
python3 core/rag_processor.py
```

### LM-Studio Configuration (Local Development)

Update LM-Studio's MCP configuration:

```json
{
  "mcpServers": {
    "crawl4ai-rag": {
      "command": "/absolute/path/to/.venv/bin/python3",
      "args": ["/absolute/path/to/core/rag_processor.py"]
    }
  }
}
```

## Production Deployment Options

For production deployments, you have several options:

### 1. Docker Server Deployment
Deploy a full-featured server with REST API and MCP capabilities in Docker.

**Quick Start:**
```bash
docker compose -f deployments/server/docker-compose.yml up -d
```

See [Server Deployment Documentation](../../deployments/server/README.md) for details.

### 2. Docker Client Deployment
Deploy a lightweight MCP client that forwards requests to a remote server.

**Quick Start:**
```bash
docker compose -f deployments/client/docker-compose.yml up -d
```

See [Client Deployment Documentation](../../deployments/client/README.md) for details.

### 3. Complete Deployment Guide
For comprehensive deployment instructions, architecture diagrams, security considerations, and advanced configurations, see:

**[Complete Deployment Guide](../deployments.md)**

This includes:
- Server deployment (REST API + MCP)
- Client deployment (lightweight forwarder)
- Network configuration
- Security best practices
- Performance optimization
- Backup and recovery
- Monitoring and scaling

## Environment Variables

### Core Settings
- `IS_SERVER` - `true` for server mode, `false` for client mode (default: `true`)
- `SERVER_HOST` - Host to bind API server (default: `0.0.0.0`)
- `SERVER_PORT` - Port for API server (default: `8080`)

### Authentication
- `LOCAL_API_KEY` - API key for server mode (required)
- `REMOTE_API_KEY` - API key for client mode
- `REMOTE_API_URL` - Remote server URL for client mode

### Database Configuration
- `DB_PATH` - SQLite database path (default: `crawl4ai_rag.db`)
- `USE_MEMORY_DB` - Enable RAM database mode (default: `true`)
  - `true`: High-performance in-memory database with automatic disk sync
  - `false`: Traditional disk-based SQLite database

### Services
- `CRAWL4AI_URL` - Crawl4AI service URL (default: `http://localhost:11235`)

### Security
- `RATE_LIMIT_PER_MINUTE` - API rate limit (default: `60`)
- `BLOCKED_DOMAIN_KEYWORD` - Authorization keyword for unblocking domains (optional but recommended)

### Logging
- `LOG_LEVEL` - Logging verbosity: `DEBUG`, `INFO`, `WARNING`, `ERROR` (default: `INFO`)

## Common Commands

### Development
```bash
# Run MCP server
python3 core/rag_processor.py

# Run REST API server
python3 deployments/server/start_api_server.py

# Run tests
python3 core/utilities/test_sqlite_vec.py
python3 core/utilities/dbstats.py
```

### Docker Operations
```bash
# Server deployment
docker compose -f deployments/server/docker-compose.yml up -d
docker compose -f deployments/server/docker-compose.yml logs -f
docker compose -f deployments/server/docker-compose.yml down

# Client deployment
docker compose -f deployments/client/docker-compose.yml up -d
docker compose -f deployments/client/docker-compose.yml logs -f
docker compose -f deployments/client/docker-compose.yml down
```

## Troubleshooting

### Common Issues

**Port already in use:**
```bash
# Check what's using the port
sudo lsof -i :8080
sudo lsof -i :11235

# Kill the process if safe
sudo kill -9 <PID>
```

**Database errors:**
```bash
# Check database permissions
ls -la data/crawl4ai_rag.db

# Verify database integrity
sqlite3 data/crawl4ai_rag.db "PRAGMA integrity_check;"
```

**Crawl4AI connection failed:**
```bash
# Check if Crawl4AI is running
docker ps | grep crawl4ai

# Check Crawl4AI logs
docker logs crawl4ai

# Restart Crawl4AI
docker restart crawl4ai
```

For more troubleshooting, see:
- [Troubleshooting Guide](troubleshooting.md)
- [Complete Deployment Guide](../deployments.md#troubleshooting)

## RAM Database Deployment

### Overview

The RAM database mode provides significant performance improvements:
- **10-50x faster** read operations
- **5-10x faster** write operations
- Automatic differential synchronization to disk
- Minimal memory overhead (typically 50-500MB)

### Configuration

Enable RAM database mode in your `.env` file:

```bash
USE_MEMORY_DB=true
DB_PATH=./data/crawl4ai_rag.db
```

### Deployment Considerations

#### Memory Requirements
- **Minimum**: 500MB free RAM (for small databases with <1000 pages)
- **Recommended**: 1-2GB free RAM (for medium databases with 1000-10000 pages)
- **Large scale**: 4GB+ free RAM (for databases with 10000+ pages)

Calculate expected memory usage:
- Base overhead: ~20MB
- Per page: ~40KB (content + metadata)
- Per vector embedding: ~1.5KB (384-dim float32)

Example: 5000 pages = 20MB + (5000 × 40KB) + (5000 × 1.5KB) ≈ 220MB

#### Disk Space Requirements
The disk database file will contain the same data:
- Plan for at least 2x the RAM database size
- Allow headroom for growth and sync operations
- Regular cleanup of old content helps manage size

#### Sync Strategy

Two automatic sync mechanisms:
1. **Idle Sync**: Triggers 5 seconds after last write operation
2. **Periodic Sync**: Runs every 5 minutes regardless of activity

**Important**: Ensure the disk path is writable and has sufficient space.

### Monitoring RAM Database

#### Health Checks

Monitor sync health via API:

```bash
# Check RAM database status
curl -H "Authorization: Bearer your-api-key" \
  http://localhost:8080/api/v1/stats | jq '.data.using_ram_db'

# Get detailed sync metrics
curl -H "Authorization: Bearer your-api-key" \
  http://localhost:8080/api/v1/db/stats
```

Expected healthy metrics:
```json
{
  "mode": "memory",
  "sync_metrics": {
    "pending_changes": 0,
    "last_sync_ago_seconds": 45.2,
    "sync_success_rate": 1.0
  }
}
```

#### Warning Signs

Watch for these indicators of potential issues:
- `pending_changes` > 1000: Sync may be struggling
- `last_sync_ago_seconds` > 600: Sync may be stalled
- `sync_success_rate` < 0.95: Frequent sync failures

See [RAM Database Troubleshooting](#ram-database-issues) below.

### Docker Deployment with RAM Database

When deploying in Docker, ensure:

```yaml
# docker-compose.yml example
services:
  crawl4ai-rag-server:
    image: your-image
    environment:
      - USE_MEMORY_DB=true
      - DB_PATH=/app/data/crawl4ai_rag.db
    volumes:
      - ./data:/app/data  # Mount for disk persistence
    deploy:
      resources:
        limits:
          memory: 2G  # Adjust based on expected database size
        reservations:
          memory: 512M
```

### Graceful Shutdown

The system automatically syncs on shutdown, but for critical deployments:

```bash
# Force sync before shutdown
curl -X POST http://localhost:8080/api/v1/db/sync \
  -H "Authorization: Bearer your-api-key"

# Wait for sync to complete
sleep 5

# Then shutdown
docker-compose down
```

### Fallback to Disk Mode

If RAM mode encounters issues, disable it temporarily:

```bash
# Edit .env
USE_MEMORY_DB=false

# Restart server
# System will use disk database directly
```

The disk database is always kept up-to-date, so switching modes is seamless.

## Security Deployment

### Domain Blocking Setup

Configure initial blocked domains:

```bash
# Set authorization keyword
echo "BLOCKED_DOMAIN_KEYWORD=$(openssl rand -base64 16)" >> .env

# Add custom blocked patterns via API
curl -X POST http://localhost:8080/api/v1/blocked-domains \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"pattern": "*.malicious-site.com", "description": "Known malicious domain"}'
```

Default blocked patterns (auto-configured on first run):
- `*.ru` - All Russian domains
- `*.cn` - All Chinese domains
- `*porn*`, `*sex*`, `*escort*`, `*massage*` - Adult content keywords

### Input Validation

The system automatically validates all inputs:
- SQL injection prevention
- XSS protection
- Length limits enforcement
- Type validation

No additional configuration needed. See [Security Documentation](../advanced/security.md) for details.

### API Key Management

**Best practices**:
1. Generate strong API keys: `openssl rand -base64 32`
2. Store in environment variables, never in code
3. Rotate keys periodically (monthly recommended)
4. Use different keys for different environments (dev/staging/prod)

```bash
# Generate new key
NEW_KEY=$(openssl rand -base64 32)

# Update .env
sed -i "s/LOCAL_API_KEY=.*/LOCAL_API_KEY=$NEW_KEY/" .env

# Restart server
docker-compose restart
```

## Performance Optimization

### RAM Database Tuning

For high-traffic deployments:

1. **Increase periodic sync interval** (edit `core/data/sync_manager.py`):
```python
# Change from 5 minutes to 10 minutes
await asyncio.sleep(600)  # Was 300
```

2. **Increase idle sync threshold** (edit `core/data/sync_manager.py`):
```python
# Change from 5 seconds to 10 seconds
if idle_time >= 10.0 and pending > 0:  # Was 5.0
```

3. **Monitor memory usage**:
```bash
# Check container memory
docker stats crawl4ai-rag-server

# Check database size
curl -H "Authorization: Bearer your-api-key" \
  http://localhost:8080/api/v1/stats | jq '.data.database_size_mb'
```

### Rate Limiting

Adjust based on your traffic patterns:

```bash
# For high-traffic: increase limit
RATE_LIMIT_PER_MINUTE=300

# For low-traffic: decrease limit
RATE_LIMIT_PER_MINUTE=30
```

### Retention Policies

Use retention policies to manage database growth:

```bash
# Store with 30-day retention
curl -X POST http://localhost:8080/api/v1/crawl/store \
  -H "Authorization: Bearer your-api-key" \
  -d '{"url": "https://example.com", "retention_policy": "30_days"}'

# Temporary session-only storage
curl -X POST http://localhost:8080/api/v1/crawl/temp \
  -H "Authorization: Bearer your-api-key" \
  -d '{"url": "https://example.com"}'
```

## Monitoring and Alerting

### Key Metrics to Monitor

1. **System Health**:
   - Endpoint: `GET /api/v1/status`
   - Alert if: `status != "operational"`

2. **RAM Database Sync**:
   - Endpoint: `GET /api/v1/db/stats`
   - Alert if: `pending_changes > 1000` or `last_sync_ago_seconds > 600`

3. **Database Size**:
   - Endpoint: `GET /api/v1/stats`
   - Alert if: `database_size_mb > threshold`

4. **Error Rates**:
   - Monitor application logs
   - Alert if: error rate > 5% of total requests

### Sample Monitoring Script

```bash
#!/bin/bash
# monitor.sh - Check system health

API_KEY="your-api-key"
BASE_URL="http://localhost:8080"

# Check RAM database sync
PENDING=$(curl -s -H "Authorization: Bearer $API_KEY" \
  "$BASE_URL/api/v1/db/stats" | jq '.sync_metrics.pending_changes')

if [ "$PENDING" -gt 1000 ]; then
  echo "ALERT: High pending changes: $PENDING"
  # Send alert (email, Slack, etc.)
fi

# Check last sync time
LAST_SYNC=$(curl -s -H "Authorization: Bearer $API_KEY" \
  "$BASE_URL/api/v1/db/stats" | jq '.health.last_sync_ago_seconds')

if [ "$LAST_SYNC" -gt 600 ]; then
  echo "ALERT: Sync stale: ${LAST_SYNC}s ago"
fi

# Check database size
DB_SIZE=$(curl -s -H "Authorization: Bearer $API_KEY" \
  "$BASE_URL/api/v1/stats" | jq '.data.database_size_mb')

if [ "$DB_SIZE" -gt 1000 ]; then
  echo "WARNING: Database size: ${DB_SIZE}MB"
fi
```

Run via cron:
```bash
# Check every 5 minutes
*/5 * * * * /path/to/monitor.sh >> /var/log/crawl4ai-monitor.log 2>&1
```

## Backup and Recovery

### Automatic Backups

The disk database is continuously updated via sync, but regular backups are recommended:

```bash
#!/bin/bash
# backup.sh - Backup database

DB_PATH="./data/crawl4ai_rag.db"
BACKUP_DIR="./backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Backup database
cp "$DB_PATH" "$BACKUP_DIR/crawl4ai_rag_$TIMESTAMP.db"

# Compress
gzip "$BACKUP_DIR/crawl4ai_rag_$TIMESTAMP.db"

# Keep only last 7 days
find "$BACKUP_DIR" -name "*.gz" -mtime +7 -delete

echo "Backup complete: crawl4ai_rag_$TIMESTAMP.db.gz"
```

Run daily via cron:
```bash
# Daily backup at 2 AM
0 2 * * * /path/to/backup.sh >> /var/log/crawl4ai-backup.log 2>&1
```

### Recovery

To restore from backup:

```bash
# Stop server
docker-compose down

# Restore database
gunzip -c backups/crawl4ai_rag_20240115_020000.db.gz > data/crawl4ai_rag.db

# Start server
docker-compose up -d

# Verify
curl -H "Authorization: Bearer your-api-key" \
  http://localhost:8080/api/v1/stats
```

## Next Steps

- [Quick Start Guide](quick-start.md) - Get started quickly
- [API Documentation](../api/index.md) - REST API reference
- [RAM Database Mode](../advanced/ram-database.md) - Deep dive into RAM database
- [Security Documentation](../advanced/security.md) - Security features and best practices
- [Troubleshooting](troubleshooting.md) - Common issues and solutions
