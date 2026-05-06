# Production Deployment Guide

## Overview

Guide for deploying Code Solver AI in production environments with optimal performance, security, and reliability.

## Deployment Options

### 1. Local Development Deployment

#### Prerequisites
```bash
# System Requirements
- Python 3.10+
- 16GB RAM (minimum 8GB)
- 8+ CPU cores
- 20GB storage
- Ollama 0.23.0+
```

#### Installation Steps
```bash
# Clone repository
git clone https://github.com/riichspider/code-solver-ai.git
cd code-solver-ai

# Install dependencies
pip install -r requirements.txt

# Install Ollama (if not already)
curl -fsSL https://ollama.com/install.sh | sh

# Pull recommended model
ollama pull qwen2.5-coder:latest

# Start Streamlit
streamlit run app.py --server.port 8501
```

### 2. Docker Container Deployment

#### Dockerfile
```dockerfile
FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Ollama
RUN curl -fsSL https://ollama.com/install.sh | sh

# Set working directory
WORKDIR /app

# Copy application files
COPY requirements.txt .
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose ports
EXPOSE 8501 11434

# Start services
CMD ["sh", "-c", "ollama serve & streamlit run app.py --server.port 8501 --server.address 0.0.0.0"]
```

#### Docker Compose
```yaml
version: '3.8'
services:
  code-solver:
    build: .
    ports:
      - "8501:8501"
      - "11434:11434"
    volumes:
      - ./data:/app/data
      - ./models:/root/.ollama
    environment:
      - OLLAMA_HOST=0.0.0.0
      - STREAMLIT_SERVER_PORT=8501
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8501/healthz"]
      interval: 30s
      timeout: 10s
      retries: 3
```

#### Deployment Commands
```bash
# Build and run
docker-compose up -d

# View logs
docker-compose logs -f

# Pull model in container
docker-compose exec code-solver ollama pull qwen2.5-coder:latest
```

### 3. Kubernetes Deployment

#### Namespace & Config
```yaml
# namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: code-solver-ai
---
# configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: code-solver-config
  namespace: code-solver-ai
data:
  config.yaml: |
    default_model: qwen2.5-coder:latest
    ollama:
      base_url: http://ollama-service:11434/api
      timeout_seconds: 240
      keep_alive: 10m
    cache:
      enabled: true
      ttl_hours: 24
```

#### Deployment
```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: code-solver-ai
  namespace: code-solver-ai
spec:
  replicas: 2
  selector:
    matchLabels:
      app: code-solver-ai
  template:
    metadata:
      labels:
        app: code-solver-ai
    spec:
      containers:
      - name: code-solver
        image: code-solver-ai:latest
        ports:
        - containerPort: 8501
        env:
        - name: OLLAMA_HOST
          value: "http://ollama-service:11434"
        resources:
          requests:
            memory: "4Gi"
            cpu: "2"
          limits:
            memory: "8Gi"
            cpu: "4"
        volumeMounts:
        - name: config-volume
          mountPath: /app/config.yaml
          subPath: config.yaml
        livenessProbe:
          httpGet:
            path: /healthz
            port: 8501
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /healthz
            port: 8501
          initialDelaySeconds: 5
          periodSeconds: 5
      volumes:
      - name: config-volume
        configMap:
          name: code-solver-config
```

#### Service
```yaml
# service.yaml
apiVersion: v1
kind: Service
metadata:
  name: code-solver-service
  namespace: code-solver-ai
spec:
  selector:
    app: code-solver-ai
  ports:
  - port: 80
    targetPort: 8501
  type: LoadBalancer
---
apiVersion: v1
kind: Service
metadata:
  name: ollama-service
  namespace: code-solver-ai
spec:
  selector:
    app: ollama
  ports:
  - port: 11434
    targetPort: 11434
  type: ClusterIP
```

## Configuration Management

### Environment Variables
```bash
# Production Configuration
export OLLAMA_HOST=http://localhost:11434
export OLLAMA_MODELS=qwen2.5-coder:latest,llama3.1:8b
export CACHE_TTL_HOURS=24
export MAX_CONCURRENT_REQUESTS=10
export LOG_LEVEL=INFO
export ENABLE_METRICS=true
```

### Configuration File
```yaml
# config.yaml
default_model: qwen2.5-coder:latest
ollama:
  base_url: http://localhost:11434/api
  timeout_seconds: 240
  keep_alive: 10m
  options:
    temperature: 0.1
    top_p: 0.9
    num_predict: 2200

cache:
  enabled: true
  directory: /app/data/cache
  ttl_hours: 24
  max_size_mb: 1000

security:
  enable_sanitization: true
  max_request_size: 10000
  rate_limit_per_minute: 60

monitoring:
  enable_metrics: true
  log_level: INFO
  health_check_interval: 30
```

