# Discord Bot Dashboard

An enterprise Discord bot with a FastAPI REST API backend, a real-time web dashboard, and comprehensive monitoring. Built for managing Discord servers with modular commands, guild-specific settings, RBAC, and Minecraft RCON integration.

## Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Discord API │◄────│  Discord Bot │────►│  FastAPI API  │
│  (Gateway)   │     │  (py-cord)   │     │  (Backend)    │
└──────────────┘     └──────────────┘     └──────┬───────┘
                                                 │
                     ┌──────────────┐     ┌──────┴───────┐
                     │  Dashboard   │────►│  PostgreSQL   │
                     │  (Jinja2)    │     │  + Redis      │
                     └──────────────┘     └──────────────┘
```

**Tech Stack:**
- **Bot:** Python 3.11+, py-cord 2.6+
- **API:** FastAPI, SQLAlchemy (async), Alembic
- **Database:** PostgreSQL 15, Redis 7
- **Dashboard:** Jinja2, Tailwind CSS, HTMX, Alpine.js
- **Auth:** JWT (access + refresh tokens), MFA (TOTP), RBAC
- **Monitoring:** Prometheus, Grafana
- **Deployment:** Docker Compose, systemd, Nginx

## Prerequisites

- Python 3.11+
- PostgreSQL 15+
- Redis 7+
- Node.js 18+ (for Tailwind CSS build, development only)
- Git

## Quick Start (Development)

```bash
# Clone the repository
git clone <repository-url>
cd DiscordBot

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Copy environment file and configure
cp .env.example .env.example
# Edit .env.example with your values (see docs/env-guide.md)

# Build Tailwind CSS
cd dashboard && npm install && npm run build && cd ..

# Run database migrations
cd migrations && alembic upgrade head && cd ..

# Seed default data (roles, modules, admin user)
python scripts/seed.py

# Start the API server
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# In a separate terminal, start the bot
python -m bot.main
```

The API will be available at `http://localhost:8000` and API docs at `http://localhost:8000/docs` (debug mode only).

## PyCharm Setup

See [docs/setup-pycharm.md](docs/setup-pycharm.md) for a step-by-step PyCharm configuration guide.

## Environment Variables

All configuration is done via environment variables (loaded from `.env`). See [docs/env-guide.md](docs/env-guide.md) for a complete reference.

**Required variables:**
| Variable | Description |
|---|---|
| `DISCORD_TOKEN` | Discord bot token from Developer Portal |
| `JWT_SECRET_KEY` | Secret for JWT signing (`openssl rand -hex 32`) |
| `SECRET_KEY` | Application secret key (`openssl rand -hex 32`) |
| `BOT_API_KEY` | Bot-to-API auth key (`openssl rand -hex 32`) |
| `DATABASE_URL` | PostgreSQL connection string |

## Database Migration

This project uses Alembic for database migrations. See [docs/database-migration.md](docs/database-migration.md) for details.

```bash
# Apply all migrations
cd migrations && alembic upgrade head

# Create a new migration after model changes
cd migrations && alembic revision --autogenerate -m "description"

# Rollback one migration
cd migrations && alembic downgrade -1
```

## Running the Project

### Local Development

```bash
# API (with hot reload)
uvicorn api.main:app --reload --port 8000

# Bot
python -m bot.main

# Tailwind CSS (watch mode)
cd dashboard && npm run watch
```

### Docker Compose (Production)

```bash
# Copy and configure environment
cp .env.example .env.example
# Edit .env.example with production values

# Start all services
docker-compose -f docker-compose.prod.yml up -d

# View logs
docker-compose -f docker-compose.prod.yml logs -f

# Stop services
docker-compose -f docker-compose.prod.yml down
```

### Systemd (Bare Metal)

```bash
# Initial setup (as root)
sudo ./scripts/deploy.sh setup

# Deploy
./scripts/deploy.sh deploy

# Update
./scripts/deploy.sh update

# Service management
sudo systemctl status discord-api discord-bot
sudo systemctl restart discord-api
sudo journalctl -u discord-api -f
```

See [docs/deployment.md](docs/deployment.md) for the full deployment guide.

## Project Structure

