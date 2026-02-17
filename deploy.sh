#!/bin/bash

# =============================================================================
# Discord Bot Deployment Script
# =============================================================================
# Dieses Script hilft beim automatisierten Setup auf dem Server.
#
# WICHTIG: Führe dieses Script AUF DEM SERVER aus, nicht lokal!
#
# Usage:
#   chmod +x deploy.sh
#   ./deploy.sh
# =============================================================================

set -e  # Exit on error

echo "========================================="
echo "Discord Bot Deployment Script"
echo "Domain: dashboard.redcrafteryt11.net"
echo "========================================="
echo ""

# Farben für Output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Funktionen
print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    print_error "Bitte NICHT als root ausführen! Benutze sudo nur wenn nötig."
    exit 1
fi

# Schritt 1: Systemd Services erstellen
echo "Schritt 1: Erstelle Systemd Services..."
echo ""

read -p "Dein Linux Username (aktuell: $USER): " USERNAME
USERNAME=${USERNAME:-$USER}

# API Service
sudo bash -c "cat > /etc/systemd/system/discord-bot-api.service << EOF
[Unit]
Description=Discord Bot API
After=network.target postgresql.service redis-server.service

[Service]
Type=simple
User=$USERNAME
Group=$USERNAME
WorkingDirectory=/opt/discord-bot
Environment=\"PATH=/opt/discord-bot/venv/bin\"
ExecStart=/opt/discord-bot/venv/bin/python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 4
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF"

print_success "API Service erstellt"

# Bot Service
sudo bash -c "cat > /etc/systemd/system/discord-bot.service << EOF
[Unit]
Description=Discord Bot
After=network.target discord-bot-api.service

[Service]
Type=simple
User=$USERNAME
Group=$USERNAME
WorkingDirectory=/opt/discord-bot
Environment=\"PATH=/opt/discord-bot/venv/bin\"
ExecStart=/opt/discord-bot/venv/bin/python -m bot.main
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF"

print_success "Bot Service erstellt"

# Schritt 2: Nginx Konfiguration
echo ""
echo "Schritt 2: Erstelle Nginx Konfiguration..."
echo ""

# Dashboard
sudo bash -c "cat > /etc/nginx/sites-available/dashboard.redcrafteryt11.net << 'EOF'
server {
    listen 80;
    server_name dashboard.redcrafteryt11.net;
    return 301 https://\$server_name\$request_uri;
}

server {
    listen 443 ssl http2;
    server_name dashboard.redcrafteryt11.net;

    # SSL wird von certbot hinzugefügt

    add_header X-Frame-Options \"SAMEORIGIN\" always;
    add_header X-Content-Type-Options \"nosniff\" always;
    add_header X-XSS-Protection \"1; mode=block\" always;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;

        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection \"upgrade\";
    }

    location /static {
        alias /opt/discord-bot/dashboard/static;
        expires 30d;
        add_header Cache-Control \"public, immutable\";
    }
}
EOF"

print_success "Dashboard Nginx Config erstellt"

# API
sudo bash -c "cat > /etc/nginx/sites-available/api.redcrafteryt11.net << 'EOF'
server {
    listen 80;
    server_name api.redcrafteryt11.net;
    return 301 https://\$server_name\$request_uri;
}

server {
    listen 443 ssl http2;
    server_name api.redcrafteryt11.net;

    add_header X-Frame-Options \"DENY\" always;
    add_header X-Content-Type-Options \"nosniff\" always;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;

        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection \"upgrade\";
    }
}
EOF"

print_success "API Nginx Config erstellt"

# Symlinks
sudo ln -sf /etc/nginx/sites-available/dashboard.redcrafteryt11.net /etc/nginx/sites-enabled/
sudo ln -sf /etc/nginx/sites-available/api.redcrafteryt11.net /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

print_success "Nginx Symlinks erstellt"

# Schritt 3: Nginx testen
echo ""
echo "Schritt 3: Teste Nginx Konfiguration..."
sudo nginx -t

if [ $? -eq 0 ]; then
    print_success "Nginx Konfiguration OK"
else
    print_error "Nginx Konfiguration fehlerhaft!"
    exit 1
fi

# Schritt 4: Services aktivieren
echo ""
echo "Schritt 4: Aktiviere und starte Services..."
sudo systemctl daemon-reload
sudo systemctl enable discord-bot-api discord-bot
sudo systemctl restart nginx
sudo systemctl start discord-bot-api
sudo systemctl start discord-bot

print_success "Services gestartet"

# Schritt 5: Status prüfen
echo ""
echo "Schritt 5: Prüfe Service-Status..."
echo ""

if sudo systemctl is-active --quiet discord-bot-api; then
    print_success "API läuft"
else
    print_error "API läuft NICHT!"
fi

if sudo systemctl is-active --quiet discord-bot; then
    print_success "Bot läuft"
else
    print_error "Bot läuft NICHT!"
fi

if sudo systemctl is-active --quiet nginx; then
    print_success "Nginx läuft"
else
    print_error "Nginx läuft NICHT!"
fi

# Schritt 6: SSL Setup
echo ""
echo "========================================="
echo "WICHTIG: SSL-Zertifikate einrichten!"
echo "========================================="
echo ""
echo "Führe jetzt manuell aus:"
echo ""
echo "  sudo certbot --nginx -d dashboard.redcrafteryt11.net -d api.redcrafteryt11.net"
echo ""
print_warning "Certbot wird nach deiner Email fragen und die Terms fragen."
echo ""

# Schritt 7: Zusammenfassung
echo ""
echo "========================================="
echo "Deployment abgeschlossen!"
echo "========================================="
echo ""
echo "Nächste Schritte:"
echo ""
echo "1. SSL-Zertifikate einrichten (siehe oben)"
echo "2. .env Datei prüfen: nano /opt/discord-bot/.env"
echo "3. Logs prüfen:"
echo "   sudo journalctl -u discord-bot-api -f"
echo "   sudo journalctl -u discord-bot -f"
echo ""
echo "4. Dashboard aufrufen:"
echo "   https://dashboard.redcrafteryt11.net"
echo ""
echo "Bei Problemen:"
echo "   sudo systemctl status discord-bot-api"
echo "   sudo systemctl status discord-bot"
echo "   sudo systemctl status nginx"
echo ""
print_success "Viel Erfolg! 🚀"
