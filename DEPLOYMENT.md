# Thai ALPR System - Deployment Guide

## 🚀 Quick Deployment with Docker Compose

### Prerequisites
- Docker 20.10+
- Docker Compose 2.0+
- NVIDIA Docker Runtime (for GPU support)
- Your custom YOLO model `best.pt`

### Step 1: Prepare Environment

```bash
# Clone or extract the project
cd alpr_system

# Place your YOLO model
cp /path/to/your/best.pt models/best.pt

# Set up environment variables
cp backend/.env.example backend/.env
# Edit backend/.env with your configuration
```

### Step 2: Start All Services

```bash
# Build and start all services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f backend
```

### Step 3: Initialize Database

```bash
# Database is automatically initialized from init.sql
# Verify it's working:
docker-compose exec postgres psql -U postgres -d thai_alpr -c "\dt"
```

### Step 4: Access the Application

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/api/docs

### Default Credentials
- Username: `admin`
- Password: `admin123`

**⚠️ CHANGE IN PRODUCTION!**

---

## 📦 Manual Deployment (Without Docker)

### Backend Setup

```bash
cd backend

# Python environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Database setup
createdb thai_alpr
psql -d thai_alpr -f ../database/init.sql

# Configure
cp .env.example .env
nano .env  # Edit configuration

# Run
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Configure
echo "VITE_API_URL=http://localhost:8000/api" > .env.local

# Development
npm run dev

# Production build
npm run build
npx serve -s dist -l 3000
```

---

## 🔧 Production Deployment

### Using Nginx as Reverse Proxy

```nginx
# /etc/nginx/sites-available/alpr

upstream backend {
    server localhost:8000;
}

upstream frontend {
    server localhost:3000;
}

server {
    listen 80;
    server_name your-domain.com;

    # Redirect to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    # Frontend
    location / {
        proxy_pass http://frontend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # Backend API
    location /api {
        proxy_pass http://backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Storage (static files)
    location /storage {
        proxy_pass http://backend;
    }
}
```

### Using Systemd Services

**Backend Service** (`/etc/systemd/system/alpr-backend.service`):

```ini
[Unit]
Description=Thai ALPR Backend
After=network.target postgresql.service

[Service]
Type=simple
User=alpr
WorkingDirectory=/opt/alpr/backend
Environment="PATH=/opt/alpr/backend/venv/bin"
ExecStart=/opt/alpr/backend/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable alpr-backend
sudo systemctl start alpr-backend
sudo systemctl status alpr-backend
```

---

## ☸️ Kubernetes Deployment

### Deploy to Kubernetes

```bash
# Apply configurations
kubectl apply -f k8s/

# Check status
kubectl get pods -n alpr
kubectl get services -n alpr

# View logs
kubectl logs -f deployment/backend -n alpr
```

### Sample Deployment YAML

```yaml
# k8s/backend-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: backend
  namespace: alpr
spec:
  replicas: 3
  selector:
    matchLabels:
      app: backend
  template:
    metadata:
      labels:
        app: backend
    spec:
      containers:
      - name: backend
        image: thai-alpr-backend:latest
        ports:
        - containerPort: 8000
        env:
        - name: DB_HOST
          value: postgres-service
        - name: DB_PASSWORD
          valueFrom:
            secretKeyRef:
              name: db-secret
              key: password
        resources:
          requests:
            memory: "2Gi"
            cpu: "1"
            nvidia.com/gpu: 1
          limits:
            memory: "4Gi"
            cpu: "2"
            nvidia.com/gpu: 1
```

---

## 📊 Monitoring & Logging

### Prometheus Metrics

Add to `main.py`:

```python
from prometheus_fastapi_instrumentator import Instrumentator

app = FastAPI(...)

Instrumentator().instrument(app).expose(app)
```

### Logging Configuration

```python
# backend/logging_config.py
LOGGING_CONFIG = {
    "version": 1,
    "handlers": {
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": "logs/alpr.log",
            "maxBytes": 10485760,  # 10MB
            "backupCount": 5,
        }
    },
    "loggers": {
        "uvicorn": {"handlers": ["file"], "level": "INFO"},
        "fastapi": {"handlers": ["file"], "level": "INFO"},
    }
}
```

---

## 🔒 Security Hardening

### Backend
- [ ] Enable HTTPS only
- [ ] Use strong JWT secret
- [ ] Implement rate limiting
- [ ] Sanitize file uploads
- [ ] Use parameterized queries (already done with SQLAlchemy)
- [ ] Enable CORS whitelist
- [ ] Regular security updates

### Database
- [ ] Strong passwords
- [ ] Enable SSL connections
- [ ] Regular backups
- [ ] Limit network access
- [ ] Monitor for SQL injection attempts

### Frontend
- [ ] CSP headers
- [ ] XSS protection
- [ ] CSRF tokens
- [ ] Secure cookie settings

---

## 📈 Performance Tuning

### Backend Workers

```bash
# Run with multiple workers
gunicorn main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --timeout 120
```

### Database Optimization

```sql
-- Create additional indexes for performance
CREATE INDEX CONCURRENTLY idx_plate_records_capture_time 
  ON plate_records (capture_timestamp DESC);

CREATE INDEX CONCURRENTLY idx_plate_records_final_plate_trgm 
  ON plate_records USING gin (final_plate_number gin_trgm_ops);

-- Analyze tables
ANALYZE plate_records;
ANALYZE plate_corrections;
```

### Caching (Redis)

```python
# Optional: Add Redis caching
from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend
from redis import asyncio as aioredis

@app.on_event("startup")
async def startup():
    redis = aioredis.from_url("redis://localhost")
    FastAPICache.init(RedisBackend(redis), prefix="fastapi-cache")
```

---

## 🔄 Backup & Recovery

### Database Backup

```bash
# Daily backup script
#!/bin/bash
BACKUP_DIR="/backups/alpr"
DATE=$(date +%Y%m%d_%H%M%S)

pg_dump -U postgres thai_alpr | gzip > "$BACKUP_DIR/alpr_$DATE.sql.gz"

# Keep only last 30 days
find $BACKUP_DIR -name "alpr_*.sql.gz" -mtime +30 -delete
```

### Add to crontab:

```bash
0 2 * * * /opt/scripts/backup_alpr.sh
```

### Storage Backup

```bash
# Backup uploaded images
rsync -av --delete storage/ /backups/alpr/storage/
```

---

## 📞 Health Checks

```bash
# Backend health
curl http://localhost:8000/health

# Database connection
curl http://localhost:8000/health | jq '.database'

# Stream status
curl http://localhost:8000/api/streaming/streams/active
```

---

## 🐛 Troubleshooting

### Common Issues

**1. Database connection failed**
```bash
# Check PostgreSQL status
sudo systemctl status postgresql

# Verify connection
psql -U postgres -d thai_alpr -c "SELECT 1;"
```

**2. CUDA/GPU not detected**
```bash
# Verify NVIDIA Docker runtime
docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi
```

**3. OCR model download fails**
```bash
# Manually download EasyOCR models
python -c "import easyocr; easyocr.Reader(['th', 'en'])"
```

**4. RTSP stream timeout**
```bash
# Test stream with ffmpeg
ffmpeg -rtsp_transport tcp -i rtsp://camera-url -frames:v 1 test.jpg
```

---

## 📚 Additional Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com)
- [PostgreSQL Tuning](https://pgtune.leopard.in.ua)
- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/)
- [Kubernetes Patterns](https://kubernetes.io/docs/concepts/)

---

**Status: Production-Ready**  
**Last Updated: 2024**