```
DiscordBot/
├── api/                        # FastAPI backend
│   ├── core/                   # Configuration, database, security
│   │   ├── config.py           # Settings (pydantic-settings)
│   │   ├── database.py         # SQLAlchemy async engine
│   │   ├── jwt_handler.py      # JWT token operations
│   │   ├── rate_limiter.py     # Rate limiting (slowapi)
│   │   └── security.py         # Auth dependencies, password hashing
│   ├── models/                 # SQLAlchemy ORM models
│   │   ├── user.py             # User model
│   │   ├── role.py             # Role + UserRole + Permissions
│   │   ├── api_key.py          # API key model
│   │   ├── audit_log.py        # Audit log model
│   │   ├── bot_settings.py     # Guild settings model
│   │   └── module.py           # Bot module model
│   ├── routes/                 # API endpoints
│   │   ├── auth.py             # Authentication (register, login, MFA)
│   │   ├── bot.py              # Bot management (status, modules)
│   │   ├── settings.py         # Guild settings CRUD
│   │   ├── dashboard.py        # Dashboard data endpoints
│   │   └── minecraft.py        # Minecraft RCON
│   ├── schemas/                # Pydantic schemas
│   ├── websocket/              # WebSocket handlers (logs, status)
│   └── main.py                 # Application entry point
├── bot/                        # Discord bot
│   ├── cogs/                   # Command modules
│   │   ├── admin.py            # Admin commands
│   │   ├── moderation.py       # Moderation commands
│   │   └── minecraft.py        # Minecraft RCON commands
│   ├── services/               # Bot services
│   │   ├── api_connector.py    # HTTP client for backend API
│   │   ├── database.py         # Direct DB access (if needed)
│   │   └── logger.py           # Structured logging
│   ├── config.py               # Bot settings
│   └── main.py                 # Bot entry point
├── dashboard/                  # Web dashboard
│   ├── templates/              # Jinja2 HTML templates
│   ├── static/                 # CSS, JS assets
│   ├── package.json            # Tailwind CSS build
│   └── tailwind.config.js      # Tailwind configuration
├── migrations/                 # Alembic migrations
│   ├── alembic.ini
│   └── alembic/
│       ├── env.py
│       └── versions/           # Migration files
├── monitoring/                 # Prometheus + Grafana
│   ├── prometheus.yml
│   └── grafana/
│       ├── provisioning/       # Auto-provisioning configs
│       └── dashboards/         # Dashboard JSON files
├── docker/                     # Docker configs
│   ├── api.Dockerfile
│   ├── bot.Dockerfile
│   └── nginx.conf
├── systemd/                    # Systemd service files
├── scripts/                    # Utility scripts
│   ├── deploy.sh               # Deployment automation
│   └── seed.py                 # Database seeding
├── tests/                      # Test suite
│   ├── conftest.py             # Test fixtures
│   ├── unit/                   # Unit tests
│   └── integration/            # Integration tests
├── docs/                       # Documentation
├── .env.example                # Environment template
├── requirements.txt            # Python dependencies
├── requirements-dev.txt        # Development dependencies
├── pyproject.toml              # Project configuration
└── docker-compose.prod.yml     # Production Docker Compose
```

## API Documentation

When running in debug mode (`DEBUG=true`), interactive API docs are available at:
- **Swagger UI:** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`

### Key Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/register` | Register new user |
| POST | `/api/v1/auth/login` | Login (returns JWT tokens) |
| POST | `/api/v1/auth/login/mfa` | Login with MFA code |
| POST | `/api/v1/auth/refresh` | Refresh access token |
| GET | `/api/v1/auth/me` | Get current user info |
| POST | `/api/v1/auth/mfa/enable` | Enable MFA (returns QR code) |
| GET | `/api/v1/bot/status` | Get bot status |
| POST | `/api/v1/bot/reload` | Reload bot cogs |
| GET | `/api/v1/bot/modules` | List all modules |
| GET | `/api/v1/settings/{guild_id}` | Get guild settings |
| PUT | `/api/v1/settings/{guild_id}` | Update guild settings |
| GET | `/health` | Health check |

### WebSocket Endpoints

| Endpoint | Description |
|----------|-------------|
| `ws://host/ws/logs` | Real-time log streaming |
| `ws://host/ws/status` | Bot status updates |

## Security

See [docs/security-checklist.md](docs/security-checklist.md) for the full checklist.

**Key security features:**
- JWT tokens with short-lived access tokens (15 min) and refresh tokens (7 days)
- bcrypt password hashing
- TOTP-based MFA
- Role-based access control (RBAC) with granular permissions
- API key authentication with prefix-based lookup
- Rate limiting on all endpoints
- Audit logging for all sensitive actions

### Firewall Rules

In production, only these ports should be open:

| Port | Protocol | Purpose |
|------|----------|---------|
| 22 | TCP | SSH |
| 80 | TCP | HTTP (redirects to HTTPS) |
| 443 | TCP | HTTPS |

PostgreSQL (5432), Redis (6379), RCON (25575), Prometheus (9090), and Grafana (3000) should **not** be exposed.

## Monitoring

### Prometheus

Prometheus scrapes metrics from the API at `/metrics`. Configuration is in `monitoring/prometheus.yml`.

### Grafana

Grafana dashboards are auto-provisioned on startup:
- **API Metrics:** Request rate, response time, error rate, system resources
- **Bot Metrics:** Guild count, command rate, latency, uptime

Access Grafana at `http://localhost:3000` (default credentials: `admin` / set via `GRAFANA_PASSWORD`).

## Nginx Configuration

The Nginx configuration in `docker/nginx.conf` uses placeholder domains:
- `api.yourdomain.de` - API endpoint
- `dashboard.yourdomain.de` - Dashboard

Replace these with your actual domains before deploying.

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=api --cov=bot --cov-report=html

# Run specific test files
pytest tests/unit/api/test_auth.py
pytest tests/integration/

# Run with verbose output
pytest -v
```

## Troubleshooting

See [docs/troubleshooting.md](docs/troubleshooting.md) for common issues and solutions.

## License

MIT