## Performance Optimization

### Resource Allocation

#### Minimum Requirements
```yaml
resources:
  requests:
    memory: "4Gi"
    cpu: "2"
  limits:
    memory: "8Gi"
    cpu: "4"
```

#### Recommended Production
```yaml
resources:
  requests:
    memory: "8Gi"
    cpu: "4"
  limits:
    memory: "16Gi"
    cpu: "8"
```

### Caching Strategy

#### Redis Cache (Optional)
```yaml
# redis-cache.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: redis-config
data:
  redis.conf: |
    maxmemory 2gb
    maxmemory-policy allkeys-lru
    save 900 1
    save 300 10
    save 60 10000
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis-cache
spec:
  replicas: 1
  selector:
    matchLabels:
      app: redis-cache
  template:
    metadata:
      labels:
        app: redis-cache
    spec:
      containers:
      - name: redis
        image: redis:7-alpine
        ports:
        - containerPort: 6379
        resources:
          requests:
            memory: "1Gi"
            cpu: "0.5"
          limits:
            memory: "2Gi"
            cpu: "1"
```

### Load Balancing

#### NGINX Configuration
```nginx
upstream code_solver_backend {
    server code-solver-1:8501;
    server code-solver-2:8501;
    server code-solver-3:8501;
}

server {
    listen 80;
    server_name code-solver.example.com;
    
    location / {
        proxy_pass http://code_solver_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
    }
    
    location /healthz {
        proxy_pass http://code_solver_backend/healthz;
        access_log off;
    }
}
```

## Security Considerations

### Network Security
```yaml
# network-policy.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: code-solver-network-policy
spec:
  podSelector:
    matchLabels:
      app: code-solver-ai
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: ingress-nginx
    ports:
    - protocol: TCP
      port: 8501
  egress:
  - to: []
    ports:
    - protocol: TCP
      port: 11434  # Ollama
    - protocol: TCP
      port: 443   # HTTPS
    - protocol: TCP
      port: 53    # DNS
```

### Input Validation
```python
# Enhanced security settings
SECURITY_CONFIG = {
    "max_input_length": 10000,
    "enable_sanitization": True,
    "blocked_patterns": [
        r"system\(",
        r"exec\(",
        r"eval\(",
        r"__import__",
    ],
    "rate_limit": {
        "requests_per_minute": 60,
        "burst_size": 10
    }
}
```

### Authentication (Optional)
```yaml
# oauth-proxy.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: oauth-proxy
spec:
  replicas: 1
  selector:
    matchLabels:
      app: oauth-proxy
  template:
    metadata:
      labels:
        app: oauth-proxy
    spec:
      containers:
      - name: oauth2-proxy
        image: quay.io/oauth2-proxy/oauth2-proxy:v7.5.1
        ports:
        - containerPort: 4180
        args:
        - --provider=github
        - --client-id=${GITHUB_CLIENT_ID}
        - --client-secret=${GITHUB_CLIENT_SECRET}
        - --cookie-secret=${COOKIE_SECRET}
        - --upstream=http://code-solver-service
        - --http-address=0.0.0.0:4180
```

## Monitoring & Observability

### Prometheus Metrics
```python
# metrics.py
from prometheus_client import Counter, Histogram, Gauge

# Metrics
REQUEST_COUNT = Counter('code_solver_requests_total', 'Total requests', ['method', 'status'])
REQUEST_DURATION = Histogram('code_solver_request_duration_seconds', 'Request duration')
ACTIVE_CONNECTIONS = Gauge('code_solver_active_connections', 'Active connections')
CACHE_HIT_RATE = Gauge('code_solver_cache_hit_rate', 'Cache hit rate')
```

### Grafana Dashboard
```json
{
  "dashboard": {
    "title": "Code Solver AI Metrics",
    "panels": [
      {
        "title": "Request Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(code_solver_requests_total[5m])",
            "legendFormat": "{{method}} {{status}}"
          }
        ]
      },
      {
        "title": "Response Time",
        "type": "graph",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, code_solver_request_duration_seconds)",
            "legendFormat": "95th percentile"
          }
        ]
      },
      {
        "title": "Cache Hit Rate",
        "type": "singlestat",
        "targets": [
          {
            "expr": "code_solver_cache_hit_rate",
            "legendFormat": "Hit Rate"
          }
        ]
      }
    ]
  }
}
```

