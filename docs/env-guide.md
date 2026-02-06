# Environment Variables Guide

All configuration is loaded from a `.env` file via pydantic-settings. Copy `.env.example` to `.env` and fill in the values.

```bash
cp .env.example .env.example
```

## Required Variables

These **must** be set for the application to start.

### Authentication Secrets

| Variable | Description | How to Generate |
|----------|-------------|-----------------|
| `JWT_SECRET_KEY` | Secret key for signing JWT tokens. Must be at least 32 characters. | `openssl rand -hex 32` |
| `SECRET_KEY` | General application secret key. | `openssl rand -hex 32` |
| `BOT_API_KEY` | API key for bot-to-backend authentication. Shared between bot and API. | `openssl rand -hex 32` |

### Discord

| Variable | Description | Where to Get It |
|----------|-------------|-----------------|
| `DISCORD_TOKEN` | Discord bot token. | [Discord Developer Portal](https://discord.com/developers/applications) > Bot > Token |

### Database

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:password@localhost:5432/discord_bot` | PostgreSQL connection string using the asyncpg driver. |

## Optional Variables

### API Server

| Variable | Default | Description |
|----------|---------|-------------|
| `API_HOST` | `0.0.0.0` | Host to bind the API server to. |
| `API_PORT` | `8000` | Port for the API server. |
| `API_URL` | `http://localhost:8000` | Public URL of the API (used by bot and dashboard). |
| `DEBUG` | `false` | Enable debug mode. Enables `/docs`, hot reload, verbose errors. |
| `ENVIRONMENT` | `development` | `development` or `production`. |

### Redis

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL. Used for caching and rate limiting in production. |

### JWT Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `JWT_ALGORITHM` | `HS256` | Algorithm for JWT signing. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `15` | Access token lifetime in minutes. |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Refresh token lifetime in days. |

### CORS & Security

| Variable | Default | Description |
|----------|---------|-------------|
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | Comma-separated list of allowed hosts. |
| `CORS_ORIGINS` | `http://localhost:3000` | Comma-separated list of allowed CORS origins. |

### Discord Bot

| Variable | Default | Description |
|----------|---------|-------------|
| `DISCORD_PREFIX` | `!` | Default command prefix. Can be overridden per guild. |

### Dashboard

| Variable | Default | Description |
|----------|---------|-------------|
| `DASHBOARD_URL` | `http://localhost:3000` | Public URL of the dashboard. |

### Minecraft RCON

| Variable | Default | Description |
|----------|---------|-------------|
| `RCON_ENABLED` | `false` | Enable Minecraft RCON integration. |
| `RCON_HOST` | `localhost` | RCON server hostname. |
| `RCON_PORT` | `25575` | RCON server port. |
| `RCON_PASSWORD` | (empty) | RCON authentication password. |

### Logging

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_LEVEL` | `INFO` | Logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`. |
| `LOG_FORMAT` | `json` | Log output format: `json` or `text`. |
| `LOG_FILE` | (none) | Optional file path for log output. |

### Monitoring

| Variable | Default | Description |
|----------|---------|-------------|
| `METRICS_ENABLED` | `true` | Enable Prometheus metrics endpoint. |
| `SENTRY_DSN` | (none) | Sentry DSN for error tracking. |

### Docker-specific

These are used in `docker-compose.prod.yml`:

| Variable | Description |
|----------|-------------|
| `POSTGRES_USER` | PostgreSQL username. |
| `POSTGRES_PASSWORD` | PostgreSQL password. |
| `POSTGRES_DB` | PostgreSQL database name. |
| `REDIS_PASSWORD` | Redis authentication password. |
| `GRAFANA_USER` | Grafana admin username (default: `admin`). |
| `GRAFANA_PASSWORD` | Grafana admin password. |

## Example: Minimal Development `.env`

```env
DISCORD_TOKEN=your-discord-bot-token
JWT_SECRET_KEY=dev-jwt-secret-change-in-production-12345678
SECRET_KEY=dev-secret-key-change-in-production-12345678
BOT_API_KEY=dev-bot-api-key-change-in-production
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/discord_bot
DEBUG=true
```

## Example: Production `.env`

```env
DISCORD_TOKEN=<real-token>
JWT_SECRET_KEY=<generated-with-openssl>
SECRET_KEY=<generated-with-openssl>
BOT_API_KEY=<generated-with-openssl>
DATABASE_URL=postgresql+asyncpg://discord:<password>@localhost:5432/discord_bot
REDIS_URL=redis://:redispassword@localhost:6379/0
ENVIRONMENT=production
DEBUG=false
API_URL=https://api.yourdomain.de
DASHBOARD_URL=https://dashboard.yourdomain.de
CORS_ORIGINS=https://dashboard.yourdomain.de
ALLOWED_HOSTS=api.yourdomain.de,dashboard.yourdomain.de
LOG_LEVEL=WARNING
LOG_FORMAT=json
```
