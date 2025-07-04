# Deployment Guide - BIN Intelligence System

This guide provides step-by-step instructions for deploying the BIN Intelligence System in various environments.

## 🚀 Quick Start (Replit)

The easiest way to deploy this application is on Replit, where it's already optimized to run.

### Prerequisites
- Replit account
- Neutrino API credentials

### Steps
1. **Fork or Import Project**
   - Fork this Replit project or import from GitHub
   - All dependencies are pre-configured in `pyproject.toml`

2. **Configure Environment Variables**
   - Go to Secrets tab in Replit
   - Add the following secrets:
     ```
     NEUTRINO_API_KEY=your-neutrino-api-key
     NEUTRINO_API_USER_ID=your-neutrino-user-id
     ```

3. **Start the Application**
   - Click the "Run" button
   - The database will be automatically created
   - Access the dashboard at the provided Replit URL

### Replit Features
- ✅ Automatic PostgreSQL database provisioning
- ✅ Environment variable management
- ✅ One-click deployment
- ✅ Built-in monitoring and logs
- ✅ Custom domain support available

---

## 🐳 Docker Deployment

### Dockerfile
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY pyproject.toml .
RUN pip install -e .

# Copy application code
COPY . .

# Expose port
EXPOSE 5000

# Start command
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "main:app"]
```

### Docker Compose
```yaml
version: '3.8'

services:
  app:
    build: .
    ports:
      - "5000:5000"
    environment:
      - DATABASE_URL=postgresql://binuser:binpass@db:5432/bindb
      - NEUTRINO_API_KEY=${NEUTRINO_API_KEY}
      - NEUTRINO_API_USER_ID=${NEUTRINO_API_USER_ID}
    depends_on:
      - db
    volumes:
      - ./:/app
    restart: unless-stopped

  db:
    image: postgres:15
    environment:
      - POSTGRES_DB=bindb
      - POSTGRES_USER=binuser
      - POSTGRES_PASSWORD=binpass
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped

volumes:
  postgres_data:
```

### Deploy with Docker
```bash
# Clone repository
git clone <repository-url>
cd bin-intelligence-system

# Create environment file
cat > .env << EOF
NEUTRINO_API_KEY=your-api-key
NEUTRINO_API_USER_ID=your-user-id
EOF

# Start services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f app
```

---

## ☁️ Cloud Platform Deployment

### Heroku Deployment

#### Prerequisites
- Heroku CLI installed
- Heroku account

#### Steps
```bash
# Login to Heroku
heroku login

# Create new app
heroku create your-bin-intelligence-app

# Add PostgreSQL addon
heroku addons:create heroku-postgresql:mini

# Set environment variables
heroku config:set NEUTRINO_API_KEY=your-api-key
heroku config:set NEUTRINO_API_USER_ID=your-user-id

# Deploy
git push heroku main

# Check status
heroku ps
heroku logs --tail
```

#### Procfile
```
web: gunicorn --bind 0.0.0.0:$PORT main:app
worker: python main.py
```

### DigitalOcean App Platform

#### app.yaml
```yaml
name: bin-intelligence-system
services:
- name: web
  source_dir: /
  github:
    repo: your-username/bin-intelligence-system
    branch: main
  run_command: gunicorn --bind 0.0.0.0:8080 main:app
  environment_slug: python
  instance_count: 1
  instance_size_slug: basic-xxs
  http_port: 8080
  envs:
  - key: NEUTRINO_API_KEY
    scope: RUN_TIME
    value: your-api-key
  - key: NEUTRINO_API_USER_ID
    scope: RUN_TIME
    value: your-user-id

databases:
- name: bindb
  engine: PG
  num_nodes: 1
  size: db-s-dev-database
```

### Google Cloud Platform

#### app.yaml (App Engine)
```yaml
runtime: python311

env_variables:
  NEUTRINO_API_KEY: "your-api-key"
  NEUTRINO_API_USER_ID: "your-user-id"
  DATABASE_URL: "postgresql://user:pass@/dbname?host=/cloudsql/project:region:instance"

beta_settings:
  cloud_sql_instances: your-project:your-region:your-instance
