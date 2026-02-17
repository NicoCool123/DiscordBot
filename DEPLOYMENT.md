# 🚀 Deployment Guide - dashboard.redcrafteryt11.net

## Übersicht

Diese Anleitung zeigt dir, wie du den Discord Bot auf deinem Server mit der Domain **dashboard.redcrafteryt11.net** einrichtest.

---

## 📋 Voraussetzungen

### Server
- Linux Server (Ubuntu 22.04 oder Debian 11 empfohlen)
- Mindestens 2GB RAM
- Root-Zugriff oder sudo-Rechte
- Python 3.11+
- PostgreSQL 15+
- Redis 7+
- Nginx

### Domain
- ✅ `dashboard.redcrafteryt11.net` muss auf deine Server-IP zeigen (A-Record)
- Optional: `api.redcrafteryt11.net` für separate API (empfohlen)

### Discord
- Discord Bot Token
- Discord Application (Client ID + Secret für OAuth)

---

## 1️⃣ DNS-Konfiguration

### A-Records setzen (bei deinem Domain-Provider):

```
dashboard.redcrafteryt11.net  →  A  →  DEINE.SERVER.IP.ADRESSE
api.redcrafteryt11.net        →  A  →  DEINE.SERVER.IP.ADRESSE
```

**Testen:**
```bash
# Warte 5-10 Minuten nach DNS-Änderung
ping dashboard.redcrafteryt11.net
ping api.redcrafteryt11.net
```

---

## 2️⃣ Server-Vorbereitung

### Als Root/Sudo einloggen:

```bash
ssh root@DEINE.SERVER.IP.ADRESSE
# oder
ssh deinuser@DEINE.SERVER.IP.ADRESSE
sudo -i
```

### System aktualisieren:

```bash
apt update && apt upgrade -y
```

### Pakete installieren:

```bash
# Python 3.11
apt install -y python3.11 python3.11-venv python3-pip

# PostgreSQL
apt install -y postgresql postgresql-contrib

# Redis
apt install -y redis-server

# Nginx
apt install -y nginx

# Certbot (für SSL)
apt install -y certbot python3-certbot-nginx

# Git
apt install -y git

# Systemd und Tools
apt install -y systemctl htop curl
```

---

## 3️⃣ PostgreSQL Datenbank einrichten

```bash
# Als postgres User
sudo -u postgres psql

# In der PostgreSQL-Shell:
CREATE DATABASE discord_bot;
CREATE USER botuser WITH PASSWORD 'SICHERES_PASSWORT_HIER';
GRANT ALL PRIVILEGES ON DATABASE discord_bot TO botuser;
\q
```

**PostgreSQL für externe Verbindungen öffnen (optional):**

```bash
# /etc/postgresql/15/main/postgresql.conf
sudo nano /etc/postgresql/15/main/postgresql.conf

# Finde und ändere:
listen_addresses = 'localhost'  # Nur lokal (sicher)
# oder
listen_addresses = '*'          # Von überall (unsicher, nur mit Firewall!)

# Neustart
sudo systemctl restart postgresql
```

---

## 4️⃣ Redis einrichten

```bash
# Redis starten
sudo systemctl enable redis-server
sudo systemctl start redis-server

# Testen
redis-cli ping
# Sollte "PONG" zurückgeben
```

---

## 5️⃣ Bot-Dateien hochladen

### Methode 1: Git Clone (empfohlen)

```bash
# Als normaler User (nicht root!)
cd /opt
sudo mkdir discord-bot
sudo chown $USER:$USER discord-bot
cd discord-bot

# Repo klonen
git clone https://github.com/DEIN_USERNAME/DEIN_REPO.git .
```

### Methode 2: SCP/SFTP Upload

```bash
# Von deinem lokalen PC:
scp -r /mnt/c/Users/Nicolas/PycharmProjects/DiscordBot/* user@SERVER_IP:/opt/discord-bot/

# Oder mit FileZilla/WinSCP hochladen nach:
/opt/discord-bot/
```

---

## 6️⃣ Python Virtual Environment

```bash
cd /opt/discord-bot

# Venv erstellen
python3.11 -m venv venv

# Aktivieren
source venv/bin/activate

# Dependencies installieren
pip install --upgrade pip
pip install -r requirements.txt

# Deaktivieren
deactivate
```

---

## 7️⃣ .env Konfiguration erstellen

```bash
cd /opt/discord-bot
nano .env
```

**Inhalt (.env):**

