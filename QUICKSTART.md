# ⚡ Quick Start - Server Deployment

## 🚀 In 10 Minuten auf dashboard.redcrafteryt11.net

Diese Kurzanleitung zeigt dir die **wichtigsten Schritte** für ein schnelles Deployment.

Für Details siehe: [DEPLOYMENT.md](DEPLOYMENT.md)

---

## 1️⃣ DNS konfigurieren

Bei deinem Domain-Provider (z.B. Cloudflare, Namecheap):

```
A-Record: dashboard.redcrafteryt11.net → DEINE_SERVER_IP
A-Record: api.redcrafteryt11.net → DEINE_SERVER_IP
```

**Test nach 5 Min:**
```bash
ping dashboard.redcrafteryt11.net
```

---

## 2️⃣ Server-Pakete installieren

```bash
ssh root@DEINE_SERVER_IP

# Alles in einem:
apt update && apt upgrade -y
apt install -y python3.11 python3.11-venv python3-pip postgresql \
               postgresql-contrib redis-server nginx certbot \
               python3-certbot-nginx git
```

---

## 3️⃣ Datenbank einrichten

```bash
sudo -u postgres psql
```

```sql
CREATE DATABASE discord_bot;
CREATE USER botuser WITH PASSWORD 'sicheres_passwort';
GRANT ALL PRIVILEGES ON DATABASE discord_bot TO botuser;
\q
```

---

## 4️⃣ Bot-Dateien hochladen

```bash
# Methode 1: Git Clone
cd /opt
sudo mkdir discord-bot
sudo chown $USER:$USER discord-bot
cd discord-bot
git clone https://github.com/DEIN_REPO.git .

# Methode 2: SCP Upload (von deinem PC)
scp -r /mnt/c/Users/Nicolas/PycharmProjects/DiscordBot/* user@SERVER:/opt/discord-bot/
```

---

## 5️⃣ Python Environment

```bash
cd /opt/discord-bot
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## 6️⃣ .env erstellen

```bash
cp .env.minimal .env
nano .env
```

**Wichtigste Änderungen:**

```bash
# Sichere Keys generieren:
JWT_SECRET_KEY=$(openssl rand -hex 32)
SECRET_KEY=$(openssl rand -hex 32)
BOT_API_KEY=$(openssl rand -hex 32)

# Database
DATABASE_URL=postgresql+asyncpg://botuser:DEIN_PASSWORT@localhost:5432/discord_bot

# Discord
DISCORD_CLIENT_ID=DEINE_ID
DISCORD_CLIENT_SECRET=DEIN_SECRET
DISCORD_TOKEN=DEIN_BOT_TOKEN

# URLs
API_URL=https://api.redcrafteryt11.net
DASHBOARD_URL=https://dashboard.redcrafteryt11.net
DISCORD_OAUTH_REDIRECT_URI=https://dashboard.redcrafteryt11.net/api/v1/auth/discord/callback
```

---

## 7️⃣ Migration ausführen

```bash
cd /opt/discord-bot
source venv/bin/activate
alembic upgrade head
```

---

## 8️⃣ Deployment Script ausführen

```bash
chmod +x deploy.sh
./deploy.sh
```

**Das Script macht:**
- ✅ Systemd Services erstellen
- ✅ Nginx konfigurieren
- ✅ Services starten

---

## 9️⃣ SSL einrichten

```bash
sudo certbot --nginx -d dashboard.redcrafteryt11.net -d api.redcrafteryt11.net
```

- Email eingeben
- Terms akzeptieren
- Redirect: Yes

---

## 🔟 Admin-User erstellen

```bash
cd /opt/discord-bot
source venv/bin/activate
python
```

```python
import asyncio
from api.core.database import AsyncSessionLocal
from api.models.user import User
from api.core.security import get_password_hash

async def create_admin():
    async with AsyncSessionLocal() as db:
        user = User(
            username="admin",
            email="admin@redcrafteryt11.net",
            password_hash=get_password_hash("DeinSicheresPasswort123!"),
            is_superuser=True,
            is_active=True,
            is_verified=True
        )
        db.add(user)
        await db.commit()
        print("Admin created!")

asyncio.run(create_admin())
exit()
```

---

## ✅ Fertig!

**Dashboard aufrufen:**
```
https://dashboard.redcrafteryt11.net
```

**Login:**
```
Username: admin
Passwort: DeinSicheresPasswort123!
```

**Bot in Discord testen:**
```
/admin status
/util ping
```

---

## 🔧 Nützliche Befehle

### Logs ansehen
```bash
sudo journalctl -u discord-bot-api -f
sudo journalctl -u discord-bot -f
```

### Services neustarten
```bash
sudo systemctl restart discord-bot-api
sudo systemctl restart discord-bot
```

### Code aktualisieren
```bash
cd /opt/discord-bot
git pull
source venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
sudo systemctl restart discord-bot-api
sudo systemctl restart discord-bot
```

---

## ⚠️ Probleme?

### Dashboard lädt nicht:
```bash
sudo systemctl status discord-bot-api
sudo journalctl -u discord-bot-api -n 50
```

### Bot offline:
```bash
sudo systemctl status discord-bot
sudo journalctl -u discord-bot -n 50
```

### Nginx Fehler:
```bash
sudo nginx -t
sudo tail -f /var/log/nginx/error.log
```

---

## 📖 Weitere Dokumentation

- [DEPLOYMENT.md](DEPLOYMENT.md) - Vollständige Deployment-Anleitung
- [PRIVACY.md](PRIVACY.md) - Datenschutz & GDPR
- [README.md](README.md) - Allgemeine Informationen

---

**Bei Fragen: Erstelle ein Issue auf GitHub! 🚀**