```

---

## 🖥️ VPS/Server Deployment

### Ubuntu/Debian Server Setup

#### System Requirements
- Ubuntu 20.04+ or Debian 11+
- 2GB RAM minimum
- 10GB disk space
- Python 3.11+
- PostgreSQL 13+

#### Installation Steps

1. **Update System**
   ```bash
   sudo apt update && sudo apt upgrade -y
   ```

2. **Install Dependencies**
   ```bash
   sudo apt install -y python3.11 python3.11-venv python3-pip postgresql postgresql-contrib nginx
   ```

3. **Setup PostgreSQL**
   ```bash
   sudo -u postgres createuser --interactive
   sudo -u postgres createdb bindb
   sudo -u postgres psql -c "ALTER USER binuser PASSWORD 'secure_password';"
   ```

4. **Create Application User**
   ```bash
   sudo useradd -m -s /bin/bash binapp
   sudo su - binapp
   ```

5. **Clone and Setup Application**
   ```bash
   git clone <repository-url> bin-intelligence-system
   cd bin-intelligence-system
   python3.11 -m venv venv
   source venv/bin/activate
   pip install -e .
   ```

6. **Configure Environment**
   ```bash
   cat > .env << EOF
   DATABASE_URL=postgresql://binuser:secure_password@localhost:5432/bindb
   NEUTRINO_API_KEY=your-api-key
   NEUTRINO_API_USER_ID=your-user-id
   EOF
   ```

7. **Create Systemd Service**
   ```bash
   sudo tee /etc/systemd/system/bin-intelligence.service << EOF
   [Unit]
   Description=BIN Intelligence System
   After=network.target postgresql.service

   [Service]
   Type=exec
   User=binapp
   WorkingDirectory=/home/binapp/bin-intelligence-system
   Environment=PATH=/home/binapp/bin-intelligence-system/venv/bin
   EnvironmentFile=/home/binapp/bin-intelligence-system/.env
   ExecStart=/home/binapp/bin-intelligence-system/venv/bin/gunicorn --bind 127.0.0.1:5000 --workers 4 main:app
   Restart=always

   [Install]
   WantedBy=multi-user.target
   EOF
   ```

8. **Configure Nginx**
   ```bash
   sudo tee /etc/nginx/sites-available/bin-intelligence << EOF
   server {
       listen 80;
       server_name your-domain.com;

       location / {
           proxy_pass http://127.0.0.1:5000;
           proxy_set_header Host \$host;
           proxy_set_header X-Real-IP \$remote_addr;
           proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto \$scheme;
       }
   }
   EOF

   sudo ln -s /etc/nginx/sites-available/bin-intelligence /etc/nginx/sites-enabled/
   sudo nginx -t
   sudo systemctl reload nginx
   ```

9. **Start Services**
   ```bash
   sudo systemctl enable bin-intelligence
   sudo systemctl start bin-intelligence
   sudo systemctl status bin-intelligence
   ```

### SSL/HTTPS Setup with Let's Encrypt

```bash
# Install Certbot
sudo apt install -y certbot python3-certbot-nginx

# Get SSL certificate
sudo certbot --nginx -d your-domain.com

# Auto-renewal
sudo crontab -e
# Add line: 0 12 * * * /usr/bin/certbot renew --quiet
```

---

## 🔧 Environment Configuration

### Required Environment Variables

| Variable | Description | Required | Example |
|----------|-------------|----------|---------|
| `DATABASE_URL` | PostgreSQL connection string | Yes | `postgresql://user:pass@host:5432/db` |
| `NEUTRINO_API_KEY` | Neutrino API authentication key | Yes | `your-api-key` |
| `NEUTRINO_API_USER_ID` | Neutrino API user identifier | Yes | `your-user-id` |
| `FLASK_SECRET_KEY` | Flask session secret | No | `random-secret-key` |
| `PORT` | Application port | No | `5000` |

### Development vs Production

#### Development (.env.development)
```bash
DATABASE_URL=postgresql://localhost:5432/bindb_dev
NEUTRINO_API_KEY=dev-api-key
NEUTRINO_API_USER_ID=dev-user-id
FLASK_ENV=development
FLASK_DEBUG=True
```

