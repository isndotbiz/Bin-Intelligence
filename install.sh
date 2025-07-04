#!/bin/bash

# BIN Intelligence System - Quick Installation Script
# This script sets up the BIN Intelligence System on Ubuntu/Debian systems

set -e

echo "🚀 BIN Intelligence System Installation Script"
echo "=============================================="

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   echo "❌ This script should not be run as root"
   exit 1
fi

# Update system packages
echo "📦 Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Install required system packages
echo "🔧 Installing system dependencies..."
sudo apt install -y \
    python3.11 \
    python3.11-venv \
    python3-pip \
    postgresql \
    postgresql-contrib \
    nginx \
    git \
    curl

# Setup PostgreSQL
echo "🗄️ Setting up PostgreSQL database..."
sudo -u postgres psql -c "CREATE USER binuser WITH PASSWORD 'binpass123';" 2>/dev/null || echo "User already exists"
sudo -u postgres psql -c "CREATE DATABASE bindb OWNER binuser;" 2>/dev/null || echo "Database already exists"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE bindb TO binuser;" 2>/dev/null

# Create application directory
echo "📁 Setting up application directory..."
APP_DIR="$HOME/bin-intelligence-system"
if [ -d "$APP_DIR" ]; then
    echo "Directory already exists, updating..."
    cd "$APP_DIR"
    git pull
else
    echo "Cloning repository..."
    git clone https://github.com/your-username/bin-intelligence-system.git "$APP_DIR"
    cd "$APP_DIR"
fi

# Create Python virtual environment
echo "🐍 Setting up Python environment..."
python3.11 -m venv venv
source venv/bin/activate

# Install Python dependencies
echo "📚 Installing Python dependencies..."
pip install --upgrade pip
pip install -e .

# Create environment configuration
echo "⚙️ Creating environment configuration..."
cat > .env << EOF
DATABASE_URL=postgresql://binuser:binpass123@localhost:5432/bindb
NEUTRINO_API_KEY=your-neutrino-api-key-here
NEUTRINO_API_USER_ID=your-neutrino-user-id-here
FLASK_ENV=production
FLASK_DEBUG=False
EOF

echo "🔑 IMPORTANT: Edit .env file with your actual Neutrino API credentials!"
echo "   API Key and User ID are required for the system to function."

# Create systemd service
echo "🔧 Creating systemd service..."
sudo tee /etc/systemd/system/bin-intelligence.service > /dev/null << EOF
[Unit]
Description=BIN Intelligence System
After=network.target postgresql.service

[Service]
Type=exec
User=$USER
WorkingDirectory=$APP_DIR
Environment=PATH=$APP_DIR/venv/bin
EnvironmentFile=$APP_DIR/.env
ExecStart=$APP_DIR/venv/bin/gunicorn --bind 127.0.0.1:5000 --workers 4 main:app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Configure Nginx
echo "🌐 Configuring Nginx..."
sudo tee /etc/nginx/sites-available/bin-intelligence > /dev/null << EOF
server {
    listen 80;
    server_name localhost;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_connect_timeout 30s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;
    }

    # Health check endpoint
    location /health {
        proxy_pass http://127.0.0.1:5000/health;
        access_log off;
    }
}
EOF

# Enable Nginx site
sudo ln -sf /etc/nginx/sites-available/bin-intelligence /etc/nginx/sites-enabled/
sudo nginx -t

# Create logs directory
echo "📝 Setting up logging..."
mkdir -p "$APP_DIR/logs"

# Initialize database (this will create tables automatically)
echo "🗄️ Initializing database..."
source venv/bin/activate
python -c "
import main
print('Database tables created successfully!')
"

# Enable and start services
echo "🚀 Starting services..."
sudo systemctl daemon-reload
sudo systemctl enable bin-intelligence
sudo systemctl start bin-intelligence
sudo systemctl enable nginx
sudo systemctl restart nginx

# Check service status
echo "✅ Checking service status..."
if sudo systemctl is-active --quiet bin-intelligence; then
    echo "✅ BIN Intelligence service is running"
else
    echo "❌ BIN Intelligence service failed to start"
    echo "Check logs with: sudo journalctl -u bin-intelligence -f"
fi

if sudo systemctl is-active --quiet nginx; then
    echo "✅ Nginx is running"
else
    echo "❌ Nginx failed to start"
    echo "Check logs with: sudo journalctl -u nginx -f"
fi

# Create backup script
echo "💾 Creating backup script..."
cat > "$APP_DIR/backup.sh" << 'EOF'
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="$HOME/backups/bin-intelligence"
mkdir -p "$BACKUP_DIR"

# Backup database
pg_dump -h localhost -U binuser bindb > "$BACKUP_DIR/bindb_$DATE.sql"
gzip "$BACKUP_DIR/bindb_$DATE.sql"

# Keep only last 7 days
find "$BACKUP_DIR" -name "*.sql.gz" -mtime +7 -delete

echo "Backup completed: bindb_$DATE.sql.gz"
EOF

chmod +x "$APP_DIR/backup.sh"

# Add backup to crontab
echo "🕒 Setting up automated backups..."
(crontab -l 2>/dev/null; echo "0 2 * * * $APP_DIR/backup.sh") | crontab -

# Create management script
echo "🛠️ Creating management script..."
cat > "$APP_DIR/manage.sh" << 'EOF'
#!/bin/bash

case "$1" in
    start)
        sudo systemctl start bin-intelligence
        echo "BIN Intelligence started"
        ;;
    stop)
        sudo systemctl stop bin-intelligence
        echo "BIN Intelligence stopped"
        ;;
    restart)
        sudo systemctl restart bin-intelligence
        echo "BIN Intelligence restarted"
        ;;
    status)
        sudo systemctl status bin-intelligence
        ;;
    logs)
        sudo journalctl -u bin-intelligence -f
        ;;
    backup)
        ./backup.sh
        ;;
    update)
        git pull
        source venv/bin/activate
        pip install -e .
        sudo systemctl restart bin-intelligence
        echo "Application updated and restarted"
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|logs|backup|update}"
        exit 1
        ;;
esac
EOF

chmod +x "$APP_DIR/manage.sh"

echo ""
echo "🎉 Installation completed successfully!"
echo "=============================================="
echo ""
echo "📋 Next Steps:"
echo "1. Edit the .env file with your Neutrino API credentials:"
echo "   nano $APP_DIR/.env"
echo ""
echo "2. Access the application:"
echo "   http://localhost (or your server's IP address)"
echo ""
echo "3. Management commands:"
echo "   $APP_DIR/manage.sh start|stop|restart|status|logs|backup|update"
echo ""
echo "4. Service logs:"
echo "   sudo journalctl -u bin-intelligence -f"
echo ""
echo "5. Nginx logs:"
echo "   sudo tail -f /var/log/nginx/access.log"
echo "   sudo tail -f /var/log/nginx/error.log"
echo ""
echo "⚠️  IMPORTANT:"
echo "   - Configure your Neutrino API credentials in .env"
echo "   - Consider setting up SSL/HTTPS for production use"
echo "   - Review firewall settings for security"
echo ""
echo "📚 Documentation available in:"
echo "   - README.md - General information"
echo "   - API.md - API documentation"
echo "   - DEPLOYMENT.md - Detailed deployment guide"
echo "   - CONTRIBUTING.md - Development guidelines"
echo ""
echo "✅ Installation complete! The BIN Intelligence System is ready to use."