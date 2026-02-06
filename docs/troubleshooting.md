# Troubleshooting

Common issues and their solutions.

## Startup Issues

### `pydantic_core._pydantic_core.ValidationError: ... field required`

**Cause:** Required environment variables are missing.

**Solution:** Ensure your `.env` file exists and contains all required variables:
```bash
cp .env.example .env.example
# Edit and fill in: DISCORD_TOKEN, JWT_SECRET_KEY, SECRET_KEY, BOT_API_KEY
```

### `ModuleNotFoundError: No module named 'xyz'`

**Cause:** Dependencies not installed.

**Solution:**
```bash
pip install -r requirements.txt
# For development/testing:
pip install -r requirements-dev.txt
```

### `sqlalchemy.exc.OperationalError: could not connect to server`

**Cause:** PostgreSQL is not running or connection string is wrong.

**Solution:**
```bash
# Check PostgreSQL is running
sudo systemctl status postgresql

# Verify DATABASE_URL in .env.example
# Format: postgresql+asyncpg://user:password@host:5432/dbname

# Test connection
psql -U postgres -h localhost -d discord_bot
```

### `redis.exceptions.ConnectionError: Error connecting to localhost:6379`

**Cause:** Redis is not running.

**Solution:**
```bash
sudo systemctl start redis-server
sudo systemctl enable redis-server
```

## Database Issues

### `alembic.util.exc.CommandError: Can't locate revision`

**Cause:** Migration history is inconsistent.

**Solution:**
```bash
cd migrations
# Check current state
alembic current

# If needed, stamp to a known revision
alembic stamp head
```

### `sqlalchemy.exc.ProgrammingError: relation "users" does not exist`

**Cause:** Migrations haven't been run.

**Solution:**
```bash
cd migrations && alembic upgrade head
```

### Tables exist but migrations fail

**Cause:** Database was created manually or by `Base.metadata.create_all()`.

**Solution:**
```bash
cd migrations
alembic stamp head  # Mark current DB as up-to-date
```

## Bot Issues

### `discord.errors.LoginFailure: Improper token has been passed`

**Cause:** Invalid Discord bot token.

**Solution:**
1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Select your application > Bot
3. Reset and copy the new token
4. Update `DISCORD_TOKEN` in `.env`

### Bot is online but doesn't respond to commands

**Cause:** Missing intents or command sync issues.

**Solution:**
1. Enable required intents in Developer Portal:
   - Server Members Intent
   - Message Content Intent
2. Wait up to 1 hour for slash command sync, or trigger manual sync

### `aiohttp.client_exceptions.ClientConnectorError: Cannot connect to host api`

**Cause:** Bot can't reach the API server.

**Solution:**
- Verify `API_URL` in `.env` points to the correct address
- Ensure the API is running: `curl http://localhost:8000/health`
- In Docker: services communicate via container names (`http://api:8000`)

## Dashboard Issues

### Dashboard loads without CSS styling

**Cause:** Tailwind CSS hasn't been compiled.

**Solution:**
```bash
cd dashboard
npm install
npm run build
```

Verify `dashboard/static/css/main.css` exists.

### "401 Unauthorized" on all API calls from the dashboard

**Cause:** JWT token expired or not present.

**Solution:**
- Clear browser localStorage and log in again
- Check that `JWT_SECRET_KEY` matches between API and dashboard
- Verify access token expiry: `ACCESS_TOKEN_EXPIRE_MINUTES` (default: 15)

### WebSocket connection fails

**Cause:** WebSocket endpoint not accessible.

**Solution:**
- In development: use `ws://localhost:8000/ws/...`
- In production: ensure Nginx proxies WebSocket connections (check `proxy_set_header Upgrade` in nginx.conf)
- Check browser console for specific error messages

## Docker Issues

### `Container exits with code 1`

**Solution:**
```bash
# Check logs
docker-compose -f docker-compose.prod.yml logs api

# Common fixes:
# 1. Missing .env.example file
# 2. Database not ready yet (check healthcheck)
# 3. Invalid configuration
```

### `postgres | FATAL: password authentication failed`

**Cause:** PostgreSQL credentials don't match.

**Solution:**
Ensure `POSTGRES_USER`, `POSTGRES_PASSWORD`, and `POSTGRES_DB` in `.env` match what's in `DATABASE_URL`.

### Nginx returns 502 Bad Gateway

**Cause:** API service is not ready or not reachable.

**Solution:**
```bash
# Check API container
docker-compose -f docker-compose.prod.yml logs api

# Verify API health inside the network
docker-compose -f docker-compose.prod.yml exec nginx curl http://api:8000/health
```

## Testing Issues

### `FAILED - pydantic_core._pydantic_core.ValidationError`

**Cause:** Test environment variables not set.

**Solution:** Tests need minimal env vars. The conftest.py sets defaults via `os.environ.setdefault()`, but if settings are loaded before tests, they might fail. Set explicitly:
```bash
JWT_SECRET_KEY=test SECRET_KEY=test BOT_API_KEY=test pytest
```

### `sqlalchemy.exc.OperationalError` during tests

**Cause:** Test database configuration issue.

**Solution:** Tests use SQLite in-memory. Ensure `aiosqlite` is installed:
```bash
pip install aiosqlite
```

## Performance Issues

### API responses are slow

**Possible causes:**
1. Missing database indexes (check `EXPLAIN ANALYZE` on slow queries)
2. N+1 query problem (use `selectin` loading, which is already configured)
3. Rate limiter using memory storage (switch to Redis in production)

### Bot has high latency

**Possible causes:**
1. API server is under load
2. Network latency between bot and API
3. Too many guilds for a single bot process

## Getting Help

If you can't resolve an issue:

1. Check the application logs:
   ```bash
   # Systemd
   journalctl -u discord-api -n 100
   # Docker
   docker-compose logs --tail=100 api
   ```
2. Enable debug mode temporarily: `DEBUG=true`
3. Check the health endpoint: `curl localhost:8000/health`
4. Review the `.env` configuration against `docs/env-guide.md`
