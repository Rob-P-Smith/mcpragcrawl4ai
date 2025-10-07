# Troubleshooting Guide

This guide provides solutions for common issues encountered when setting up and using the Crawl4AI RAG MCP Server.

## Common Issues and Solutions

### RAM Database Issues

#### 1. RAM Database Not Initializing

**Symptoms**:
- `using_ram_db: false` in `/api/v1/stats` response
- Server logs show "Disk Database mode (traditional)"

**Causes**:
- `USE_MEMORY_DB` not set to `true` in `.env`
- Insufficient RAM available
- Initialization error during startup

**Solutions**:

1. **Verify environment variable**:
```bash
# Check .env file
grep USE_MEMORY_DB .env
# Should show: USE_MEMORY_DB=true

# If missing or false, update it
echo "USE_MEMORY_DB=true" >> .env
```

2. **Check available RAM**:
```bash
# Linux
free -h

# Should have at least 500MB free
# If low, close other applications or increase system RAM
```

3. **Restart the server**:
```bash
# For Docker deployment
docker-compose restart

# For local deployment
# Stop (Ctrl+C) and restart:
python3 core/rag_processor.py
```

4. **Check initialization logs**:
```bash
# Look for startup messages
docker-compose logs | grep -i "ram database"
# Should see: "RAM Database initialized and ready"
```

#### 2. Sync Failures and Recovery

**Symptoms**:
- High `failed_syncs` count in `/api/v1/db/stats`
- `sync_success_rate` < 1.0
- Error logs showing sync failures

**Causes**:
- Disk full or insufficient space
- Database file permissions issues
- Disk I/O errors
- Database file locked by another process

**Solutions**:

1. **Check disk space**:
```bash
df -h
# Ensure at least 1GB free in data directory
```

2. **Verify file permissions**:
```bash
ls -la data/crawl4ai_rag.db
# Should be writable by the server process

# Fix permissions if needed
chmod 666 data/crawl4ai_rag.db
chown $USER:$USER data/crawl4ai_rag.db
```

3. **Check for locks**:
```bash
# Check if database is locked by another process
lsof data/crawl4ai_rag.db

# If locked, identify and stop the locking process
```

4. **Force a manual sync**:
```bash
# Via API (if implemented)
curl -X POST http://localhost:8080/api/v1/db/sync \
  -H "Authorization: Bearer your-api-key"
```

5. **Restart with fresh sync**:
```bash
# Stop server
docker-compose down

# Verify disk database exists and is readable
sqlite3 data/crawl4ai_rag.db "PRAGMA integrity_check;"

# Start server (will reload from disk)
docker-compose up -d
```

#### 3. High Memory Usage

**Symptoms**:
- System running out of memory
- Server becoming slow or unresponsive
- OOM (Out of Memory) errors in logs

**Causes**:
- Database too large for available RAM
- Memory leak (rare)
- Multiple large crawl operations simultaneously

**Solutions**:

1. **Check database size**:
```bash
curl -H "Authorization: Bearer your-api-key" \
  http://localhost:8080/api/v1/stats | jq '.data.database_size_mb'

# If > 500MB, consider:
# - Cleaning up old content
# - Using retention policies
# - Switching to disk mode temporarily
```

2. **Monitor memory usage**:
```bash
# Check container memory
docker stats crawl4ai-rag-server

# Check system memory
free -h
htop
```

3. **Clean up old content**:
```bash
# Remove session-only content
curl -X DELETE http://localhost:8080/api/v1/memory/temp \
  -H "Authorization: Bearer your-api-key"

# Remove specific URLs
curl -X DELETE "http://localhost:8080/api/v1/memory?url=https://example.com" \
  -H "Authorization: Bearer your-api-key"
```

4. **Increase Docker memory limit**:
```yaml
# docker-compose.yml
services:
  crawl4ai-rag-server:
    deploy:
      resources:
        limits:
          memory: 4G  # Increase from 2G
```

5. **Switch to disk mode temporarily**:
```bash
# Edit .env
USE_MEMORY_DB=false

# Restart
docker-compose restart

# RAM mode can be re-enabled after cleanup
```

#### 4. Sync Taking Too Long

**Symptoms**:
- `last_sync_duration` > 5 seconds in `/api/v1/db/stats`
- Slow response times after writes
- High `pending_changes` count

