# Troubleshooting Guide

This guide provides solutions for common issues encountered when setting up and using the Crawl4AI RAG MCP Server.

## Common Issues and Solutions

### 1. Docker Container Not Starting

**Symptoms**: The container fails to start or shows "exited" status in `docker-compose ps`.

**Solutions**:
- Check container logs: `docker compose logs crawl4ai` and `docker compose logs crawl4ai-mcp-server`
- Verify port availability: `sudo lsof -i :11235` and `sudo lsof -i :8765`
- Increase Docker memory allocation in Docker Desktop settings
- Check disk space: `df -h` (ensure at least 10GB free)
- Restart Docker service: `sudo systemctl restart docker`

### 2. Python Import Errors

**Symptoms**: "ModuleNotFoundError" or similar import errors when running the RAG server.

**Solutions**:
- Verify virtual environment is activated: `source crawl4ai_rag_env/bin/activate`
- Check installed packages: `pip list | grep -E "(sentence|sqlite|numpy|requests)"`
- Reinstall dependencies: 
```bash
deactivate
rm -rf crawl4ai_rag_env
python3 -m venv crawl4ai_rag_env
source crawl4ai_rag_env/bin/activate
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
- Verify firewall rules allow traffic on required ports (8765, 11235)
- For cloud deployments, check security group settings
- Increase timeout values in configuration files
- Test with curl directly to the service endpoint

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
- Verify the Crawl4AI container is running: `docker-compose ps`
- Check if port 11235 is available: `sudo lsof -i :11235`
- Restart the Crawl4AI container: `docker compose restart crawl4ai`
- Update to the latest Crawl4AI Docker image
- Check network configuration in docker-compose.yml

### 8. LM-Studio Integration Issues

**Symptoms**: "Connection refused" or "MCP server not found" errors.

**Solutions**:
- Verify file paths in mcp.json are absolute and correct
- Ensure the script has execute permissions: `chmod +x crawl4ai_rag_optimized.py`
- Restart LM-Studio completely after configuration changes
- Check that the virtual environment path is correct
- For Docker deployments, ensure proper port mapping

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

## Contact Support

If you're unable to resolve an issue, please provide the following information when contacting support:

1. Full error message and stack trace
2. Relevant log file excerpts (last 50 lines)
3. Configuration files (.env, docker-compose.yml)
4. System specifications (OS version, Docker version, hardware specs)
5. Steps taken to reproduce the issue

For immediate assistance, you can also:
- Check the GitHub Issues page for similar problems
- Join the community forum or chat channel
- Contact the maintainers directly via email
