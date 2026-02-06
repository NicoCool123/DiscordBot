#!/usr/bin/env bash
# =============================================================================
# Discord Bot - Deployment Script
#
# Usage:
#   ./scripts/deploy.sh setup   - Initial server setup (run as root)
#   ./scripts/deploy.sh deploy  - First deployment
#   ./scripts/deploy.sh update  - Update existing deployment
# =============================================================================

set -euo pipefail

# Configuration
APP_USER="discord"
APP_DIR="/opt/discord-bot"
REPO_URL="${REPO_URL:-}"
BRANCH="${BRANCH:-main}"
PYTHON_VERSION="3.11"
DOMAIN_API="${DOMAIN_API:-api.yourdomain.de}"
DOMAIN_DASHBOARD="${DOMAIN_DASHBOARD:-dashboard.yourdomain.de}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# =============================================================================
# Setup Mode - Initial server configuration (run as root)
# =============================================================================
do_setup() {
    log_info "Starting server setup..."

    if [[ $EUID -ne 0 ]]; then
        log_error "Setup must be run as root"
        exit 1
    fi

    # Update system
    log_info "Updating system packages..."
    apt-get update && apt-get upgrade -y

    # Install dependencies
    log_info "Installing system dependencies..."
    apt-get install -y \
        python${PYTHON_VERSION} \
        python${PYTHON_VERSION}-venv \
        python3-pip \
        postgresql \
        postgresql-contrib \
        redis-server \
        nginx \
        certbot \
        python3-certbot-nginx \
        git \
        curl \
        ufw \
        nodejs \
        npm

    # Create application user
    if ! id "${APP_USER}" &>/dev/null; then
        log_info "Creating application user '${APP_USER}'..."
        useradd --system --create-home --shell /bin/bash "${APP_USER}"
    else
        log_info "User '${APP_USER}' already exists"
    fi

    # Create application directory
    log_info "Creating application directory..."
    mkdir -p "${APP_DIR}"
    mkdir -p "${APP_DIR}/logs"
    chown -R "${APP_USER}:${APP_USER}" "${APP_DIR}"

    # Configure PostgreSQL
    log_info "Configuring PostgreSQL..."
    sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='discord'" | grep -q 1 || \
        sudo -u postgres createuser --createdb discord
    sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='discord_bot'" | grep -q 1 || \
        sudo -u postgres createdb --owner=discord discord_bot
    sudo -u postgres psql -c "ALTER USER discord WITH PASSWORD 'changeme';" 2>/dev/null || true
    log_warn "Change the PostgreSQL password! Default is 'changeme'"

    # Configure Redis
    log_info "Configuring Redis..."
    systemctl enable redis-server
    systemctl start redis-server

    # Configure firewall
    log_info "Configuring firewall (ufw)..."
    ufw default deny incoming
    ufw default allow outgoing
    ufw allow 22/tcp comment "SSH"
    ufw allow 443/tcp comment "HTTPS"
    ufw allow 80/tcp comment "HTTP (redirect to HTTPS)"
    ufw --force enable
    log_info "Firewall configured: only SSH (22), HTTP (80), HTTPS (443) allowed"

    # Install systemd services
    log_info "Installing systemd service files..."
    if [ -f "${APP_DIR}/systemd/api.service" ]; then
        cp "${APP_DIR}/systemd/api.service" /etc/systemd/system/discord-api.service
        cp "${APP_DIR}/systemd/bot.service" /etc/systemd/system/discord-bot.service
        systemctl daemon-reload
        systemctl enable discord-api discord-bot
    else
        log_warn "Service files not found yet - run 'deploy' first, then re-run setup"
    fi

    # SSL certificates
    log_info "Obtaining SSL certificates..."
    if [[ "${DOMAIN_API}" != "api.yourdomain.de" ]]; then
        certbot --nginx -d "${DOMAIN_API}" -d "${DOMAIN_DASHBOARD}" --non-interactive --agree-tos --redirect
    else
        log_warn "Skipping SSL - set DOMAIN_API and DOMAIN_DASHBOARD environment variables"
    fi

    log_info "Setup complete!"
    echo ""
    log_warn "Next steps:"
    echo "  1. Edit ${APP_DIR}/.env with your configuration"
    echo "  2. Run: ./scripts/deploy.sh deploy"
}