```bash
# =============================================================================
# PRODUCTION CONFIGURATION - dashboard.redcrafteryt11.net
# =============================================================================

# -----------------------------------------------------------------------------
# Application
# -----------------------------------------------------------------------------
APP_NAME="Discord Bot Dashboard"
APP_VERSION="1.0.0"
DEBUG=false
ENVIRONMENT=production

# -----------------------------------------------------------------------------
# API Server
# -----------------------------------------------------------------------------
API_HOST=0.0.0.0
API_PORT=8000
API_URL=https://api.redcrafteryt11.net

# -----------------------------------------------------------------------------
# Dashboard
# -----------------------------------------------------------------------------
DASHBOARD_URL=https://dashboard.redcrafteryt11.net

# -----------------------------------------------------------------------------
# Database
# -----------------------------------------------------------------------------
DATABASE_URL=postgresql+asyncpg://botuser:DEIN_DB_PASSWORT@localhost:5432/discord_bot

# -----------------------------------------------------------------------------
# Redis
# -----------------------------------------------------------------------------
REDIS_URL=redis://localhost:6379/0

# -----------------------------------------------------------------------------
# Security (WICHTIG: Eigene sichere Keys generieren!)
# -----------------------------------------------------------------------------
# Generiere sichere Keys mit: openssl rand -hex 32
JWT_SECRET_KEY=GENERIERE_HIER_EINEN_SICHEREN_KEY_MIT_OPENSSL
SECRET_KEY=GENERIERE_HIER_EINEN_ANDEREN_SICHEREN_KEY
BOT_API_KEY=GENERIERE_HIER_EINEN_BOT_API_KEY

JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

# -----------------------------------------------------------------------------
# CORS & Hosts
# -----------------------------------------------------------------------------
ALLOWED_HOSTS=dashboard.redcrafteryt11.net,api.redcrafteryt11.net,localhost
CORS_ORIGINS=https://dashboard.redcrafteryt11.net,https://api.redcrafteryt11.net

# -----------------------------------------------------------------------------
# Discord OAuth
# -----------------------------------------------------------------------------
DISCORD_CLIENT_ID=DEINE_DISCORD_CLIENT_ID
DISCORD_CLIENT_SECRET=DEIN_DISCORD_CLIENT_SECRET
DISCORD_OAUTH_REDIRECT_URI=https://dashboard.redcrafteryt11.net/api/v1/auth/discord/callback

# -----------------------------------------------------------------------------
# Discord Bot Token
# -----------------------------------------------------------------------------
DISCORD_TOKEN=DEIN_DISCORD_BOT_TOKEN
DISCORD_PREFIX=!

# -----------------------------------------------------------------------------
# Minecraft RCON (optional)
# -----------------------------------------------------------------------------
RCON_ENABLED=false
RCON_HOST=localhost
RCON_PORT=25575
RCON_PASSWORD=

# -----------------------------------------------------------------------------
# Data Retention & Privacy
# -----------------------------------------------------------------------------
AUDIT_LOG_ENABLED=false
AUDIT_LOG_RETENTION_DAYS=1
AUDIT_LOG_ANONYMIZE_AFTER_DAYS=0
STORE_IP_ADDRESSES=false
STORE_USER_AGENTS=false

# -----------------------------------------------------------------------------
# Monitoring
# -----------------------------------------------------------------------------
METRICS_ENABLED=true
SENTRY_DSN=

# -----------------------------------------------------------------------------
# Logging
# -----------------------------------------------------------------------------
LOG_LEVEL=INFO
LOG_FORMAT=json
```

**Sichere Keys generieren:**

```bash
# JWT_SECRET_KEY
openssl rand -hex 32

# SECRET_KEY
openssl rand -hex 32

# BOT_API_KEY
openssl rand -hex 32
```

**Datei speichern:** STRG+O, Enter, STRG+X

---

## 8️⃣ Datenbank-Migrationen ausführen

```bash
cd /opt/discord-bot
source venv/bin/activate

# Alembic ausführen
alembic upgrade head

# Prüfen
alembic current
```

---

## 9️⃣ Systemd Services erstellen

### API Service

```bash
sudo nano /etc/systemd/system/discord-bot-api.service
```

**Inhalt:**

```ini
[Unit]
Description=Discord Bot API
After=network.target postgresql.service redis-server.service

[Service]
Type=simple
User=YOUR_USERNAME
Group=YOUR_USERNAME
WorkingDirectory=/opt/discord-bot
Environment="PATH=/opt/discord-bot/venv/bin"
ExecStart=/opt/discord-bot/venv/bin/python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 4
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**WICHTIG:** Ersetze `YOUR_USERNAME` mit deinem Linux-Username!

### Discord Bot Service

```bash
sudo nano /etc/systemd/system/discord-bot.service
```

**Inhalt:**

```ini
[Unit]
Description=Discord Bot
After=network.target discord-bot-api.service