**Causes**:
- Large number of pending changes
- Slow disk I/O (HDD instead of SSD)
- Database file fragmentation
- Network-mounted storage (NFS, etc.)

**Solutions**:

1. **Check sync metrics**:
```bash
curl -H "Authorization: Bearer your-api-key" \
  http://localhost:8080/api/v1/db/stats

# Look at:
# - pending_changes (should be < 1000)
# - last_sync_duration (should be < 1s)
# - total_records_synced
```

2. **Optimize disk I/O**:
- Use SSD instead of HDD
- Avoid network-mounted storage for database files
- Ensure adequate disk cache

3. **Reduce sync frequency for high-write scenarios**:
```python
# Edit core/data/sync_manager.py
# Increase idle sync threshold from 5s to 10s
if idle_time >= 10.0 and pending > 0:
    await self.differential_sync()
```

4. **Vacuum database to reduce fragmentation**:
```bash
# Stop server
docker-compose down

# Vacuum database
sqlite3 data/crawl4ai_rag.db "VACUUM;"

# Start server
docker-compose up -d
```

#### 5. Pending Changes Not Syncing

**Symptoms**:
- `pending_changes` count keeps increasing
- `last_sync_ago_seconds` keeps growing
- No sync happening despite activity

**Causes**:
- Sync monitor threads not running
- Exception in sync process
- Deadlock in sync mechanism

**Solutions**:

1. **Check server logs**:
```bash
docker-compose logs | grep -i sync
# Look for errors or exceptions
```

2. **Verify sync monitors are running**:
```bash
# Logs should show on startup:
# "Starting idle sync monitor"
# "Starting periodic sync monitor"
```

3. **Restart server**:
```bash
docker-compose restart

# Monitor logs during startup
docker-compose logs -f
```

4. **Check for deadlocks or hangs**:
```bash
# If server is responsive but not syncing
# Check process status
docker exec crawl4ai-rag-server ps aux | grep python

# Check thread status (if tools available)
docker exec crawl4ai-rag-server py-spy dump --pid 1
```

### Security Issues

#### 1. Domain Blocking Not Working

**Symptoms**:
- Blocked URLs are still being crawled
- No error message when crawling blocked domain
- Blocked pattern not being matched

**Causes**:
- Pattern syntax incorrect
- Pattern not in database
- Case sensitivity mismatch
- Pattern added but server not restarted

**Solutions**:

1. **Verify pattern is in blocklist**:
```bash
curl -H "Authorization: Bearer your-api-key" \
  http://localhost:8080/api/v1/blocked-domains

# Should show your pattern in the list
```

2. **Check pattern syntax**:
- `*.ru` - Blocks all .ru domains (wildcard TLD)
- `*spam*` - Blocks any URL containing "spam" (keyword)
- `example.com` - Blocks exact domain only

3. **Test domain blocking**:
```bash
# Try to crawl a blocked URL
curl -X POST http://localhost:8080/api/v1/crawl \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.ru/page"}'

# Should return error: "URL is blocked by domain pattern: *.ru"
```

4. **Add pattern if missing**:
```bash
curl -X POST http://localhost:8080/api/v1/blocked-domains \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"pattern": "*.ru", "description": "Block Russian domains"}'
```

5. **Restart server after adding patterns** (for MCP mode):
```bash
# Docker deployment
docker-compose restart

# Local deployment
# Stop and restart the server
```

#### 2. Input Validation Errors

**Symptoms**:
- "URL contains dangerous SQL pattern" errors
- Legitimate URLs being rejected
- "contains dangerous characters" errors

**Causes**:
- URL contains SQL keywords in legitimate context
- URL contains special characters flagged as dangerous
- Very long URLs exceeding limits

**Solutions**:

1. **Check for SQL keywords in URL**:
```bash
# URLs like: https://example.com/select-your-plan
# Contain "SELECT" which is flagged

# Solution: URL encode the path or use different URL structure
```

2. **Review URL content filter**:
```bash
# If legitimate URL is blocked by adult content filter
# Check the word list in core/data/dbdefense.py

# Example false positive:
# https://essex.ac.uk (contains "sex")
# https://dickssportinggoods.com (contains "dick")
```

3. **Adjust validation rules** (if needed):
```python
# Edit core/data/dbdefense.py
# Modify ADULT_CONTENT_WORDS list
# Or adjust sanitize_url() function for exceptions
```