# =============================================================================
# Deploy Mode - First deployment
# =============================================================================
do_deploy() {
    log_info "Starting deployment..."

    # Clone or copy repository
    if [[ -n "${REPO_URL}" ]]; then
        log_info "Cloning repository..."
        if [ -d "${APP_DIR}/.git" ]; then
            cd "${APP_DIR}" && git pull origin "${BRANCH}"
        else
            git clone --branch "${BRANCH}" "${REPO_URL}" "${APP_DIR}"
        fi
    else
        log_info "No REPO_URL set - assuming code is already at ${APP_DIR}"
    fi

    cd "${APP_DIR}"

    # Create virtual environment
    log_info "Setting up Python virtual environment..."
    python${PYTHON_VERSION} -m venv venv
    source venv/bin/activate

    # Install dependencies
    log_info "Installing Python dependencies..."
    pip install --upgrade pip
    pip install -r requirements.txt

    # Create .env.example if it doesn't exist
    if [ ! -f .env.example ]; then
        log_info "Creating .env from template..."
        cp .env.example.example .env.example
        # Generate secrets
        JWT_SECRET=$(openssl rand -hex 32)
        SECRET_KEY=$(openssl rand -hex 32)
        BOT_API_KEY=$(openssl rand -hex 32)
        sed -i "s/your-super-secret-jwt-key-change-this/${JWT_SECRET}/" .env.example
        sed -i "s/your-super-secret-app-key-change-this/${SECRET_KEY}/" .env.example
        sed -i "s/your-bot-api-key-change-this/${BOT_API_KEY}/" .env.example
        log_warn "Generated secrets in .env - review and update other values!"
    fi

    # Build Tailwind CSS
    log_info "Building Tailwind CSS..."
    if [ -f dashboard/package.json ]; then
        cd dashboard && npm install && npm run build && cd ..
    fi

    # Run database migrations
    log_info "Running database migrations..."
    cd migrations && alembic upgrade head && cd ..

    # Seed default data
    log_info "Seeding default data..."
    python scripts/seed.py

    # Set permissions
    chown -R "${APP_USER}:${APP_USER}" "${APP_DIR}"

    # Install and start services
    if [[ $EUID -eq 0 ]]; then
        log_info "Installing systemd services..."
        cp systemd/api.service /etc/systemd/system/discord-api.service
        cp systemd/bot.service /etc/systemd/system/discord-bot.service
        systemctl daemon-reload
        systemctl enable discord-api discord-bot
        systemctl start discord-api
        systemctl start discord-bot
        log_info "Services started!"
    else
        log_warn "Not running as root - skipping systemd service installation"
        log_warn "Start manually: uvicorn api.main:app --host 0.0.0.0 --port 8000"
    fi

    log_info "Deployment complete!"
}

# =============================================================================
# Update Mode - Update existing deployment
# =============================================================================
do_update() {
    log_info "Starting update..."

    cd "${APP_DIR}"

    # Pull latest changes
    if [ -d .git ]; then
        log_info "Pulling latest changes..."
        git pull origin "${BRANCH}"
    fi

    # Activate venv
    source venv/bin/activate

    # Update dependencies
    log_info "Updating Python dependencies..."
    pip install -r requirements.txt

    # Rebuild CSS
    log_info "Rebuilding Tailwind CSS..."
    if [ -f dashboard/package.json ]; then
        cd dashboard && npm install && npm run build && cd ..
    fi

    # Run migrations
    log_info "Running database migrations..."
    cd migrations && alembic upgrade head && cd ..

    # Restart services
    if [[ $EUID -eq 0 ]]; then
        log_info "Restarting services..."
        systemctl restart discord-api
        systemctl restart discord-bot
        log_info "Services restarted!"
    else
        log_warn "Not running as root - restart services manually"
    fi

    log_info "Update complete!"
}

# =============================================================================
# Main
# =============================================================================
case "${1:-}" in
    setup)
        do_setup
        ;;
    deploy)
        do_deploy
        ;;
    update)
        do_update
        ;;
    *)
        echo "Usage: $0 {setup|deploy|update}"
        echo ""
        echo "Commands:"
        echo "  setup   - Initial server setup (run as root)"
        echo "  deploy  - First deployment"
        echo "  update  - Update existing deployment"
        exit 1
        ;;
esac
