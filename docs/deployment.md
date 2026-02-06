# Deployment Guide

This guide covers deploying the Discord Bot to a KVM server (or any Linux VPS) using either Docker or bare metal with systemd.

## Prerequisites

- Linux server (Ubuntu 22.04+ recommended)
- Root or sudo access
- Domain names pointed to your server (for SSL)
- Discord bot token

## Option A: Docker Compose (Recommended)

### 1. Install Docker

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# Log out and back in
```

### 2. Clone and Configure

```bash
git clone <repository-url> /opt/discord-bot
cd /opt/discord-bot

cp .env .env
# Edit .env with production values
nano .env
```

Generate secrets:

```bash
echo "JWT_SECRET_KEY=$(openssl rand -hex 32)" >> .env
echo "SECRET_KEY=$(openssl rand -hex 32)" >> .env
echo "BOT_API_KEY=$(openssl rand -hex 32)" >> .env
```

### 3. Configure SSL

Place your SSL certificates in `docker/ssl/`:

```bash
mkdir -p docker/ssl
cp /path/to/fullchain.pem docker/ssl/
cp /path/to/privkey.pem docker/ssl/
```

Or use Let's Encrypt:

```bash
sudo apt install certbot
sudo certbot certonly --standalone -d api.yourdomain.de -d dashboard.yourdomain.de
sudo cp /etc/letsencrypt/live/api.yourdomain.de/fullchain.pem docker/ssl/
sudo cp /etc/letsencrypt/live/api.yourdomain.de/privkey.pem docker/ssl/
```

### 4. Update Nginx Config

Edit `docker/nginx.conf` and replace:
- `api.yourdomain.de` with your actual API domain
- `dashboard.yourdomain.de` with your actual dashboard domain

### 5. Deploy

```bash
docker-compose -f docker-compose.prod.yml up -d
```

### 6. Seed the Database

```bash
docker-compose -f docker-compose.prod.yml exec api python scripts/seed.py
```

### 7. Verify

```bash
# Check all services are running
docker-compose -f docker-compose.prod.yml ps

# Check API health
curl https://api.yourdomain.de/health

# View logs
docker-compose -f docker-compose.prod.yml logs -f api
```

### Updating

```bash
cd /opt/discord-bot
git pull origin main
docker-compose -f docker-compose.prod.yml build
docker-compose -f docker-compose.prod.yml up -d
```

---

## Option B: Bare Metal with Systemd

### 1. Initial Setup

```bash
sudo ./scripts/deploy.sh setup
```

This installs:
- Python 3.11, PostgreSQL, Redis, Nginx, certbot
- Creates `discord` system user
- Configures firewall (SSH, HTTP, HTTPS only)
- Obtains SSL certificates (if domains are configured)

### 2. Deploy

```bash
./scripts/deploy.sh deploy
```

This:
- Creates virtual environment
- Installs Python dependencies
- Generates secrets in `.env`
- Builds Tailwind CSS
- Runs database migrations
- Seeds default data
- Installs and starts systemd services

### 3. Configure

Edit `/opt/discord-bot/.env` with your values:

```bash
sudo -u discord nano /opt/discord-bot/.env
```

Restart services:

```bash
sudo systemctl restart discord-api discord-bot
```

### 4. Nginx Setup

Copy the Nginx config:

```bash
sudo cp /opt/discord-bot/docker/nginx.conf /etc/nginx/sites-available/discord-bot
sudo ln -s /etc/nginx/sites-available/discord-bot /etc/nginx/sites-enabled/
# Edit domains
sudo nano /etc/nginx/sites-available/discord-bot
sudo nginx -t
sudo systemctl reload nginx
```

### Service Management

```bash
# Status
sudo systemctl status discord-api
sudo systemctl status discord-bot

# Restart
sudo systemctl restart discord-api
sudo systemctl restart discord-bot

# Logs
sudo journalctl -u discord-api -f
sudo journalctl -u discord-bot -f

# Enable on boot
sudo systemctl enable discord-api discord-bot
```

### Updating

```bash
./scripts/deploy.sh update
```

---

## Post-Deployment Checklist

- [ ] API health check returns `{"status": "healthy"}`
- [ ] Dashboard loads with correct CSS styling
- [ ] Bot appears online in Discord
- [ ] Admin can log in at the dashboard
- [ ] SSL certificates are valid
- [ ] Firewall only allows ports 22, 80, 443
- [ ] PostgreSQL and Redis are not exposed externally
- [ ] Grafana dashboards show data
- [ ] Log files are being written
- [ ] Automatic service restart works (test with `kill`)

## Backup Strategy

### Database

```bash
# Backup
pg_dump -U discord discord_bot > backup_$(date +%Y%m%d).sql

# Restore
psql -U discord discord_bot < backup_20250101.sql
```

### Docker Volumes

```bash
# Backup all volumes
docker run --rm -v discord_bot_postgres_data:/data -v $(pwd):/backup alpine \
  tar czf /backup/postgres_data.tar.gz -C /data .
```

## SSL Certificate Renewal

With certbot, certificates auto-renew. Verify:

```bash
sudo certbot renew --dry-run
```