4. **Check URL length**:
```bash
# Maximum URL length is 2048 characters
# Check length:
echo "https://very-long-url..." | wc -c
```

#### 3. Cannot Unblock Domain

**Symptoms**:
- DELETE /api/v1/blocked-domains returns "Unauthorized"
- Cannot remove blocked pattern
- "Invalid authorization keyword" error

**Causes**:
- `BLOCKED_DOMAIN_KEYWORD` not set in environment
- Wrong keyword provided
- Keyword mismatch (case-sensitive)

**Solutions**:

1. **Verify keyword is set**:
```bash
# Check .env file
grep BLOCKED_DOMAIN_KEYWORD .env

# If not set, add it
echo "BLOCKED_DOMAIN_KEYWORD=$(openssl rand -base64 16)" >> .env
```

2. **Use correct keyword in request**:
```bash
# Get keyword from .env
KEYWORD=$(grep BLOCKED_DOMAIN_KEYWORD .env | cut -d'=' -f2)

# Unblock with keyword
curl -X DELETE "http://localhost:8080/api/v1/blocked-domains?pattern=*.spam.com&keyword=$KEYWORD" \
  -H "Authorization: Bearer your-api-key"
```

3. **Restart server after setting keyword**:
```bash
docker-compose restart
```

#### 4. API Key Authentication Failing

**Symptoms**:
- "Unauthorized" or "Invalid API key" on all requests
- 401 errors despite providing key

**Causes**:
- API key not set in environment
- Wrong format in Authorization header
- Typo in API key
- Server restarted without loading new .env

**Solutions**:

1. **Verify API key in .env**:
```bash
grep LOCAL_API_KEY .env
# Should show a base64-encoded string
```

2. **Check Authorization header format**:
```bash
# Correct format
Authorization: Bearer your-api-key-here

# Not: "Authorization: your-api-key-here"
# Not: "X-API-Key: your-api-key-here"
```

3. **Test with curl**:
```bash
API_KEY=$(grep LOCAL_API_KEY .env | cut -d'=' -f2)

curl -H "Authorization: Bearer $API_KEY" \
  http://localhost:8080/api/v1/status
```

4. **Regenerate API key if needed**:
```bash
# Generate new key
NEW_KEY=$(openssl rand -base64 32)

# Update .env
sed -i "s/LOCAL_API_KEY=.*/LOCAL_API_KEY=$NEW_KEY/" .env

# Restart server
docker-compose restart

# Update clients with new key
```

### Performance Issues

#### 1. Slow Query Performance

**Symptoms**:
- Search requests taking > 1 second
- Memory listing slow
- Database stats slow to load

**Causes**:
- Not using RAM database mode
- Large database without proper indexing
- Heavy concurrent load

**Solutions**:

1. **Enable RAM database mode**:
```bash
# Edit .env
USE_MEMORY_DB=true

# Restart server
docker-compose restart

# Verify enabled
curl -H "Authorization: Bearer your-api-key" \
  http://localhost:8080/api/v1/stats | jq '.data.using_ram_db'
```

2. **Check database size and indexes**:
```bash
# Get stats
curl -H "Authorization: Bearer your-api-key" \
  http://localhost:8080/api/v1/stats

# Large databases (>10000 pages) may need optimization
```

3. **Reduce result limits**:
```bash
# Instead of requesting 1000 results
curl -X POST http://localhost:8080/api/v1/search \
  -d '{"query": "test", "limit": 10}'  # Use smaller limit
```

#### 2. High CPU Usage

**Symptoms**:
- Server using 100% CPU
- Slow response times
- System becoming unresponsive

**Causes**:
- Deep crawl operations in progress
- Multiple concurrent search requests
- Vector embedding generation

**Solutions**:

1. **Check active operations**:
```bash
# View server logs for active crawls
docker-compose logs -f | grep "Crawling"
```

2. **Limit concurrent operations**:
- Reduce `max_pages` in deep crawl requests
- Implement request queuing on client side
- Use rate limiting

3. **Monitor with docker stats**:
```bash
docker stats crawl4ai-rag-server

# Shows real-time CPU and memory usage
```

### 1. Docker Container Not Starting

**Symptoms**: The container fails to start or shows "exited" status in `docker ps`.

**Solutions**:
- Check container logs: `docker logs crawl4ai` or `docker logs crawl4ai-rag-server`
- Verify port availability:
  - Crawl4AI: `sudo lsof -i :11235`
  - REST API: `sudo lsof -i :8080`
  - MCP Server: `sudo lsof -i :3000`