### Health Checks
```python
# health.py
from fastapi import FastAPI
from core.pipeline import CodeSolver

app = FastAPI()

@app.get("/healthz")
async def health_check():
    try:
        solver = CodeSolver()
        models = solver.available_models()
        return {
            "status": "healthy",
            "models_count": len(models),
            "cache_status": "enabled",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }, 503
```

## Backup & Recovery

### Data Backup
```bash
#!/bin/bash
# backup.sh

BACKUP_DIR="/backup/code-solver-ai"
DATE=$(date +%Y%m%d_%H%M%S)

# Backup cache and history
mkdir -p $BACKUP_DIR
tar -czf $BACKUP_DIR/cache_$DATE.tar.gz /app/data/cache/
tar -czf $BACKUP_DIR/history_$DATE.tar.gz /app/data/history.db

# Backup configuration
cp /app/config.yaml $BACKUP_DIR/config_$DATE.yaml

# Cleanup old backups (keep 7 days)
find $BACKUP_DIR -name "*.tar.gz" -mtime +7 -delete
find $BACKUP_DIR -name "*.yaml" -mtime +7 -delete
```

### Disaster Recovery
```bash
#!/bin/bash
# recovery.sh

BACKUP_DIR="/backup/code-solver-ai"
BACKUP_DATE=$1

if [ -z "$BACKUP_DATE" ]; then
    echo "Usage: $0 <backup_date>"
    exit 1
fi

# Restore cache
tar -xzf $BACKUP_DIR/cache_$BACKUP_DATE.tar.gz -C /

# Restore history
tar -xzf $BACKUP_DIR/history_$BACKUP_DATE.tar.gz -C /

# Restore configuration
cp $BACKUP_DIR/config_$BACKUP_DATE.yaml /app/config.yaml

# Restart services
systemctl restart code-solver-ai
```

## Troubleshooting

### Common Issues

#### 1. Ollama Connection Failed
```bash
# Check Ollama status
curl http://localhost:11434/api/tags

# Restart Ollama
systemctl restart ollama

# Check logs
journalctl -u ollama -f
```

#### 2. Memory Issues
```bash
# Check memory usage
docker stats

# Increase memory limits
kubectl patch deployment code-solver-ai -p '{"spec":{"template":{"spec":{"containers":[{"name":"code-solver","resources":{"limits":{"memory":"16Gi"}}}]}}}}'

# Clear cache
rm -rf /app/data/cache/*
```

#### 3. Slow Response Times
```bash
# Check model performance
ollama show qwen2.5-coder:latest

# Use smaller model
export DEFAULT_MODEL=qwen2.5-coder-4k:latest

# Enable debug logging
export LOG_LEVEL=DEBUG
```

### Performance Tuning

#### Model Optimization
```yaml
# Optimized model settings
ollama:
  options:
    temperature: 0.05  # Lower for more deterministic
    top_p: 0.9
    num_predict: 1400  # Reduce for faster response
    num_ctx: 2048      # Reduce context window
```

#### Cache Optimization
```yaml
cache:
  enabled: true
  max_size_mb: 2000    # Increase cache size
  cleanup_interval: 3600  # Cleanup every hour
  compression: true    # Enable compression
```

## Maintenance

### Regular Tasks
```bash
# Daily cleanup
0 2 * * * /app/scripts/cleanup_cache.sh

# Weekly backup
0 3 * * 0 /app/scripts/backup.sh

# Monthly model updates
0 4 1 * * /app/scripts/update_models.sh
```

### Monitoring Alerts
```yaml
# alerts.yaml
groups:
- name: code-solver-ai
  rules:
  - alert: HighErrorRate
    expr: rate(code_solver_requests_total{status="5xx"}[5m]) > 0.1
    for: 5m
    labels:
      severity: critical
    annotations:
      summary: "High error rate detected"
  
  - alert: HighResponseTime
    expr: histogram_quantile(0.95, code_solver_request_duration_seconds) > 60
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "High response time detected"
```

## Conclusion

This deployment guide provides comprehensive options for deploying Code Solver AI in production environments, from local development to enterprise Kubernetes deployments. Key considerations include:

1. **Resource Planning**: Ensure adequate memory and CPU for model inference
2. **Security**: Implement proper network policies and input validation
3. **Monitoring**: Set up comprehensive observability
4. **Backup**: Regular data protection and recovery procedures
5. **Performance**: Optimize caching and model selection

Following these guidelines will ensure a reliable, scalable, and secure production deployment of Code Solver AI.
