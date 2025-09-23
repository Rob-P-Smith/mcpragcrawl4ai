# Deployment Guide

This guide provides detailed information about different deployment scenarios for the Crawl4AI RAG MCP Server.

## Local Development Environment

### Prerequisites
- Ubuntu/Linux system
- Docker and docker-compose installed
- Python 3.8 or higher
- LM-Studio installed
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

## Production Deployment

### Prerequisites
- Linux server (Ubuntu 20.04 or later)
- Docker and docker-compose installed
- Domain name with DNS records configured
- SSL certificate (Let's Encrypt recommended)
- At least 8GB RAM available
- 50GB+ free disk space

### Configuration Steps

1. **Set up the server**:
```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Install Docker and docker-compose
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Install docker-compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

2. **Configure the application**:
```bash
# Create directory structure
mkdir -p /opt/crawl4ai-rag/{data,logs}

# Copy configuration files
cp docker-compose.yml /opt/crawl4ai-rag/
cp .env.example /opt/crawl4ai-rag/.env

# Set appropriate permissions
sudo chown -R $USER:$USER /opt/crawl4ai-rag
```

3. **Configure environment variables**:
```bash
# Edit the .env file with production settings
nano /opt/crawl4ai-rag/.env
```

Update the following values:
- `IS_SERVER=true`
- `LOCAL_API_KEY=your-strong-production-api-key-here` (use a strong, randomly generated key)
- `DB_PATH=/app/data/crawl4ai_rag.db`
- `RATE_LIMIT_PER_MINUTE=120` (increase for production)

4. **Set up SSL with Let's Encrypt**:
```bash
# Install certbot
sudo apt install certbot python3-certbot-nginx -y

# Obtain SSL certificate
sudo certbot --nginx -d your-domain.com
```

5. **Configure nginx as reverse proxy**:
```bash
# Create nginx configuration file
sudo nano /etc/nginx/sites-available/crawl4ai-rag
```

Add the following configuration:
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 301 https://$host$request_uri;
    }
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate_file /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key_file /etc/letsencrypt/live/your-domain.com/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    location / {
        proxy_pass http://localhost:8765;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /api/v1 {
        proxy_pass http://localhost:8080/api/v1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

6. **Enable the site and restart nginx**:
```bash
sudo ln -s /etc/nginx/sites-available/crawl4ai-rag /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

7. **Start the application**:
```bash
cd /opt/crawl4ai-rag
docker-compose up -d
```

## Cloud Deployment (AWS)

### Prerequisites
- AWS account with appropriate permissions
- EC2 instance (t3.large or larger recommended)
- EBS volume for data storage
- Route 53 domain management

### Setup Steps

1. **Launch an EC2 instance**:
   - Choose Ubuntu Server 20.04 LTS
   - Select t3.large instance type (2 vCPUs, 8GB RAM)
   - Configure security group to allow HTTP/HTTPS and SSH access
   - Attach EBS volume for data storage

2. **Connect to the instance**:
```bash
ssh -i your-key.pem ubuntu@your-instance-public-ip
```

3. **Install required software**:
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker and docker-compose
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker ubuntu

sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

4. **Set up the application**:
```bash
# Create directory structure
mkdir -p /opt/crawl4ai-rag/{data,logs}

# Copy configuration files
scp -i your-key.pem docker-compose.yml ubuntu@your-instance-public-ip:/opt/crawl4ai-rag/
scp -i your-key.pem .env.example ubuntu@your-instance-public-ip:/opt/crawl4ai-rag/.env

# Set appropriate permissions
sudo chown -R ubuntu:ubuntu /opt/crawl4ai-rag
```

5. **Configure environment variables**:
```bash
nano /opt/crawl4ai-rag/.env
```

Update the following values:
- `IS_SERVER=true`
- `LOCAL_API_KEY=your-strong-production-api-key-here` (use a strong, randomly generated key)
- `DB_PATH=/app/data/crawl4ai_rag.db`
- `RATE_LIMIT_PER_MINUTE=120` (increase for production)

6. **Set up SSL with Let's Encrypt**:
```bash
# Install certbot
sudo apt install certbot python3-certbot-nginx -y

# Obtain SSL certificate
sudo certbot --nginx -d your-domain.com
```

7. **Configure nginx as reverse proxy** (same as production deployment above)

8. **Start the application**:
```bash
cd /opt/crawl4ai-rag
docker-compose up -d
```

## Kubernetes Deployment

### Prerequisites
- Kubernetes cluster (EKS, GKE, or AKS)
- Helm installed
- PersistentVolume and PersistentVolumeClaim configured

### Setup Steps

1. **Create a values.yaml file**:
```yaml
# values.yaml
image:
  repository: your-dockerhub-username/crawl4ai-mcp-server
  tag: latest
  pullPolicy: IfNotPresent

replicaCount: 2

service:
  type: LoadBalancer
  port: 80
  targetPort: 8765

resources:
  limits:
    memory: "4Gi"
    cpu: "2"
  requests:
    memory: "2Gi"
    cpu: "1"

env:
  IS_SERVER: "true"
  LOCAL_API_KEY: "your-strong-production-api-key-here"
  DB_PATH: "/app/data/crawl4ai_rag.db"
  RATE_LIMIT_PER_MINUTE: "120"

volumeMounts:
  - name: data-storage
    mountPath: /app/data

volumes:
  - name: data-storage
    persistentVolumeClaim:
      claimName: crawl4ai-rag-pvc

# Additional configuration for the Crawl4AI container
crawl4ai:
  image:
    repository: unclecode/crawl4ai
    tag: latest
    pullPolicy: IfNotPresent
  ports:
    - name: http
      containerPort: 11235
```

2. **Create PersistentVolumeClaim**:
```yaml
# pvc.yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: crawl4ai-rag-pvc
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 50Gi
```

3. **Deploy the application**:
```bash
# Create the PVC
kubectl apply -f pvc.yaml

# Install the Helm chart
helm install crawl4ai-rag ./chart --values values.yaml
```

## Monitoring and Maintenance

### Logging Configuration

1. **Configure log rotation**:
```bash
# Create logrotate configuration
sudo nano /etc/logrotate.d/crawl4ai-rag
```

Add the following content:
```
/opt/crawl4ai-rag/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 644 root root
}
```

2. **Set up centralized logging** (optional):
```bash
# Install Fluent Bit for log collection
helm install fluent-bit stable/fluent-bit --namespace kube-system

# Configure to collect application logs
kubectl apply -f fluent-bit-config.yaml
```

### Backup Strategy

1. **Database backups**:
```bash
#!/bin/bash
# backup-db.sh
DATE=$(date +"%Y%m%d_%H%M%S")
BACKUP_DIR="/backup/crawl4ai-rag"
DB_PATH="/opt/crawl4ai-rag/data/crawl4ai_rag.db"

mkdir -p $BACKUP_DIR

cp $DB_PATH $BACKUP_DIR/crawl4ai_rag_$DATE.db
gzip $BACKUP_DIR/crawl4ai_rag_$DATE.db

# Remove backups older than 7 days
find $BACKUP_DIR -name "crawl4ai_rag_*.db.gz" -mtime +7 -delete
```

2. **Schedule backups**:
```bash
# Add to crontab
crontab -e
```

Add the following line for daily backups at 2 AM:
```
0 2 * * * /path/to/backup-db.sh
```

### Health Checks

1. **Configure health checks in docker-compose.yml**:
```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8765/health"]
  interval: 30s
  timeout: 10s
  retries: 3
```

2. **Set up monitoring with Prometheus and Grafana** (optional):
```yaml
# prometheus-config.yaml
- job_name: 'crawl4ai-rag'
  static_configs:
    - targets: ['your-domain.com:8765']
```

## Security Best Practices

1. **API Key Management**
   - Use strong, randomly generated API keys
   - Rotate keys regularly (every 90 days)
   - Store keys in environment variables or secret management system

2. **Network Security**
   - Use HTTPS with valid SSL certificates
   - Configure firewall rules to restrict access
   - Use private subnets for database servers

3. **Regular Updates**
   - Keep Docker images updated
   - Regularly update dependencies
   - Apply security patches promptly

4. **Access Control**
   - Limit user permissions
   - Implement role-based access control
   - Monitor and audit access logs