- Increase Docker memory allocation in Docker Desktop settings
- Check disk space: `df -h` (ensure at least 10GB free)
- Restart Docker service: `sudo systemctl restart docker`

### 2. Python Import Errors

**Symptoms**: "ModuleNotFoundError" or similar import errors when running the RAG server.

**Solutions**:
- Verify virtual environment is activated: `source .venv/bin/activate`
- Check installed packages: `pip list | grep -E "(sentence|sqlite|numpy|requests)"`
- Reinstall dependencies:
```bash
deactivate
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```
- Check Python version compatibility with installed packages

### 3. API Key Authentication Fails

**Symptoms**: "Unauthorized" or "Invalid API key" errors when calling endpoints.

**Solutions**:
- Verify `LOCAL_API_KEY` is set in `.env` file
- Ensure the correct API key format: `Authorization: Bearer your-api-key`
- Check for typos in the API key
- Restart the server after changing environment variables
- For client mode, verify `REMOTE_API_KEY` and `REMOTE_API_URL` are correctly configured

### 4. Connection Timeout Errors

**Symptoms**: "Connection timed out" or "Failed to connect" errors when accessing services.

**Solutions**:
- Check network connectivity: `ping your-server-ip`
- Verify firewall rules allow traffic on required ports (8080 for REST API, 3000 for MCP, 11235 for Crawl4AI)
- For cloud deployments, check security group settings
- Increase timeout values in configuration files
- Test with curl directly to the service endpoint:
```bash
curl http://localhost:8080/health  # REST API
curl http://localhost:11235/  # Crawl4AI
```

### 5. Memory Issues

**Symptoms**: Out of memory errors or system slowdowns.

**Solutions**:
- Monitor memory usage: `htop` or `free -h`
- Increase Docker container memory allocation
- Reduce batch processing size in configuration files
- Optimize database queries and indexing
- Consider upgrading to a server with more RAM

### 6. Database Errors

**Symptoms**: "Database locked" or "Cannot open database file" errors.

**Solutions**:
- Check file permissions: `ls -la data/`
- Ensure the data directory is writable by the container user
- Verify disk space: `df -h` (ensure at least 10GB free)
- Restart Docker service to release locks
- For production, consider using a dedicated database server

### 7. Crawl4AI Service Not Responding

**Symptoms**: "Failed to connect to Crawl4AI" errors.

**Solutions**:
- Verify the Crawl4AI container is running: `docker ps | grep crawl4ai`
- Check if port 11235 is available: `sudo lsof -i :11235`
- Restart the Crawl4AI container: `docker restart crawl4ai`
- Update to the latest Crawl4AI Docker image: `docker pull unclecode/crawl4ai:latest`
- Check if containers are on same network: `docker network inspect crawler_default`

### 8. LM-Studio Integration Issues

**Symptoms**: "Connection refused" or "MCP server not found" errors.

**Solutions**:
- Verify file paths in mcp.json are absolute and correct
- Check MCP server path: should be `core/rag_processor.py`
- Restart LM-Studio completely after configuration changes
- Check that the virtual environment path is correct
- For Docker deployments:
  - Server mode: Use socat to connect to port 3000
  - Client mode: Use docker exec with container name

### 9. Rate Limiting Issues

**Symptoms**: "Too many requests" or "Rate limit exceeded" errors.

**Solutions**:
- Increase `RATE_LIMIT_PER_MINUTE` in .env file
- Implement request queuing for high-volume applications
- Add exponential backoff to client code
- Consider using a load balancer with rate limiting

### 10. SSL Certificate Issues

**Symptoms**: "SSL certificate error" or "Invalid certificate" warnings.

**Solutions**:
- Verify domain name matches the certificate
- Check that DNS records are properly configured
- Renew certificates before expiration: `sudo certbot renew`
- For development, use self-signed certificates with proper trust configuration
- Clear browser cache and restart browser

## Environment-Specific Troubleshooting

### Local Development Environment

1. **Port conflicts**: If ports 8765 or 11235 are already in use:
```bash
# Find the process using the port
sudo lsof -i :8765
sudo lsof -i :11235

# Kill the process (if safe to do so)
sudo kill -9 <PID>
```