[Service]
Type=simple
User=YOUR_USERNAME
Group=YOUR_USERNAME
WorkingDirectory=/opt/discord-bot
Environment="PATH=/opt/discord-bot/venv/bin"
ExecStart=/opt/discord-bot/venv/bin/python -m bot.main
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Services aktivieren und starten

```bash
# Reload systemd
sudo systemctl daemon-reload

# API starten
sudo systemctl enable discord-bot-api
sudo systemctl start discord-bot-api

# Bot starten
sudo systemctl enable discord-bot
sudo systemctl start discord-bot

# Status prüfen
sudo systemctl status discord-bot-api
sudo systemctl status discord-bot

# Logs ansehen
sudo journalctl -u discord-bot-api -f
sudo journalctl -u discord-bot -f
```

---

## 🔟 Nginx Konfiguration

### Dashboard Config

```bash
sudo nano /etc/nginx/sites-available/dashboard.redcrafteryt11.net
```

**Inhalt:**

```nginx
server {
    listen 80;
    server_name dashboard.redcrafteryt11.net;

    # Redirect all HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name dashboard.redcrafteryt11.net;

    # SSL Certificates (wird von certbot automatisch hinzugefügt)
    # ssl_certificate /etc/letsencrypt/live/dashboard.redcrafteryt11.net/fullchain.pem;
    # ssl_certificate_key /etc/letsencrypt/live/dashboard.redcrafteryt11.net/privkey.pem;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Proxy to FastAPI
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    # Static files
    location /static {
        alias /opt/discord-bot/dashboard/static;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
}
```

### API Config (optional, separate Domain)

```bash
sudo nano /etc/nginx/sites-available/api.redcrafteryt11.net
```

**Inhalt:**

```nginx
server {
    listen 80;
    server_name api.redcrafteryt11.net;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name api.redcrafteryt11.net;

    # SSL Certificates (wird von certbot automatisch hinzugefügt)

    # Security headers
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

### Nginx aktivieren

```bash
# Symlinks erstellen
sudo ln -s /etc/nginx/sites-available/dashboard.redcrafteryt11.net /etc/nginx/sites-enabled/
sudo ln -s /etc/nginx/sites-available/api.redcrafteryt11.net /etc/nginx/sites-enabled/

# Default Site deaktivieren
sudo rm /etc/nginx/sites-enabled/default

# Nginx Konfiguration testen
sudo nginx -t

# Nginx neu starten
sudo systemctl restart nginx
```

---

## 1️⃣1️⃣ SSL-Zertifikate mit Let's Encrypt

```bash
# Certbot für beide Domains
sudo certbot --nginx -d dashboard.redcrafteryt11.net -d api.redcrafteryt11.net

# Folge den Anweisungen:
# - Email eingeben
# - Terms akzeptieren
# - Redirect wählen (empfohlen: Yes)

# Auto-Renewal testen
sudo certbot renew --dry-run
```

**Certbot fügt automatisch SSL-Konfiguration zu Nginx hinzu!**

---

## 1️⃣2️⃣ Firewall einrichten (UFW)

```bash
# UFW installieren (falls nicht vorhanden)
sudo apt install -y ufw

# Regeln setzen
sudo ufw allow 22/tcp      # SSH
sudo ufw allow 80/tcp      # HTTP
sudo ufw allow 443/tcp     # HTTPS

# Optional: PostgreSQL nur von localhost
sudo ufw deny 5432/tcp

# Firewall aktivieren
sudo ufw enable

# Status prüfen
sudo ufw status verbose
```

---

## 1️⃣3️⃣ Discord Application OAuth URLs aktualisieren

1. Gehe zu [Discord Developer Portal](https://discord.com/developers/applications)
2. Wähle deine Application
3. **OAuth2** → **Redirects**
4. Füge hinzu:
   ```
   https://dashboard.redcrafteryt11.net/api/v1/auth/discord/callback
   ```
5. **Save Changes**

---

## 1️⃣4️⃣ Ersten Admin-User erstellen

```bash
cd /opt/discord-bot
source venv/bin/activate

# Python Shell
python

# In der Python Shell:
import asyncio
from api.core.database import AsyncSessionLocal
from api.models.user import User
from api.core.security import get_password_hash

