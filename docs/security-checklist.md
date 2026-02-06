# Security Checklist

Use this checklist before deploying to production.

## Authentication & Authorization

- [ ] `JWT_SECRET_KEY` is a random 64+ character string (generated with `openssl rand -hex 32`)
- [ ] `SECRET_KEY` is a random 64+ character string
- [ ] `BOT_API_KEY` is a random 64+ character string
- [ ] Access token expiry is short (default: 15 minutes)
- [ ] Refresh token expiry is reasonable (default: 7 days)
- [ ] Default admin password has been changed from `Admin123!`
- [ ] Debug mode is disabled (`DEBUG=false`)
- [ ] API docs are disabled in production (automatic when `DEBUG=false`)

## Passwords & Secrets

- [ ] All passwords are hashed with bcrypt (handled by passlib)
- [ ] No secrets are stored in code or committed to git
- [ ] `.env` file is in `.gitignore`
- [ ] No default passwords remain in configuration

## Network & Firewall

- [ ] Only ports 22 (SSH), 80 (HTTP), 443 (HTTPS) are open
- [ ] PostgreSQL (5432) is NOT exposed externally
- [ ] Redis (6379) is NOT exposed externally
- [ ] RCON (25575) is NOT exposed externally
- [ ] Prometheus (9090) is NOT exposed externally
- [ ] Grafana (3000) is NOT exposed externally (or behind auth proxy)
- [ ] SSH uses key-based authentication (password auth disabled)
- [ ] Fail2ban is installed and configured

## SSL/TLS

- [ ] All traffic is served over HTTPS
- [ ] HTTP redirects to HTTPS
- [ ] TLS 1.2+ only (TLS 1.0 and 1.1 disabled)
- [ ] HSTS header is set (included in nginx.conf)
- [ ] SSL certificates auto-renew (certbot)

## API Security

- [ ] Rate limiting is enabled on all endpoints
- [ ] Auth endpoints have stricter rate limits (5/minute for login)
- [ ] CORS origins are restricted to your dashboard domain
- [ ] `ALLOWED_HOSTS` is set to your actual domains
- [ ] Request validation rejects malformed input (Pydantic)
- [ ] SQL injection is prevented (SQLAlchemy ORM)

## Data Protection

- [ ] Audit logging is enabled for all sensitive actions
- [ ] API keys are stored as hashes, not plaintext
- [ ] User passwords are never logged or returned in responses
- [ ] MFA secrets are stored encrypted (or at least hashed)
- [ ] Database backups are encrypted

## Application Security

- [ ] No `import *` in production code (except intentional model imports)
- [ ] Error messages don't leak internal details in production
- [ ] File uploads are validated (if applicable)
- [ ] WebSocket connections are authenticated
- [ ] CSRF protection is enabled (for form submissions)

## Infrastructure

- [ ] Server OS is up to date
- [ ] Python packages are up to date (check with `pip audit`)
- [ ] Docker images use specific version tags (not `latest` in production)
- [ ] Container runs as non-root user
- [ ] Systemd services have security hardening (PrivateTmp, ProtectSystem, etc.)
- [ ] Log rotation is configured

## Discord Bot

- [ ] Bot token is kept secret
- [ ] Bot has minimum required permissions (intents)
- [ ] RCON commands are whitelisted (dangerous commands blocked)
- [ ] Bot validates guild permissions before executing commands

## Monitoring

- [ ] Prometheus is collecting metrics
- [ ] Grafana alerts are configured for errors and anomalies
- [ ] Log aggregation is set up
- [ ] Health check endpoint is monitored
- [ ] Uptime monitoring is in place (external service)

## Regular Maintenance

- [ ] Review audit logs weekly
- [ ] Rotate secrets quarterly
- [ ] Update dependencies monthly
- [ ] Review firewall rules quarterly
- [ ] Test disaster recovery plan annually