2. **Virtual environment issues**: If the virtual environment becomes corrupted:
```bash
# Recreate the virtual environment
rm -rf crawl4ai_rag_env
python3 -m venv crawl4ai_rag_env
source crawl4ai_rag_env/bin/activate
pip install -r requirements.txt
```

### Production Deployment

1. **High CPU usage**: Monitor with `top` or `htop`, then:
   - Optimize database queries and indexing
   - Reduce concurrent crawling operations
   - Consider scaling horizontally with multiple instances

2. **Disk space issues**: Regularly monitor disk usage:
```bash
# Check disk usage
df -h

# Clean up old backups
find /backup/crawl4ai-rag -name "crawl4ai_rag_*.db.gz" -mtime +7 -delete
```

3. **SSL certificate renewal failures**: 
```bash
# Test the renewal process
sudo certbot renew --dry-run

# Check for configuration errors in nginx
sudo nginx -t
```


### Kubernetes Deployment

1. **Pods stuck in Pending state**:
```bash
# Check for scheduling issues
kubectl describe pod <pod-name>

# Check resource limits and requests
kubectl get nodes --show-labels
```

2. **PersistentVolumeClaim not bound**:
```bash
# Check PVC status
kubectl get pvc

# Check PV status
kubectl get pv

# Verify storage class configuration
kubectl get storageclass
```

## Log Analysis

### Common Error Patterns

1. **Database connection errors**: Look for "database locked" or "cannot open database file"
2. **Network timeouts**: Search for "connection timed out" or "failed to connect"
3. **Authentication failures**: Check for "invalid API key" or "unauthorized access"
4. **Memory allocation issues**: Look for "out of memory" or "memory limit exceeded"

### Log File Locations

- `./data/crawl4ai_rag_errors.log` - Application error logs
- `docker-compose logs` - Container logs
- `/var/log/nginx/` - Web server access and error logs (production)
- `/opt/crawl4ai-rag/logs/` - Application logs in production

### Log Analysis Commands

```bash
# View recent errors from application log
tail -n 100 ./data/crawl4ai_rag_errors.log | grep "ERROR"

# Monitor logs in real-time
docker compose logs -f

# Search for specific error patterns
grep -r "connection timeout" /opt/crawl4ai-rag/logs/

# Check nginx access logs
tail -n 50 /var/log/nginx/access.log
```

## Recovery Procedures

### Database Recovery

1. **Restore from backup**:
```bash
# Copy backup to data directory
cp ./backup/crawl4ai_rag_20231015_020000.db.gz ./data/
gunzip ./data/crawl4ai_rag_20231015_020000.db.gz

# Restart the application
docker compose restart crawl4ai-mcp-server
```

2. **Database integrity check**:
```bash
# Access SQLite database directly
docker exec -it crawl4ai-mcp-server sqlite3 /app/data/crawl4ai_rag.db

# Run integrity check
PRAGMA integrity_check;
```

### Service Recovery

1. **Restart all services**:
```bash
docker compose down
docker compose up -d
```

2. **Rollback to previous version**:
```bash
# Stop current deployment
docker compose down

# Pull previous image tag
docker pull your-dockerhub-username/crawl4ai-mcp-server:previous-version

# Restart with previous version
docker-compose up -d
```

## Prevention Strategies

### Regular Maintenance Tasks

1. **Daily**:
   - Check system health and resource usage
   - Verify backups are running successfully
   - Monitor error logs for new issues

2. **Weekly**:
   - Review access logs for suspicious activity
   - Update dependencies and security patches
   - Test backup restoration process

3. **Monthly**:
   - Rotate API keys
   - Review configuration settings
   - Perform full system health check

### Monitoring Setup

1. **Set up alerts for critical metrics**:
   - CPU usage > 80% for 5 minutes
   - Memory usage > 90% for 5 minutes
   - Disk space < 10% free
   - Error rate > 1% of total requests

2. **Implement logging aggregation**:
```bash
# Use Fluent Bit to collect logs from all containers
helm install fluent-bit stable/fluent-bit --namespace kube-system
```

3. **Set up monitoring dashboard** (Prometheus + Grafana):
```yaml
# prometheus-config.yaml
- job_name: 'crawl4ai-rag'
  static_configs:
    - targets: ['your-domain.com:8765']
```

## Quick Reference: Diagnostic Commands