async def create_admin():
    async with AsyncSessionLocal() as db:
        user = User(
            username="admin",
            email="admin@redcrafteryt11.net",
            password_hash=get_password_hash("SICHERES_PASSWORT"),
            is_superuser=True,
            is_active=True,
            is_verified=True
        )
        db.add(user)
        await db.commit()
        print("Admin user created!")

asyncio.run(create_admin())
exit()
```

---

## 1️⃣5️⃣ Testen

### 1. Dashboard aufrufen:

```
https://dashboard.redcrafteryt11.net
```

### 2. Login testen:

```
Username: admin
Password: DEIN_PASSWORT
```

### 3. API testen:

```
https://dashboard.redcrafteryt11.net/docs
# oder
https://api.redcrafteryt11.net/docs
```

### 4. Bot testen (Discord):

```
/admin status
/util ping
```

---

## 🔧 Wartung & Troubleshooting

### Logs ansehen:

```bash
# API Logs
sudo journalctl -u discord-bot-api -f

# Bot Logs
sudo journalctl -u discord-bot -f

# Nginx Logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

### Services neustarten:

```bash
sudo systemctl restart discord-bot-api
sudo systemctl restart discord-bot
sudo systemctl restart nginx
```

### Code aktualisieren:

```bash
cd /opt/discord-bot
git pull
source venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
sudo systemctl restart discord-bot-api
sudo systemctl restart discord-bot
```

### Datenbank-Backup:

```bash
# Backup erstellen
sudo -u postgres pg_dump discord_bot > backup_$(date +%Y%m%d).sql

# Restore
sudo -u postgres psql discord_bot < backup_20260217.sql
```

---

## 📊 Performance-Optimierung

### Nginx Caching

```nginx
# In /etc/nginx/sites-available/dashboard.redcrafteryt11.net
# Füge hinzu im server block:

# Cache static files
location ~* \.(jpg|jpeg|png|gif|ico|css|js|svg|woff|woff2|ttf)$ {
    expires 1y;
    add_header Cache-Control "public, immutable";
}
```

### Uvicorn Worker anpassen

```ini
# In /etc/systemd/system/discord-bot-api.service
ExecStart=/opt/discord-bot/venv/bin/python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 4

# Workers = CPU Kerne (z.B. 4 Kerne = 4 Workers)
```

---

## 🔐 Sicherheit

### Automatische Updates

```bash
sudo apt install -y unattended-upgrades
sudo dpkg-reconfigure --priority=low unattended-upgrades
```

### Fail2Ban (SSH-Schutz)

```bash
sudo apt install -y fail2ban
sudo systemctl enable fail2ban
sudo systemctl start fail2ban
```

### PostgreSQL Hardening

```bash
# /etc/postgresql/15/main/pg_hba.conf
sudo nano /etc/postgresql/15/main/pg_hba.conf

# Erlaube nur localhost:
local   all             all                                     peer
host    all             all             127.0.0.1/32            scram-sha-256
```

---

## ✅ Checkliste

- [ ] DNS A-Records gesetzt (dashboard + api)
- [ ] Server-Pakete installiert (Python, PostgreSQL, Redis, Nginx)
- [ ] PostgreSQL Datenbank erstellt
- [ ] Redis läuft
- [ ] Bot-Dateien hochgeladen
- [ ] Virtual Environment erstellt
- [ ] `.env` konfiguriert (mit sicheren Keys!)
- [ ] Alembic Migration ausgeführt
- [ ] Systemd Services erstellt und gestartet
- [ ] Nginx konfiguriert
- [ ] SSL-Zertifikate mit Let's Encrypt
- [ ] Firewall aktiviert
- [ ] Discord OAuth URLs aktualisiert
- [ ] Admin-User erstellt
- [ ] Dashboard erreichbar unter https://dashboard.redcrafteryt11.net
- [ ] Bot online in Discord

---

## 🆘 Probleme?

### Dashboard lädt nicht:

```bash
# Nginx Status
sudo systemctl status nginx

# API Status
sudo systemctl status discord-bot-api

# Logs prüfen
sudo journalctl -u discord-bot-api -n 50
```

### Bot offline:

```bash
sudo systemctl status discord-bot
sudo journalctl -u discord-bot -n 50
```

### SSL-Fehler:

```bash
sudo certbot renew --dry-run
sudo nginx -t
```

### Datenbank-Verbindung fehlschlägt:

```bash
# PostgreSQL läuft?
sudo systemctl status postgresql

# Connection testen
psql -U botuser -d discord_bot -h localhost
```

---

**Viel Erfolg mit deinem Deployment! 🚀**