#### Production (.env.production)
```bash
DATABASE_URL=postgresql://user:pass@prod-host:5432/bindb
NEUTRINO_API_KEY=prod-api-key
NEUTRINO_API_USER_ID=prod-user-id
FLASK_ENV=production
FLASK_DEBUG=False
```

---

## 📊 Monitoring and Maintenance

### Health Checks

#### Basic Health Check Endpoint
Add to `main.py`:
```python
@app.route('/health')
def health_check():
    try:
        # Check database connectivity
        db_session.execute(text("SELECT 1"))
        return jsonify({"status": "healthy", "timestamp": datetime.utcnow().isoformat()})
    except Exception as e:
        return jsonify({"status": "unhealthy", "error": str(e)}), 503
```

#### Advanced Monitoring
```python
@app.route('/metrics')
def metrics():
    return jsonify({
        "total_bins": db_session.query(func.count(BIN.id)).scalar(),
        "verified_bins": db_session.query(func.count(BIN.id)).filter(BIN.is_verified == True).scalar(),
        "exploitable_bins": db_session.query(func.count(BIN.id)).filter(BIN.patch_status == 'Exploitable').scalar(),
        "last_update": db_session.query(func.max(BIN.updated_at)).scalar()
    })
```

### Log Management

#### Application Logs
```python
import logging
from logging.handlers import RotatingFileHandler

if not app.debug:
    file_handler = RotatingFileHandler('logs/bin-intelligence.log', maxBytes=10240000, backupCount=10)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
```

#### System Logs
```bash
# View application logs
sudo journalctl -u bin-intelligence -f

# View Nginx logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log

# View PostgreSQL logs
sudo tail -f /var/log/postgresql/postgresql-*.log
```

### Backup Strategy

#### Database Backup
```bash
#!/bin/bash
# backup.sh
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backups/bin-intelligence"
mkdir -p $BACKUP_DIR

pg_dump -h localhost -U binuser bindb > $BACKUP_DIR/bindb_$DATE.sql
gzip $BACKUP_DIR/bindb_$DATE.sql

# Keep only last 7 days
find $BACKUP_DIR -name "*.sql.gz" -mtime +7 -delete
```

#### Automated Backup
```bash
# Add to crontab
0 2 * * * /home/binapp/backup.sh
```

---

## 🚨 Troubleshooting

### Common Issues

#### Database Connection Errors
```bash
# Check PostgreSQL status
sudo systemctl status postgresql

# Check connection
psql -h localhost -U binuser -d bindb

# Reset password
sudo -u postgres psql -c "ALTER USER binuser PASSWORD 'new_password';"
```

#### Application Won't Start
```bash
# Check logs
sudo journalctl -u bin-intelligence -f

# Check Python environment
source venv/bin/activate
python -c "import main"

# Check dependencies
pip install -e .
```

#### API Rate Limiting
```python
# Monitor API usage
@app.route('/api-status')
def api_status():
    return jsonify({
        "neutrino_calls_today": get_api_usage_count(),
        "rate_limit_remaining": get_rate_limit_remaining()
    })
```

### Performance Optimization

#### Database Optimization
```sql
-- Add indexes for better performance
CREATE INDEX idx_bins_patch_status ON bins(patch_status);
CREATE INDEX idx_bins_brand ON bins(brand);
CREATE INDEX idx_bins_is_verified ON bins(is_verified);
CREATE INDEX idx_bin_exploits_bin_id ON bin_exploits(bin_id);
```

#### Application Tuning
```python
# Gunicorn configuration
workers = 4
worker_class = "sync"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 50
timeout = 30
keepalive = 2
```

---

## 🔒 Security Considerations

### Production Security Checklist

- [ ] Use HTTPS/SSL certificates
- [ ] Secure database with strong passwords
- [ ] Limit database access to application server only
- [ ] Use environment variables for all secrets
- [ ] Implement rate limiting on API endpoints
- [ ] Regular security updates for all dependencies
- [ ] Backup encryption for sensitive data
- [ ] Network firewall configuration
- [ ] Monitor access logs for suspicious activity

### Firewall Configuration
```bash
# UFW setup
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 'Nginx Full'
sudo ufw enable
```

---

This deployment guide covers the most common deployment scenarios. For specific platform requirements or custom configurations, refer to the platform-specific documentation or create a custom deployment script based on these examples.