### Check RAM Database Status
```bash
API_KEY=$(grep LOCAL_API_KEY .env | cut -d'=' -f2)

# Is RAM mode enabled?
curl -H "Authorization: Bearer $API_KEY" \
  http://localhost:8080/api/v1/stats | jq '.data.using_ram_db'

# Sync health metrics
curl -H "Authorization: Bearer $API_KEY" \
  http://localhost:8080/api/v1/db/stats | jq '.health'
```

### Check Security Status
```bash
# List blocked domains
curl -H "Authorization: Bearer $API_KEY" \
  http://localhost:8080/api/v1/blocked-domains | jq '.data.blocked_domains'

# Test if URL would be blocked
curl -X POST http://localhost:8080/api/v1/crawl \
  -H "Authorization: Bearer $API_KEY" \
  -d '{"url": "https://test.ru"}' | jq '.error'
```

### Check System Health
```bash
# Overall status
curl http://localhost:8080/health

# Detailed component health
curl -H "Authorization: Bearer $API_KEY" \
  http://localhost:8080/api/v1/status | jq '.components'

# Database statistics
curl -H "Authorization: Bearer $API_KEY" \
  http://localhost:8080/api/v1/stats | jq '.data | {total_pages, database_size_mb, using_ram_db}'
```

### Check Logs
```bash
# Recent application logs
docker-compose logs --tail=100 -f

# Search for errors
docker-compose logs | grep -i error

# Check sync activity
docker-compose logs | grep -i sync
```

### Performance Metrics
```bash
# Container resource usage
docker stats crawl4ai-rag-server --no-stream

# Database size and breakdown
curl -H "Authorization: Bearer $API_KEY" \
  http://localhost:8080/api/v1/stats | jq '.data.storage_breakdown'

# Recent activity
curl -H "Authorization: Bearer $API_KEY" \
  http://localhost:8080/api/v1/stats | jq '.data.recent_activity'
```

## Related Documentation

For more detailed information on specific topics:

- **[RAM Database Mode](../advanced/ram-database.md)** - Architecture, configuration, and optimization
- **[Security Layer](../advanced/security.md)** - Input validation, domain blocking, and best practices
- **[API Endpoints](../api/endpoints.md)** - Complete API reference with examples
- **[Deployment Guide](deployment.md)** - Production deployment, monitoring, and backups
- **[Quick Start Guide](quick-start.md)** - Initial setup and configuration

## Contact Support

If you're unable to resolve an issue, please provide the following information when contacting support:

1. Full error message and stack trace
2. Relevant log file excerpts (last 50 lines)
3. Configuration files (.env, docker-compose.yml)
4. System specifications (OS version, Docker version, hardware specs)
5. Steps taken to reproduce the issue
6. Output from diagnostic commands above

### Diagnostic Data Collection

Run this script to collect diagnostic information:

```bash
#!/bin/bash
# collect-diagnostics.sh

API_KEY=$(grep LOCAL_API_KEY .env | cut -d'=' -f2)
OUTPUT="diagnostics-$(date +%Y%m%d-%H%M%S).txt"

{
  echo "=== System Information ==="
  uname -a
  docker --version
  docker-compose --version

  echo -e "\n=== Environment Configuration ==="
  cat .env | grep -v "API_KEY\|KEYWORD"  # Redact sensitive keys

  echo -e "\n=== Container Status ==="
  docker ps -a | grep crawl4ai

  echo -e "\n=== Database Status ==="
  curl -s -H "Authorization: Bearer $API_KEY" \
    http://localhost:8080/api/v1/stats | jq '.'

  echo -e "\n=== RAM Database Health ==="
  curl -s -H "Authorization: Bearer $API_KEY" \
    http://localhost:8080/api/v1/db/stats | jq '.'

  echo -e "\n=== Blocked Domains ==="
  curl -s -H "Authorization: Bearer $API_KEY" \
    http://localhost:8080/api/v1/blocked-domains | jq '.data.count'

  echo -e "\n=== Recent Logs ==="
  docker-compose logs --tail=50

  echo -e "\n=== Resource Usage ==="
  docker stats crawl4ai-rag-server --no-stream

} > "$OUTPUT"

echo "Diagnostics saved to: $OUTPUT"
echo "Please attach this file when requesting support"
```

For immediate assistance, you can also:
- Check the GitHub Issues page for similar problems
- Join the community forum or chat channel
- Review the troubleshooting sections in this guide
